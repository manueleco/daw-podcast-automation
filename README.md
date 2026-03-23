# daw-podcast-automation

MVP para automatizar una pasada de postproduccion de podcast sobre proyectos de Logic Pro sin tocar los originales.

La app de escritorio se presenta como `Logic Podcast Automation`.

La idea base del repo es esta:

- detectar proyectos de Logic
- crear una copia de trabajo
- alinear voces por archivo antes del bounce cuando los nombres lo permiten
- abrir el proyecto en Logic y generar un bounce
- medir loudness del bounce
- corregir nivel final para dejar el episodio listo para distribucion

## Estado actual

Ya esta montada la base del proyecto:

- repo inicial
- CLI en Python
- perfiles iniciales de podcast
- prepare mix base para audios de voz
- analisis por ventanas con RMS, short-term loudness y clasificacion heuristica
- capa opcional de research con Essentia para envelope, QC y contraste de EBU short-term
- automatizacion base para abrir Logic y lanzar bounce
- medicion y correccion de loudness con ffmpeg
- documento de MVP
- tablero de seguimiento en root
- notas internas ignoradas por git
- desktop app con layout tipo app macOS y logs embebidos
- logs persistentes en `runtime-logs/`

## Alcance del MVP

En esta primera etapa vamos a resolver el flujo y las decisiones tecnicas antes de meternos de lleno con la automatizacion completa de Logic Pro.

Objetivo del MVP:

- no modificar los `.logicx` o paquetes originales
- trabajar siempre sobre una copia
- dejar una salida coherente para podcast y streaming
- preparar una capa de automatizacion compatible con Logic Pro

Fuera de alcance por ahora:

- editar internamente archivos del proyecto de Logic
- mezclar cada track con criterio creativo variable
- UI final de macOS

## Targets iniciales

- `podcast-stereo`: `-16 LUFS`, `<= -1 dBTP`, `48 kHz`
- `podcast-mono`: `-19 LUFS`, `<= -1 dBTP`, `48 kHz`

## Estructura

- `PROJECT_TODO.md`: tablero principal del proyecto
- `docs/logic-pro-mvp.md`: definicion del MVP
- `config/podcast-default.yaml`: ejemplo de configuracion
- `src/daw_podcast_automation/`: codigo base del CLI
- `macos/Logic Podcast Automation.js`: launcher GUI para macOS
- `src/daw_podcast_automation/gui.py`: app de escritorio con ventana propia
- `src/daw_podcast_automation/gui_assets/`: interfaz y estilos de la app
- `build-macos-app.command`: builder de la app clickable
- `runtime-logs/`: logs generales, errores y sesiones
- `.internal/`: notas operativas fuera de commit

## Uso rapido

```bash
python3 -m pip install -e .
python3 -m pip install -e '.[analysis]'
daw-podcast-automation scan --root "/ruta/a/proyectos"
daw-podcast-automation profile --name podcast-stereo
daw-podcast-automation plan --source "/ruta/episodio.logicx" --profile podcast-stereo
daw-podcast-automation prepare-mix --source "/ruta/episodio.logicx" --profile podcast-stereo --open-in-logic
daw-podcast-automation analyze-track --input "/ruta/track.wav" --report "/ruta/track-analysis.json" --profile podcast-stereo
daw-podcast-automation essentia-analyze-track --input "/ruta/track.wav" --report "/ruta/track-essentia.json" --profile podcast-stereo
daw-podcast-automation compare-analysis-backends --input "/ruta/track.wav" --comparison-report "/ruta/track-compare.json" --profile podcast-stereo
daw-podcast-automation measure --input "/ruta/bounce.wav" --profile podcast-stereo
daw-podcast-automation correct --input "/ruta/bounce.wav" --output "/ruta/bounce-master.wav" --profile podcast-stereo
daw-podcast-automation final-master --input "/ruta/bounce.wav" --output "/ruta/bounce-master.wav" --profile podcast-stereo
daw-podcast-automation logic-marker-list --source "/ruta/episodio.logicx"
daw-podcast-automation logic-marker-create --source "/ruta/episodio.logicx" --name "Dialogo Intro"
daw-podcast-automation run --source "/ruta/episodio.logicx" --profile podcast-stereo
```

## Launcher macOS

Para generar la app clickable:

```bash
./build-macos-app.command
```

Esto crea `Logic Podcast Automation.app` en el root del repo. Al abrirla:

- abre una ventana propia de escritorio
- permite lanzar `Full run` o `Prepare mix`
- permite correr `Analyze track`
- muestra logs y estado del proceso dentro de la app
- usa el mismo perfil para los targets de analisis y master
- deja rastro en `runtime-logs/` para depurar errores luego

## Permisos

La parte de UI para Logic Pro necesita permisos de `Accessibility` y `Automation` para la app desde la que ejecutes el script.

## Estado del plugin setup

La insercion/configuracion automatica de plugins stock de Logic todavia no esta implementada. El flujo actual prepara ganancia base de voces, hace bounce y corrige el master final.

## Estado de track analysis

`Analyze track` ahora genera un JSON con:

- ventanas con `RMS`, `momentary` y `short-term loudness`
- clasificacion heuristica `speech`, `music` u `other`
- segmentos consolidados
- marcadores tipo `Dialogo` y `Musica`
- borrador de automation de volumen para futura traduccion a Logic

La escritura directa de esos puntos y marcadores dentro de Logic sigue pendiente.

## Estado de Essentia

Se anadio una capa opcional `essentia_analyze.py` para explorar:

- `RMS` por ventanas
- `envelope`
- `EBU short-term / integrated / LRA`
- chequeos de QC como `true peak`, clipping potencial y offset DC

Tambien hay un comando `compare-analysis-backends` para contrastar ese backend contra el analisis actual.

Decision provisional:

- mantener `librosa + ffmpeg` como backend principal
- dejar Essentia como backend secundario de research y QC

Motivo:

- el backend actual ya cubre clasificacion, segmentos, marcadores y automation draft
- Essentia aporta cosas buenas, pero en este Mac fallo la instalacion por build nativo y dependencias de toolchain
- no conviene volverlo ruta critica del MVP hasta validarlo sobre episodios reales y un setup estable

## Estado de marker automation

Ya esta resuelto este tramo:

- abrir `Marker List`
- crear marker en el playhead actual
- renombrar marker por Accessibility

Lo que sigue pendiente es el posicionamiento exacto por tiempo desde JSON y luego la traduccion de `automation_draft` a la lane de `Volume`.

## Logs

Cuando corras la app o el CLI quedan trazas en:

- `runtime-logs/general.log`
- `runtime-logs/errors.log`
- `runtime-logs/sessions/`

## Sesiones largas

Tracks de mas de 1 hora y proyectos con 4 a 10 tracks son un caso valido para esta arquitectura. El analisis y el bounce son procesos offline y lineales, asi que tardaran, pero no dependen de tener clips cortos.

## Siguiente foco

- validar el bounce real sobre un proyecto de Logic
- ajustar la navegacion del dialogo de bounce segun la UI real
- añadir fallback manual-asistido si la UI cambia
- mejorar la deteccion de voces y el prepare mix por track
- sumar VAD a `analyze-track` para excluir musica y ruido antes de proponer automatizacion
