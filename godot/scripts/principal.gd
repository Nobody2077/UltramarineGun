extends Node3D
## UltramarineGun: escena principal. Todo se construye desde código para que se lea
## de arriba a abajo: entorno -> arma -> efectos -> sonido -> HUD -> lógica del arma.
##
## Controles:
##   Tablet: tirón hacia arriba = disparo | inclinar y volver = recarga | zonas táctiles.
##   PC:     ESPACIO (mantener = ráfaga) = disparo | R = recarga | clic en las zonas.
##
## Para fotos de prueba en el PC:
##   godot --path . -- --foto=foto.png --accion=disparo --tiempo=1.5

const MUNICION_MAX := 18
const CADENCIA := 0.13            # segundos entre disparos en ráfaga (≈ 7,7 por segundo)
const AJUSTES := "user://ajustes.cfg"

enum Estado { LISTO, RECARGANDO }
var estado := Estado.LISTO
var municion := MUNICION_MAX
var objetivo := "HEREJE"

# Escena
var camara: Camera3D
var pivote: Node3D
var arma: Node3D
var anim: AnimationPlayer
var fogonazo: MeshInstance3D
var mats_fogonazo: Array[ShaderMaterial] = []
var luz_boca: OmniLight3D
var humos: Array[CPUParticles3D] = []
var chispas: Array[CPUParticles3D] = []
var _i_efecto := 0

# Sonido
var reproductores: Array[AudioStreamPlayer] = []
var _i_audio := 0
var disparos: Array[AudioStream] = []
var snd := {}

# Estado de juego
var gestos := Gestos.new()
var voz := EspirituMaquina.new()
var gatillo_apretado := false
var _t_ultimo := -10.0
var _clic_vacio_dado := false
var _temblor := 0.0
var _t_fogonazo := 0.0
var calor := 0.0                  # 0 = cañón frío, 1 = al rojo vivo
var _t_sin_disparar := 0.0
var _aviso_calor := false
var mat_calor: ShaderMaterial
var humo_calor: CPUParticles3D
var _escala_fogonazo := 1.0
var _t := 0.0
var _t_quieto := 0.0

# HUD
var lbl_municion: Label
var lbl_total: Label
var lbl_estado: Label
var lbl_voz: Label
var lbl_panel: Label
var panel_sensores: PanelContainer
var btn_voz: Button
var destello: ColorRect
var _tw_subtitulo: Tween

# Fotos de prueba
var _foto := ""
var _accion := ""
var _t_foto := 1.5


func _ready() -> void:
	randomize()
	_leer_argumentos()
	_crear_entorno()
	_crear_arma()
	_crear_efectos()
	_crear_audio()
	_crear_hud()
	_cargar_ajustes()
	voz.iniciar()
	voz.dijo.connect(_mostrar_subtitulo)
	gestos.disparo.connect(disparar)
	gestos.recarga.connect(recargar)
	_actualizar_hud()
	if _foto != "":
		_preparar_foto()


# ---------------------------------------------------------------------------
# Entorno: cámara, luces, cielo para los reflejos del metal, brillo (glow)
# ---------------------------------------------------------------------------
func _crear_entorno() -> void:
	# HDRI: foto panorámica de 360° de un taller real (Poly Haven, CC0). No se ve de fondo,
	# pero el metal la REFLEJA: ventanas y lámparas aparecen como brillos en los cantos.
	# Eso es lo que hace que el metal parezca metal y no plástico pintado.
	var cielo_mat := PanoramaSkyMaterial.new()
	cielo_mat.panorama = load("res://assets/hdri/machine_shop_02_1k.hdr")
	var cielo := Sky.new()
	cielo.sky_material = cielo_mat
	cielo.radiance_size = Sky.RADIANCE_SIZE_256       # suficiente para reflejos y liviano en la tablet

	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.025, 0.028, 0.038)
	env.sky = cielo
	env.sky_rotation = Vector3(0, deg_to_rad(110), 0)  # gira el taller para que una ventana quede de frente
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.7
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.glow_enabled = true                           # el fogonazo "sangra" luz alrededor
	env.glow_intensity = 0.9
	env.glow_bloom = 0.05
	env.glow_hdr_threshold = 0.9
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	var clave := DirectionalLight3D.new()
	clave.rotation_degrees = Vector3(-40, -25, 0)
	clave.light_energy = 1.2
	add_child(clave)
	var contra := DirectionalLight3D.new()
	contra.rotation_degrees = Vector3(-20, 150, 0)
	contra.light_color = Color(0.6, 0.72, 1.0)
	contra.light_energy = 1.4
	add_child(contra)

	camara = Camera3D.new()
	camara.fov = 38
	camara.position = Vector3(0.56, 0.16, 1.18)
	add_child(camara)
	camara.look_at(Vector3(0.40, 0.05, 0.0))


