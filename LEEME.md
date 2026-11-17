# UltramarineGun

Documentación técnica. Simulador de **bólter** (Warhammer 40K, colores Ultramarines: azul y
oro) para una tablet Android de 11" (2560×1600, 16:10) sostenida en horizontal como un arma.
Fan project **sin fines de lucro**. La portada del repo es `README.md`.

Se dispara con un tirón de la tablet o con el pulgar, se recarga inclinándola, y el arma
"habla" (espíritu máquina) con la voz del sistema. La tablet de pruebas no tiene LED: el
fogonazo se muestra en pantalla.

- Créditos de sonidos, texturas y HDRI: `CREDITOS.md`

---

## Estado y pendientes

- **Versión actual: v0.2.0**, pendiente de probar en la tablet real (aspecto, sonido, voz,
  gestos con el panel **SENSORES**, FPS).
- **Refactor:** partir `godot/scripts/principal.gd` (707 líneas, "script dios")
  en partes: el HUD (`_crear_hud`, ~150 líneas), los efectos (humo/chispas) y los ajustes a
  scripts propios. Probar en la tablet después.
- **Pendiente de pulir** (por orden de impacto):
  1. Empuñadura más redondeada/orgánica (hoy es de bloques).
  2. Más contraste de "pincel seco" en el metal: relieves más plateados, huecos casi negros.
  3. Mira delantera y culata un poco más chicas (en la réplica son menores).
  4. Pergamino de pureza con sello de cera roja.
  5. Proyectil bólter con estela de cohete al disparar.
  6. Ideas: casquillos que rebotan con física, distorsión de calor, pantalla de inicio,
     un blanco al que disparar (servocráneo / hereje de cartón).
- **Decisiones de diseño:**
  - Placa **azul** (Ultramarines), no roja como la foto. Sin la punta naranja de réplica.
  - Fan art de 40K (bólter, águila, frases), sin fines de lucro.
  - Una sola arma por ahora (este bólter). Pistola y escopeta, más adelante.
  - Voz = texto a voz de Android (no voz grabada).
  - Sonidos **grabados**, no generados por código.
  - El icono de la app es personal y **no está en el repositorio** (`.gitignore`): al
    clonar, Godot usa su icono por defecto.

---

## Carpetas

| Carpeta / archivo | Qué hay |
|---|---|
| `blender/crear_bolter.py` | Script que construye **todo** el arma desde cero: materiales, modelo, efectos, horneado, animaciones, export y renders. |
| `blender/UltramarineGun.blend` | Resultado del script (se puede abrir y mirar en Blender). |
| `blender/texturas/` | Texturas horneadas (albedo, rugosidad, metal, normales) + texturas del fogonazo. |
| `blender/texturas_descargas/` | Materiales escaneados CC0 de ambientCG (solo se usan los .jpg). |
| `godot/assets/modelos/UltramarineGun.glb` | El arma para Godot (malla + texturas + animaciones). El script la exporta directo ahí. |
| `audio/mezclar_sonidos.sh` | Mezcla los sonidos finales desde grabaciones. |
| `audio/descargas/`, `audio/final/` | Grabaciones originales / sonidos mezclados. |
| `godot/` | El juego (Godot 4.7.2). |
| `renders/` | Vistas previas de Blender; `renders/godot/` capturas del juego. |
| `referencias/` | Fotos de referencia con derechos de terceros (**no se versionan**). `bolter_foto_2.jpg` es la que se usó para medir. |

---

## 1. El modelo (Blender 4.5)

```
cd UltramarineGun
<ruta a Blender 4.5>\blender.exe --background --factory-startup --python blender/crear_bolter.py
```
Tarda ~3 min (casi todo es el horneado). Con la variable `UG_MUESTRAS=8` va rápido para pruebas
(texturas con más ruido). El `.glb` se exporta directo a `godot/assets/modelos/` (antes iba a
`exportado/` y había que copiarlo: eran dos copias de 13 MB que podían desincronizarse).

**Ejes:** X = hacia la boca, Z = arriba, Y = grosor (el lado −Y es el que ve la cámara).
Las medidas del script están en **cm**. Medidas tomadas de `referencias/bolter_foto_2.jpg`
a razón de **~0,081 cm por píxel** (arma de ~80 cm).

### Cómo está hecho
- **Modelado por perfiles:** cada pieza es su silueta lateral (`prisma`) extruida en grosor.
- **Booleanos:** el ánima y el puerto lateral de la bocacha son cortes con cilindros.
- **Bisel** en todos los cantos (sin bisel parece plástico). Bisel grande = bordes redondeados
  (guardamanos, anillos de la empuñadura).
