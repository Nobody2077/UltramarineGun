class_name ZonaTactil
extends Control
## Zona de la pantalla que se aprieta con el pulgar (GATILLO o RECARGA).
## Usa toques de pantalla (InputEventScreenTouch) y recuerda QUÉ dedo la apretó,
## así funciona aunque tengas otro dedo en otra zona al mismo tiempo (multitáctil).

signal presionada
signal soltada

@export var texto := "GATILLO"
@export var subtexto := ""
@export var redonda := true

var apretada := false
var _dedo := -1
const ORO := Color(0.79, 0.64, 0.29)


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed and _dedo == -1 and get_global_rect().has_point(t.position):
			_dedo = t.index
			apretada = true
			presionada.emit()
			queue_redraw()
		elif not t.pressed and t.index == _dedo:
			_dedo = -1
			apretada = false
			soltada.emit()
			queue_redraw()


func _draw() -> void:
	var r := Rect2(Vector2.ZERO, size)
	var relleno := Color(ORO, 0.28 if apretada else 0.07)
	var borde := Color(ORO, 0.95 if apretada else 0.55)
	if redonda:
		var c := size / 2.0
		var radio := minf(size.x, size.y) / 2.0 - 3.0
		draw_circle(c, radio, relleno)
		draw_arc(c, radio, 0, TAU, 64, borde, 4.0, true)
	else:
		draw_rect(r.grow(-3), relleno)
		draw_rect(r.grow(-3), borde, false, 4.0)
	var f := get_theme_default_font()
	var y := size.y / 2.0 + 6.0
	draw_string(f, Vector2(0, y), texto, HORIZONTAL_ALIGNMENT_CENTER, size.x, 30, borde)
	if subtexto != "":
		draw_string(f, Vector2(0, y + 32), subtexto, HORIZONTAL_ALIGNMENT_CENTER, size.x, 18, Color(0.75, 0.72, 0.65, 0.8))