# ---------------------------------------------------------------------------
# El arma (el .glb de Blender) y el shader del fogonazo
# ---------------------------------------------------------------------------
func _crear_arma() -> void:
	pivote = Node3D.new()
	add_child(pivote)
	arma = (load("res://assets/modelos/UltramarineGun.glb") as PackedScene).instantiate()
	pivote.add_child(arma)
	anim = arma.find_child("AnimationPlayer", true, false) as AnimationPlayer
	anim.animation_finished.connect(_al_terminar_animacion)

	fogonazo = arma.find_child("Fogonazo", true, false) as MeshInstance3D
	# El fogonazo lo maneja el código (aparece en el MISMO fotograma del disparo, con tamaño
	# y giro al azar), así que se quita su pista de la animación que vino de Blender.
	var a_disparo := anim.get_animation("Disparo")
	for i in range(a_disparo.get_track_count() - 1, -1, -1):
		if "Fogonazo" in str(a_disparo.track_get_path(i)):
			a_disparo.remove_track(i)
	var sh := load("res://shaders/fogonazo.gdshader") as Shader
	for s in fogonazo.mesh.get_surface_count():
		var m := fogonazo.mesh.surface_get_material(s)
		var es_frente := m != null and "frente" in m.resource_name.to_lower()
		var sm := ShaderMaterial.new()
		sm.shader = sh
		sm.set_shader_parameter("forma", load("res://assets/texturas/fogonazo_%s.png" % ("frente" if es_frente else "lado")))
		sm.set_shader_parameter("intensidad", 3.4 if es_frente else 2.6)
		fogonazo.set_surface_override_material(s, sm)
		mats_fogonazo.append(sm)