- **Cargador curvo:** se genera desde una línea central `centro(t)`; el ancho se aplica
  perpendicular a la curva.
- **Águila bicéfala** (`aquila()`): relieve por capas, en "unidades de águila" escaladas a cm:
  12 plumas largas superpuestas, coberteras, banda del ala, cabezas con pico ganchudo,
  pecho en dos niveles y cola en abanico. El ala izquierda es la derecha en espejo.
- **Empuñadura:** sobre un eje inclinado, con 3 anillos (más salientes adelante) y talón.

### Materiales y texturas
`material_capas()` mezcla, por material:
1. **Foto escaneada** (ambientCG, CC0) proyectada en **caja/triplanar** y **teñida**
   (tinte calculado con el color promedio de cada foto).
2. **Desgaste en cantos** (nodo Bevel vs normal real) + rayones finos + **astillas reales**
   (mapa de metalicidad de PaintedMetal004 en la pintura azul).
3. **Suciedad** en rincones (nodo AO) + **mugre escaneada** (SurfaceImperfections017).
4. **Relieve**: metal martillado + pintura saltada + relieve de la foto → nodo Bump.

| Material | Foto | Notas |
|---|---|---|
| Metal_gastado | Metal038 (tinte ×1,95/1,8/1,72) | acero plateado; cantos Metal054A ×1,3 |
| Pintura_ultramar | PaintedMetal004 (sin su color) | azul propio; astillas y relieve de la foto |
| Oro_aquila | Metal048A (tinte 0,92/0,76/0,48) | oro viejo |
| Empunadura | Metal038 (×1,25) | más mate |
| Interior_oscuro | — | ánima, ranuras |

**Horneado:** Godot no entiende los nodos de Blender, así que cada pieza se "fotografía" en 4
PNG: albedo, rugosidad, metal (vía emisión) y **normales** (bake NORMAL). Tamaños: Cuerpo 2048,
Cargador 1024, Palanca 512, Gatillo 256.

### Piezas del .glb
- `UltramarineGun` (raíz, pivote en la empuñadura) → recibe el retroceso.
- `Cuerpo` (fijo), `Cargador`, `Palanca` (cuña del cerrojo), `Gatillo`.
- `Fogonazo` y `Casquillo`: en reposo con escala **0,0001** (ocultos; ver trampas).
- ~17–20 mil triángulos.

### Animaciones (60 fps, una pista NLA por animación; el exportador las junta por nombre)
| Nombre | Duración | Qué pasa |
|---|---|---|
| `Disparo` | 0,25 s | gatillo, retroceso hacia arriba, cerrojo atrás/adelante, casquillo volando |
| `Recarga` | 1,8 s | el arma se inclina, cae el cargador (f16–36), entra uno nuevo (encaja f60), palanca atrás (f72–88) |
| `Gatillo_vacio` | 0,17 s | clic sin munición |

---

## 2. Sonidos

`bash audio/mezclar_sonidos.sh` (Git Bash) arma `audio/final/*.wav` con ffmpeg:
- **Disparo** = 3 capas: estallido de fusil real (Mosin / SKS / CZ) + lanzacohetes (los
  proyectiles del bólter son mini cohetes) + explosión lejana filtrada y retrasada 110 ms;
  graves +7 dB a 70 Hz, compresor y limitador. 3 variantes.
- **Mecánica** (cargador fuera/dentro, palanca, gatillo vacío): grabaciones reales bajadas de
  tono ×0,86 para que suenen a arma grande.

---

## 3. El juego (`godot/`, Godot 4.7.2, renderer Compatibility)

| Archivo | Qué hace |
|---|---|
| `scripts/principal.gd` | Escena completa: entorno + HDRI, arma, efectos, sonido, HUD, máquina de estados (LISTO / RECARGANDO), calor del cañón, ajustes guardados. |
| `scripts/gestos.gd` | Acelerómetro → DISPARO (tirón > `umbral_disparo` m/s²) y RECARGA (inclinar > 35° y volver en < 2 s). Funciona sin giroscopio. |
| `scripts/espiritu_maquina.gd` | Frases por objetivo (HEREJE, XENO, TRAIDOR, DEMONIO) y voz TTS (tono 0,55). Habla 1 de cada 4 disparos. |
| `scripts/zona_tactil.gd` | Zonas GATILLO (mantener = ráfaga) y RECARGA, multitáctiles. |
| `shaders/fogonazo.gdshader` | Fogonazo aditivo con forma distinta en cada disparo (semilla). |
| `shaders/calor.gdshader` | Halo rojo→naranja de la bocacha caliente (fresnel). |
| `assets/hdri/machine_shop_02_1k.hdr` | HDRI de taller (Poly Haven) para los reflejos del metal. |
| `icono/icono.png` | Icono (meme). **No se versiona.** |

