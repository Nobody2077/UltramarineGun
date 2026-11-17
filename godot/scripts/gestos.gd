class_name Gestos
extends RefCounted
## Convierte los números del acelerómetro en dos gestos: DISPARO y RECARGA.
##
## La idea clave: el acelerómetro mide la gravedad (9,8 m/s²) + tus movimientos.
## Separamos las dos cosas con un filtro:
##   gravedad = promedio lento de la lectura   (lo que casi no cambia)
##   lineal   = lectura - gravedad             (tus movimientos bruscos)
##
## DISPARO:  un tirón fuerte (lineal grande) -> como el retroceso.
## RECARGA:  inclinar la tablet rápido (la boca del arma hacia abajo o hacia arriba)
##           y volver a la posición normal. Se mide con el ÁNGULO de la gravedad, así
##           funciona aunque la tablet no tenga giroscopio.

signal disparo
signal recarga

var umbral_disparo := 13.0        # m/s² de movimiento brusco para disparar
var umbral_inclinacion := 35.0    # grados que hay que inclinar para recargar
var activo := true

var hay_sensor := false
var gravedad := Vector3.ZERO
var lineal := Vector3.ZERO
var fuerza := 0.0
var pico := 0.0                   # máximo reciente, para ver en el panel
var desvio := 0.0                 # inclinación actual respecto del reposo (grados)
var ultimo_gesto := "-"

var _reposo := 0.0
var _espera_disparo := 0.0
var _inclinado := false
var _t_inclinado := 0.0


func procesar(delta: float) -> void:
	var a := Input.get_accelerometer()
	if a == Vector3.ZERO:
		hay_sensor = false
		return
	hay_sensor = true
	if gravedad == Vector3.ZERO:
		gravedad = a
		_reposo = _angulo(a)

	# Filtro paso bajo: la gravedad sigue a la lectura despacio (4 veces por segundo).
	gravedad = gravedad.lerp(a, clampf(delta * 4.0, 0.0, 1.0))
	lineal = a - gravedad
	fuerza = lineal.length()
	pico = maxf(pico * exp(-delta * 1.5), fuerza)

	# Ángulo de la gravedad en el plano de la pantalla.
	var ang := _angulo(gravedad)
	desvio = wrapf(ang - _reposo, -180.0, 180.0)
	if not _inclinado:
		# el "reposo" se adapta despacio a cómo sostienes la tablet
		_reposo = lerp_angle(deg_to_rad(_reposo), deg_to_rad(ang), clampf(delta * 0.6, 0.0, 1.0))
		_reposo = rad_to_deg(_reposo)
	if not activo:
		return

	# --- RECARGA: inclinar rápido y volver
	if not _inclinado and absf(desvio) > umbral_inclinacion:
		_inclinado = true
		_t_inclinado = 0.0
	elif _inclinado:
		_t_inclinado += delta
		if absf(desvio) < 14.0:
			_inclinado = false
			if _t_inclinado < 2.0:
				ultimo_gesto = "RECARGA (%.1f s)" % _t_inclinado
				recarga.emit()
		elif _t_inclinado > 3.5:
			# lo dejaste inclinado mucho rato: esa es tu nueva posición normal
			_inclinado = false
			_reposo = ang

	# --- DISPARO: tirón brusco (no cuenta mientras estás inclinando para recargar)
	_espera_disparo -= delta
	if fuerza > umbral_disparo and _espera_disparo <= 0.0 and not _inclinado:
		_espera_disparo = 0.22
		ultimo_gesto = "DISPARO (%.1f m/s²)" % fuerza
		disparo.emit()


func _angulo(v: Vector3) -> float:
	return rad_to_deg(atan2(v.x, -v.y))


func texto_panel() -> String:
	if not hay_sensor:
		return "Sin acelerómetro (en el PC es normal).\nUsa ESPACIO para disparar y R para recargar."
	return ("Acelerómetro: (%.1f, %.1f, %.1f)\n" % [gravedad.x + lineal.x, gravedad.y + lineal.y, gravedad.z + lineal.z]
		+ "Movimiento brusco: %.1f m/s²   (pico %.1f, dispara con > %.0f)\n" % [fuerza, pico, umbral_disparo]
		+ "Inclinación: %+.0f°   (recarga con > %.0f° y volver)\n" % [desvio, umbral_inclinacion]
		+ "Último gesto: %s" % ultimo_gesto)