# ---------------------------------------------------------------------------
# Efectos del disparo: luz, humo y chispas en la boca del cañón
# ---------------------------------------------------------------------------
func _crear_efectos() -> void:
	# Los efectos cuelgan del nodo que se mueve con el retroceso, en la boca del cañón.
	var padre := fogonazo.get_parent() as Node3D
	var boca := fogonazo.position

	luz_boca = OmniLight3D.new()
	luz_boca.light_color = Color(1.0, 0.62, 0.25)
	luz_boca.omni_range = 1.4
	luz_boca.light_energy = 0.0
	luz_boca.position = boca + Vector3(0.04, 0.0, 0.06)
	padre.add_child(luz_boca)

	var circulo := GradientTexture2D.new()
	circulo.fill = GradientTexture2D.FILL_RADIAL
	circulo.fill_from = Vector2(0.5, 0.5)
	circulo.fill_to = Vector2(1.0, 0.5)
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	circulo.gradient = g

	for i in 4:
		humos.append(_particulas_humo(circulo))
		padre.add_child(humos[i])
		humos[i].position = boca + Vector3(0.02, 0, 0)
	for i in 3:
		chispas.append(_particulas_chispas(circulo))
		padre.add_child(chispas[i])
		chispas[i].position = boca

	# Cañón al rojo: un cilindro apenas más grande que la bocacha, con el shader de calor
	var tubo := CylinderMesh.new()
	tubo.top_radius = 0.0475          # apenas más grande que la bocacha (4,6 cm de radio)
	tubo.bottom_radius = 0.0475
	tubo.height = 0.088
	tubo.cap_top = false          # sin tapas: el agujero de la boca sigue viéndose
	tubo.cap_bottom = false
	mat_calor = ShaderMaterial.new()
	mat_calor.shader = load("res://shaders/calor.gdshader")
	tubo.material = mat_calor
	var brillo := MeshInstance3D.new()
	brillo.mesh = tubo
	brillo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	brillo.rotation_degrees = Vector3(0, 0, 90)          # el cilindro nace vertical: lo acostamos
	brillo.position = boca + Vector3(-0.047, 0, 0)
	padre.add_child(brillo)

	# Humo de calor: hilitos que suben de la boca mientras está caliente
	humo_calor = _particulas_humo(circulo)
	humo_calor.one_shot = false
	humo_calor.explosiveness = 0.0
	humo_calor.amount = 14
	humo_calor.lifetime = 1.8
	humo_calor.direction = Vector3(0, 1, 0)
	humo_calor.spread = 10
	humo_calor.initial_velocity_min = 0.03
	humo_calor.initial_velocity_max = 0.08
	humo_calor.gravity = Vector3(0, 0.06, 0)
	var tenue := Gradient.new()
	tenue.set_color(0, Color(0.7, 0.7, 0.72, 0.16))
	tenue.set_color(1, Color(0.5, 0.5, 0.55, 0.0))
	humo_calor.color_ramp = tenue
	humo_calor.position = boca + Vector3(-0.03, 0.04, 0)
	padre.add_child(humo_calor)


func _particulas_humo(tex: Texture2D) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.emitting = false
	p.one_shot = true
	p.amount = 12
	p.lifetime = 1.6
	p.explosiveness = 0.85
	p.local_coords = false              # el humo se queda en el aire aunque el arma se mueva
	p.direction = Vector3(1, 0.25, 0)
	p.spread = 28
	p.initial_velocity_min = 0.12
	p.initial_velocity_max = 0.5
	p.gravity = Vector3(0, 0.10, 0)     # sube despacio
	p.damping_min = 0.25
	p.damping_max = 0.5
	p.scale_amount_min = 0.7
	p.scale_amount_max = 1.3
	var crece := Curve.new()
	crece.max_value = 3.0
	crece.add_point(Vector2(0, 0.4))
	crece.add_point(Vector2(1, 2.6))
	p.scale_amount_curve = crece
	var col := Gradient.new()
	col.set_color(0, Color(0.6, 0.58, 0.55, 0.38))
	col.set_color(1, Color(0.35, 0.36, 0.40, 0.0))
	p.color_ramp = col
	var q := QuadMesh.new()
	q.size = Vector2(0.07, 0.07)
	var m := StandardMaterial3D.new()
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.billboard_keep_scale = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.albedo_texture = tex
	q.material = m
	p.mesh = q
	return p


func _particulas_chispas(tex: Texture2D) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.emitting = false
	p.one_shot = true
	p.amount = 14
	p.lifetime = 0.28
	p.explosiveness = 1.0
	p.local_coords = false
	p.direction = Vector3(1, 0, 0)
	p.spread = 20
	p.initial_velocity_min = 2.5
	p.initial_velocity_max = 5.5
	p.gravity = Vector3(0, -5, 0)
	var col := Gradient.new()
	col.set_color(0, Color(4.0, 2.6, 1.0, 1.0))     # valores > 1: activan el glow
	col.set_color(1, Color(1.0, 0.25, 0.02, 0.0))
	p.color_ramp = col
	var q := QuadMesh.new()
	q.size = Vector2(0.012, 0.012)
	var m := StandardMaterial3D.new()
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.albedo_texture = tex
	q.material = m
	p.mesh = q
	return p


