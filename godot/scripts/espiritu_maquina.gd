class_name EspirituMaquina
extends RefCounted
## La voz del arma. Usa el "texto a voz" (TTS) del propio Android, en español,
## con el tono bajado para que suene grave, como un marine.

signal dijo(texto: String)

const OBJETIVOS := ["HEREJE", "XENO", "TRAIDOR", "DEMONIO"]

const FRASES := {
	"fijar": {
		"HEREJE": ["Hereje localizado. Que el Emperador lo juzgue; yo lo ejecuto."],
		"XENO": ["Xeno detectado. Sin piedad."],
		"TRAIDOR": ["Traidor marcado. Diez mil años de traición terminan hoy."],
		"DEMONIO": ["Disformidad detectada. Que la fe sea tu armadura."],
	},
	"disparo": {
		"HEREJE": ["¡Muere, hereje, muere!", "¡Quema, hereje!", "La herejía se paga con plomo bendito."],
		"XENO": ["¡Purgad al xeno!", "¡Ningún xeno vivirá!"],
		"TRAIDOR": ["¡Muere, traidor!", "¡Por los diez mil años de traición!"],
		"DEMONIO": ["¡Vuelve a la disformidad!", "¡El Emperador protege!"],
	},
	"general": ["¡Por el Emperador!", "¡Por Macragge!", "¡Valor y honor!"],
	"vacio": ["Munición agotada, hermano. Recarga."],
	"recargado": ["Proyectiles benditos en la recámara.", "El espíritu máquina está satisfecho."],
	"espera": ["Conoce el miedo… y no lo sientas.", "Espero tu orden, hermano."],
	"calor": ["El cañón arde, hermano. Mi furia también.", "Calor en el cañón. El espíritu máquina está despierto."],
}

var activa := true
var _voz := ""
var _ultima := ""


func iniciar() -> void:
	var voces := DisplayServer.tts_get_voices_for_language("es")
	if voces.is_empty():
		voces = DisplayServer.tts_get_voices_for_language("spa")
	if not voces.is_empty():
		_voz = voces[0]


func decir(texto: String, interrumpir := false) -> void:
	if not activa:
		return
	if not interrumpir and DisplayServer.tts_is_speaking():
		return
	dijo.emit(texto)
	if _voz != "":
		# volumen 100, tono 0.55 (grave), velocidad 0.92
		DisplayServer.tts_speak(texto, _voz, 100, 0.55, 0.92, 0, interrumpir)


func _elegir(lista: Array) -> String:
	if lista.size() == 1:
		return lista[0]
	var f: String = lista.pick_random()
	while f == _ultima:
		f = lista.pick_random()
	_ultima = f
	return f


func al_fijar(objetivo: String) -> void:
	decir(_elegir(FRASES["fijar"][objetivo]), true)


func al_disparar(objetivo: String) -> void:
	# No habla en cada tiro (sería agotador): 1 de cada 4, y nunca encima de otra frase.
	if randf() > 0.25:
		return
	var lista: Array = FRASES["disparo"][objetivo] if randf() < 0.7 else FRASES["general"]
	decir(_elegir(lista))


func al_vaciar() -> void:
	decir(_elegir(FRASES["vacio"]), true)


func al_recargar() -> void:
	if randf() < 0.6:
		decir(_elegir(FRASES["recargado"]))


func al_calentar() -> void:
	decir(_elegir(FRASES["calor"]), true)


func al_esperar() -> void:
	decir(_elegir(FRASES["espera"]))
