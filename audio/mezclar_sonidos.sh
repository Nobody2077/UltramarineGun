#!/usr/bin/env bash
# Mezcla los sonidos del bólter a partir de GRABACIONES reales (carpeta descargas/).
# Ejecutar desde Git Bash:  bash audio/mezclar_sonidos.sh
#
# Diseño de sonido por capas (así se hacen los disparos de los juegos):
#   1) estallido  -> disparo real de fusil (Mosin / SKS / CZ)
#   2) cohete     -> lanzacohetes: los proyectiles del bólter son mini cohetes
#   3) cola       -> explosión lejana, con filtro de graves y un retraso de 110 ms
# + realce de graves (70 Hz), compresión y limitador para que pegue fuerte sin saturar.
set -e
FF="${FFMPEG:-ffmpeg}"
# Si ffmpeg no está en el PATH, se busca el instalado con WinGet (sin rutas de usuario fijas).
command -v "$FF" >/dev/null || FF=$(ls "$(cygpath "$LOCALAPPDATA")"/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe 2>/dev/null | head -1)
[ -n "$FF" ] || { echo "No encuentro ffmpeg: instálalo o define FFMPEG=/ruta/a/ffmpeg"; exit 1; }
cd "$(dirname "$0")"
D=descargas
G=$D/gunshot_sounds/extraido/sounds
Q=$D/q009/extraido/q009
R=$D/gun_reload
mkdir -p final

disparo () {   # $1 salida  $2 archivo estallido  $3 inicio(s)  $4 cohete
  "$FF" -y -hide_banner -loglevel error \
    -i "$2" -i "$4" -i "$Q/explosion.ogg" -filter_complex "
    [0]atrim=start=$3:duration=1.3,asetpts=PTS-STARTPTS,aresample=44100,pan=stereo|c0=c0|c1=c0,volume=2.2[a];
    [1]aresample=44100,volume=0.55,adelay=15|15[b];
    [2]aresample=44100,lowpass=f=900,volume=0.5,adelay=110|110[c];
    [a][b][c]amix=inputs=3:normalize=0,
      equalizer=f=70:t=q:w=1.2:g=7,equalizer=f=3500:t=q:w=1:g=2,
      acompressor=threshold=0.18:ratio=4:attack=2:release=120:makeup=1.6,
      atrim=duration=1.4,afade=t=out:st=0.8:d=0.6,alimiter=limit=0.89" \
    -ar 44100 -c:a pcm_s16le "final/$1"
  echo "  final/$1"
}

echo "Disparos:"
disparo bolter_disparo_1.wav "$G/mosin.wav" 3.50 "$Q/rlauncher.ogg"
disparo bolter_disparo_2.wav "$G/sks.wav"   7.65 "$Q/rlauncher2.ogg"
disparo bolter_disparo_3.wav "$G/cz.wav"    2.75 "$Q/rlauncher3.ogg"

# Mecánica: un poco más grave (asetrate 0.86) para que suene a arma GRANDE.
mecanico () {  # $1 salida  $2 entrada  $3 inicio  $4 duración  $5 volumen
  "$FF" -y -hide_banner -loglevel error -i "$2" -af "
    atrim=start=$3:duration=$4,asetpts=PTS-STARTPTS,aresample=44100,
    asetrate=44100*0.86,aresample=44100,equalizer=f=150:t=q:w=1:g=4,volume=$5,
    afade=t=in:d=0.005,afade=t=out:st=$(awk "BEGIN{print $4/0.86-0.06}"):d=0.06,alimiter=limit=0.89" \
    -ac 2 -c:a pcm_s16le "final/$1"
  echo "  final/$1"
}
echo "Mecánica:"
mecanico cargador_fuera.wav  "$R/assaultriflereload1_0.wav" 0.16 0.55 2.5
mecanico cargador_dentro.wav "$R/assaultriflereload1_0.wav" 0.97 0.30 1.0
mecanico palanca.wav         "$R/shotguncock_0.wav"         0.08 0.40 0.9
mecanico gatillo_vacio.wav   "$Q/outofammo.ogg"             0.10 0.13 1.0
echo "LISTO"