# ---------------------------------------------------------------------------
# Sonido: varios reproductores en rotación para que un disparo no corte al anterior
# ---------------------------------------------------------------------------
func _crear_audio() -> void:
	for i in 8:
		var r := AudioStreamPlayer.new()
		add_child(r)
		reproductores.append(r)
	for i in [1, 2, 3]:
		disparos.append(load("res://assets/audio/bolter_disparo_%d.wav" % i))
	for n in ["cargador_fuera", "cargador_dentro", "palanca", "gatillo_vacio"]:
		snd[n] = load("res://assets/audio/%s.wav" % n)


func _sonar(stream: AudioStream, tono := 1.0, volumen_db := 0.0) -> void:
	var r := reproductores[_i_audio]
	_i_audio = (_i_audio + 1) % reproductores.size()
	r.stream = stream
	r.pitch_scale = tono
	r.volume_db = volumen_db
	r.play()


# ---------------------------------------------------------------------------
# Lógica del arma (máquina de estados: LISTO <-> RECARGANDO)
# ---------------------------------------------------------------------------
func disparar() -> void:
	if estado == Estado.RECARGANDO:
		return
	var ahora := Time.get_ticks_msec() / 1000.0
	if ahora - _t_ultimo < CADENCIA:
		return
	_t_ultimo = ahora
	_t_quieto = 0.0

	if municion <= 0:
		if not _clic_vacio_dado:
			_clic_vacio_dado = true
			anim.stop()
			anim.play("Gatillo_vacio")
			_sonar(snd["gatillo_vacio"])
			voz.al_vaciar()
		return

	municion -= 1
	anim.stop()
	anim.play("Disparo")

	# Fogonazo distinto cada vez: forma (semilla del shader), tamaño y giro al azar
	var semilla := randf() * 100.0
	for sm in mats_fogonazo:
		sm.set_shader_parameter("semilla", semilla)
	_escala_fogonazo = randf_range(0.9, 1.3)
	fogonazo.scale = Vector3.ONE * _escala_fogonazo
	fogonazo.rotation.x = randf() * TAU
	_t_fogonazo = 0.055

	# Luz del fogonazo: sube de golpe y se apaga en 80 ms
	luz_boca.light_energy = 5.0
	create_tween().tween_property(luz_boca, "light_energy", 0.0, 0.09)

	humos[_i_efecto % humos.size()].restart()
	chispas[_i_efecto % chispas.size()].restart()
	_i_efecto += 1

	_sonar(disparos.pick_random(), randf_range(0.94, 1.05), randf_range(-1.5, 0.0))

	# Destello en toda la pantalla (sustituto del LED que la tablet no tiene)
	destello.color.a = 0.15
	create_tween().tween_property(destello, "color:a", 0.0, 0.08)

	_temblor = minf(_temblor + 0.55, 1.0)
	calor = minf(calor + 0.065, 1.0)
	_t_sin_disparar = 0.0
	if calor > 0.85 and not _aviso_calor:
		_aviso_calor = true
		voz.al_calentar()
	Input.vibrate_handheld(70, 1.0)
	voz.al_disparar(objetivo)
	_actualizar_hud()
	if municion == 0:
		get_tree().create_timer(0.35).timeout.connect(voz.al_vaciar)


func recargar() -> void:
	if estado == Estado.RECARGANDO or municion == MUNICION_MAX:
		return
	estado = Estado.RECARGANDO
	_t_quieto = 0.0
	anim.stop()
	anim.play("Recarga")
	# Sonidos sincronizados con los fotogramas de la animación (60 fps):
	_en(0.27, func(): _sonar(snd["cargador_fuera"]))                                   # frame 16
	_en(1.00, func():                                                                    # frame 60
		_sonar(snd["cargador_dentro"])
		Input.vibrate_handheld(40, 0.8))
	_en(1.22, func():                                                                    # frame 73
		_sonar(snd["palanca"])
		Input.vibrate_handheld(55, 1.0))
	_actualizar_hud()