**Un disparo** = fogonazo (controlado por código, ~3 fotogramas, tamaño y giro al azar) + luz
naranja 90 ms + chispas + humo que queda en el aire + casquillo + destello de pantalla (en lugar
del LED) + temblor de cámara + vibración + 1 de 3 sonidos con tono al azar.
**Calor:** +0,065 por disparo, se enfría a los 0,5 s; > 0,45 sale humo de calor; > 0,85 frase.

Ajustes guardados en la tablet (`user://ajustes.cfg`): voz on/off, sensibilidad, objetivo.

```
cd UltramarineGun\godot
$g = "<ruta a Godot 4.7.2>\Godot_v4.7.2-stable_win64_console.exe"
& $g --headless --path . --import
& $g --path . --resolution 1600x1000 -- --foto=foto.png --accion=disparo --tiempo=1.8
#   acciones de prueba: reposo | disparo | humo | recarga | sensores | caliente
& $g --headless --path . --export-debug "Android" exportaciones/ultramarine_gun.apk
$a = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $a push exportaciones/ultramarine_gun.apk /sdcard/Download/ultramarine_gun.apk
& $a shell ls -la /sdcard/Download/ultramarine_gun.apk     # comparar el tamaño con el del PC
```
En el PC: ESPACIO = disparar (mantener = ráfaga), R = recargar. Al cambiar de versión, subir
`version/code` en `export_presets.cfg` y `config/version` en `project.godot`.

---

## 4. Trampas encontradas (cada una costó tiempo)

1. **Escala 0 rompe Godot:** un nodo con escala 0 da «Basis must be normalized» y no se puede
   rotar. Se usa `OCULTO = 0.0001`.
2. **El fogonazo por animación no se veía:** con interpolación constante aparecía recién en el
   fotograma 1. Ahora lo maneja el código y se quita su pista de `Disparo` al cargar.
3. **Luces del render demasiado fuertes** (260 W) "quemaban" los colores: parecía un fallo del
   horneado y no lo era. Revisar los mapas horneados antes de culpar a las texturas.
4. **Unir objetos en Blender** conserva solo los modificadores del activo: aplicar los biseles
   antes de `join`.
5. **Vista previa con pistas NLA silenciadas** se queda con la pose del render anterior: volver
   al fotograma 0 con todas las pistas activas antes de aislar una.
6. **BOM en `export_presets.cfg`** → Godot no exporta. Editar con Edit/Write o `sed`, nunca con
   `Set-Content -Encoding utf8` de PowerShell 5. Verificar la hora del APK después de exportar.
7. **adb desde Git Bash:** usar `MSYS_NO_PATHCONV=1`; para `adb install` pasar la ruta estilo
   `C:/...`. En tablets Xiaomi, `adb install` da `INSTALL_FAILED_USER_RESTRICTED` si nadie acepta el
   aviso en pantalla → instalar desde Descargas.
8. **OpenGameArt bloquea al lector web** (403): bajar con `curl -A "Mozilla/5.0"`.
9. **ffmpeg `drawtext`** se cae en Windows si falta fontconfig: armar hojas de contacto sin texto.

---

## 5. Historial

- **2026-11-16, sesión 1** (todo en una tarde/noche):
  idea y bocetos → modelo por script en Blender → cargador curvo y grueso como la foto →
  sonidos grabados mezclados en capas → juego Godot v0.1.0 (fogonazo, humo, chispas, luz, voz,
  HUD, gestos, panel de sensores) → icono y cañón que se calienta → texturas escaneadas
  (ambientCG) → águila bicéfala nueva → caja del gatillo + HDRI → **v0.2.0**: formas medidas
  sobre la foto (acero plateado, palanca en cuña, empuñadura con anillos, guardamanos con
  costillas, miras, culata, tornillo, botón con estrías, bloque bajo la bocacha, cargador más
  corto).
- **2026-11-17, sesión 2:** limpieza del repositorio y publicación en GitHub (el `.glb` se
  exporta directo a Godot; solo se versionan las grabaciones que se usan).
