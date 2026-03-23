# daw-podcast-automation

MVP para automatizar una pasada de postproduccion de podcast sobre proyectos de Logic Pro sin tocar los originales.

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
- analisis por ventanas para detectar tramos problematicos
- automatizacion base para abrir Logic y lanzar bounce
- medicion y correccion de loudness con ffmpeg
- documento de MVP
- tablero de seguimiento en root
- notas internas ignoradas por git

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
- `macos/DAW Podcast Automation.js`: launcher GUI para macOS
- `build-macos-app.command`: builder de la app clickable
- `.internal/`: notas operativas fuera de commit

## Uso rapido

```bash
python3 -m pip install -e .
python3 -m pip install -e '.[analysis]'
daw-podcast-automation scan --root "/ruta/a/proyectos"
daw-podcast-automation profile --name podcast-stereo
daw-podcast-automation plan --source "/ruta/episodio.logicx" --profile podcast-stereo
daw-podcast-automation prepare-mix --source "/ruta/episodio.logicx" --profile podcast-stereo --open-in-logic
daw-podcast-automation analyze-track --input "/ruta/track.wav" --report "/ruta/track-analysis.json"
daw-podcast-automation measure --input "/ruta/bounce.wav" --profile podcast-stereo
daw-podcast-automation correct --input "/ruta/bounce.wav" --output "/ruta/bounce-master.wav" --profile podcast-stereo
daw-podcast-automation final-master --input "/ruta/bounce.wav" --output "/ruta/bounce-master.wav" --profile podcast-stereo
daw-podcast-automation run --source "/ruta/episodio.logicx" --profile podcast-stereo
```

## Launcher macOS

Para generar la app clickable:

```bash
./build-macos-app.command
```

Esto crea `DAW Podcast Automation.app` en el root del repo. Al abrirla:

- eliges el proyecto o carpeta de Logic
- eliges carpeta de salida
- eliges el perfil
- se abre Terminal con el progreso visible del flujo completo

## Permisos

La parte de UI para Logic Pro necesita permisos de `Accessibility` y `Automation` para la app desde la que ejecutes el script.

## Estado del plugin setup

La insercion/configuracion automatica de plugins stock de Logic todavia no esta implementada. El flujo actual prepara ganancia base de voces, hace bounce y corrige el master final.

## Siguiente foco

- validar el bounce real sobre un proyecto de Logic
- ajustar la navegacion del dialogo de bounce segun la UI real
- añadir fallback manual-asistido si la UI cambia
- mejorar la deteccion de voces y el prepare mix por track
- sumar VAD a `analyze-track` para excluir musica y ruido antes de proponer automatizacion