func _en(segundos: float, que: Callable) -> void:
	get_tree().create_timer(segundos).timeout.connect(que)


func _al_terminar_animacion(nombre: StringName) -> void:
	if nombre == &"Recarga":
		municion = MUNICION_MAX
		estado = Estado.LISTO
		_clic_vacio_dado = false
		voz.al_recargar()
		_actualizar_hud()


func elegir_objetivo(nuevo: String) -> void:
	objetivo = nuevo
	voz.al_fijar(objetivo)
	_guardar_ajustes()


# ---------------------------------------------------------------------------
# Cada fotograma
# ---------------------------------------------------------------------------
func _process(delta: float) -> void:
	_t += delta
	gestos.procesar(delta)

	# Vida del fogonazo: grande -> se encoge -> desaparece (unos 3 fotogramas)
	if _t_fogonazo > 0.0:
		_t_fogonazo -= delta
		var vida := clampf(_t_fogonazo / 0.055, 0.0, 1.0)
		fogonazo.scale = Vector3.ONE * maxf(_escala_fogonazo * (0.45 + 0.55 * vida), 0.0001)
		if _t_fogonazo <= 0.0:
			fogonazo.scale = Vector3.ONE * 0.0001
	if gatillo_apretado:
		disparar()

	# Calor del cañón: se enfría solo medio segundo después del último disparo
	_t_sin_disparar += delta
	if _t_sin_disparar > 0.5:
		calor = maxf(calor - delta * 0.09, 0.0)
	if calor < 0.4:
		_aviso_calor = false
	mat_calor.set_shader_parameter("calor", calor)
	humo_calor.emitting = calor > 0.45

	# Respiración del arma + pequeña inclinación siguiendo la tablet (efecto de profundidad)
	var inclina := 0.0
	if gestos.hay_sensor:
		inclina = clampf(gestos.desvio, -30.0, 30.0)
	pivote.position.y = sin(_t * 1.4) * 0.002
	pivote.rotation.z = lerp_angle(pivote.rotation.z, deg_to_rad(sin(_t * 0.9) * 0.4 + inclina * 0.12), delta * 6.0)

	# Temblor de cámara: se reduce solo; se usa al cuadrado para que sea más "golpe"
	_temblor = maxf(_temblor - delta * 3.2, 0.0)
	var k := _temblor * _temblor
	camara.h_offset = (randf() - 0.5) * 0.03 * k
	camara.v_offset = (randf() - 0.5) * 0.03 * k

	if panel_sensores.visible:
		lbl_panel.text = gestos.texto_panel()

	_t_quieto += delta
	if _t_quieto > 30.0:
		_t_quieto = 0.0
		voz.al_esperar()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and not event.echo:
		var k := event as InputEventKey
		if k.keycode == KEY_SPACE:
			gatillo_apretado = k.pressed
			if not k.pressed:
				_clic_vacio_dado = false    # al soltar, el próximo apretón vuelve a hacer clic
		elif k.keycode == KEY_R and k.pressed:
			recargar()


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
func _crear_hud() -> void:
	var capa := CanvasLayer.new()
	add_child(capa)
	var raiz := Control.new()
	raiz.set_anchors_preset(Control.PRESET_FULL_RECT)
	raiz.mouse_filter = Control.MOUSE_FILTER_IGNORE
	capa.add_child(raiz)

	destello = ColorRect.new()
	destello.set_anchors_preset(Control.PRESET_FULL_RECT)
	destello.color = Color(1.0, 0.72, 0.4, 0.0)
	destello.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var suma := CanvasItemMaterial.new()
	suma.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	destello.material = suma
	raiz.add_child(destello)

	# Selector de objetivo (arriba a la izquierda)
	var sel := OptionButton.new()
	for o in EspirituMaquina.OBJETIVOS:
		sel.add_item("OBJETIVO:  " + o)
	sel.position = Vector2(36, 30)
	sel.custom_minimum_size = Vector2(430, 76)
	sel.add_theme_font_size_override("font_size", 30)
	sel.get_popup().add_theme_font_size_override("font_size", 34)
	sel.item_selected.connect(func(i): elegir_objetivo(EspirituMaquina.OBJETIVOS[i]))
	sel.name = "Selector"
	raiz.add_child(sel)

	# Munición (arriba a la derecha)
	var caja := HBoxContainer.new()
	caja.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	caja.position = Vector2(-560, 18)
	caja.custom_minimum_size = Vector2(380, 100)
	caja.alignment = BoxContainer.ALIGNMENT_END
	raiz.add_child(caja)
	lbl_municion = _etiqueta("18", 84, Color(0.85, 0.68, 0.30))
	lbl_total = _etiqueta(" / %d" % MUNICION_MAX, 38, Color(0.6, 0.58, 0.52))
	caja.add_child(lbl_municion)
	caja.add_child(lbl_total)

	btn_voz = Button.new()
	btn_voz.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	btn_voz.position = Vector2(-160, 30)
	btn_voz.custom_minimum_size = Vector2(130, 70)
	btn_voz.add_theme_font_size_override("font_size", 26)
	btn_voz.pressed.connect(func():
		voz.activa = not voz.activa
		if not voz.activa:
			DisplayServer.tts_stop()
		_guardar_ajustes()
		_actualizar_hud())
	raiz.add_child(btn_voz)

	var btn_sens := Button.new()
	btn_sens.text = "SENSORES"
	btn_sens.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	btn_sens.position = Vector2(-160, 112)
	btn_sens.custom_minimum_size = Vector2(130, 50)
	btn_sens.add_theme_font_size_override("font_size", 18)
	btn_sens.pressed.connect(func(): panel_sensores.visible = not panel_sensores.visible)
	raiz.add_child(btn_sens)

	lbl_estado = _etiqueta("", 30, Color(0.95, 0.35, 0.25))
	lbl_estado.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	lbl_estado.position = Vector2(-560, 120)
	lbl_estado.custom_minimum_size = Vector2(380, 40)
	lbl_estado.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	raiz.add_child(lbl_estado)

	# Zonas táctiles
	var gatillo := ZonaTactil.new()
	gatillo.texto = "GATILLO"
	gatillo.subtexto = "mantener = ráfaga"
	gatillo.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	gatillo.position = Vector2(50, -330)
	gatillo.size = Vector2(280, 280)
	gatillo.presionada.connect(func(): gatillo_apretado = true)
	gatillo.soltada.connect(func():
		gatillo_apretado = false
		_clic_vacio_dado = false)
	raiz.add_child(gatillo)

	var zrec := ZonaTactil.new()
	zrec.texto = "RECARGA"
	zrec.subtexto = "o inclina y vuelve"
	zrec.redonda = false
	zrec.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	zrec.position = Vector2(-330, -360)
	zrec.size = Vector2(280, 310)
	zrec.presionada.connect(recargar)
	raiz.add_child(zrec)

	# Subtítulo de la voz
	lbl_voz = _etiqueta("", 34, Color(0.92, 0.88, 0.78))
	lbl_voz.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	lbl_voz.position = Vector2(-500, -110)
	lbl_voz.custom_minimum_size = Vector2(1000, 60)
	lbl_voz.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl_voz.add_theme_color_override("font_outline_color", Color.BLACK)
	lbl_voz.add_theme_constant_override("outline_size", 10)
	raiz.add_child(lbl_voz)

	# Panel de sensores (Fase 0): números en vivo y sensibilidad
	panel_sensores = PanelContainer.new()
	panel_sensores.position = Vector2(36, 130)
	panel_sensores.visible = false
	var v := VBoxContainer.new()
	panel_sensores.add_child(v)
	lbl_panel = _etiqueta("", 20, Color(0.85, 0.9, 1.0))
	v.add_child(lbl_panel)
	v.add_child(_etiqueta("Sensibilidad del disparo (más bajo = más fácil):", 18, Color(0.8, 0.8, 0.8)))
	var deslizador := HSlider.new()
	deslizador.min_value = 7
	deslizador.max_value = 25
	deslizador.step = 0.5
	deslizador.value = gestos.umbral_disparo
	deslizador.custom_minimum_size = Vector2(520, 50)
	deslizador.value_changed.connect(func(x):
		gestos.umbral_disparo = x
		_guardar_ajustes())
	deslizador.name = "Sensibilidad"
	v.add_child(deslizador)
	raiz.add_child(panel_sensores)


func _etiqueta(texto: String, tam: int, color: Color) -> Label:
	var l := Label.new()
	l.text = texto
	l.add_theme_font_size_override("font_size", tam)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _actualizar_hud() -> void:
	lbl_municion.text = str(municion)
	lbl_municion.add_theme_color_override("font_color",
		Color(0.95, 0.3, 0.2) if municion == 0 else Color(0.85, 0.68, 0.30))
	if estado == Estado.RECARGANDO:
		lbl_estado.text = "RECARGANDO…"
	elif municion == 0:
		lbl_estado.text = "¡SIN MUNICIÓN!"
	else:
		lbl_estado.text = ""
	btn_voz.text = "VOZ ●" if voz.activa else "VOZ ○"


func _mostrar_subtitulo(texto: String) -> void:
	lbl_voz.text = "«%s»" % texto
	lbl_voz.modulate.a = 1.0
	if _tw_subtitulo:
		_tw_subtitulo.kill()
	_tw_subtitulo = create_tween()
	_tw_subtitulo.tween_interval(2.6)
	_tw_subtitulo.tween_property(lbl_voz, "modulate:a", 0.0, 0.6)


# ---------------------------------------------------------------------------
# Ajustes guardados en la tablet
# ---------------------------------------------------------------------------
func _cargar_ajustes() -> void:
	var c := ConfigFile.new()
	if c.load(AJUSTES) != OK:
		return
	voz.activa = c.get_value("arma", "voz", true)
	gestos.umbral_disparo = c.get_value("arma", "umbral_disparo", gestos.umbral_disparo)
	objetivo = c.get_value("arma", "objetivo", objetivo)
	var sel := find_child("Selector", true, false) as OptionButton
	if sel:
		sel.select(EspirituMaquina.OBJETIVOS.find(objetivo))
	var d := find_child("Sensibilidad", true, false) as HSlider
	if d:
		d.set_value_no_signal(gestos.umbral_disparo)


func _guardar_ajustes() -> void:
	var c := ConfigFile.new()
	c.set_value("arma", "voz", voz.activa)
	c.set_value("arma", "umbral_disparo", gestos.umbral_disparo)
	c.set_value("arma", "objetivo", objetivo)
	c.save(AJUSTES)


# ---------------------------------------------------------------------------
# Fotos de prueba desde la línea de comandos
# ---------------------------------------------------------------------------
func _leer_argumentos() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--foto="):
			_foto = a.get_slice("=", 1)
		elif a.begins_with("--accion="):
			_accion = a.get_slice("=", 1)
		elif a.begins_with("--tiempo="):
			_t_foto = a.get_slice("=", 1).to_float()


func _preparar_foto() -> void:
	match _accion:
		"disparo":
			_en(_t_foto - 0.02, disparar)
		"humo":
			_en(_t_foto - 0.5, disparar)
			_en(_t_foto - 0.3, disparar)
		"recarga":
			municion = 3
			_en(0.3, recargar)
		"sensores":
			panel_sensores.visible = true
		"caliente":
			for i in 16:
				_en(0.2 + i * 0.14, disparar)
	_en(_t_foto, func():
		var img := get_viewport().get_texture().get_image()
		img.save_png(_foto)
		print("FOTO ", _foto, "  fogonazo escala=", fogonazo.scale, " anim=", anim.current_animation, " t=", anim.current_animation_position)
		get_tree().quit())
