# Project TODO

## In Progress

- Validar el flujo real de bounce sobre un proyecto de Logic con permisos de sistema completos.
- Ajustar la navegacion del cuadro de bounce segun la UI real del equipo.
- Afinar el perfil de salida para episodios con mas canales y casos con musica.
- Separar mejor `prepare mix` de `final master` en la app y el CLI.
- Revisar si la ganancia base por archivo de voz esta acercando bien a las voces o necesita otro target.
- Soportar bien proyectos Logic en formato `project folder`, no solo `.logicx` autocontenido.
- Definir la estrategia real de `plugin setup` para stock plugins de Logic en tracks y master.
- Validar la nueva desktop app con ventana propia sobre proyectos reales largos.

## Todo

- Implementar copia segura de proyectos `.logicx` y proyectos en carpeta.
- Implementar deteccion de proyectos y lotes de episodios.
- Diseñar el mapper de tracks y buses para podcast con mas canales.
- Definir la cadena base de voz, musica y master para el MVP.
- Implementar lectura de configuracion por perfil.
- Añadir reintentos o fallback manual para bounce si la UI no coincide.
- Afinar el launcher GUI con mejor feedback de progreso y errores.
- Evaluar automatizacion por fragmentos dentro de una track usando reporte por ventanas y luego traducirlo a automation o region gain.
- Detectar mejor voces cuando los nombres de archivos no ayudan.
- Añadir preflight para permisos de macOS antes del bounce.
- Detectar assets externos y avisar si falta material o si el proyecto vive en cloud storage.
- Integrar VAD para refinar `analyze-track` y no tratar musica/ruido como voz.
- Traducir el reporte de `analyze-track` a puntos de automation de Logic.
- Añadir cancelacion de procesos y barra de progreso mas detallada en la desktop app.
- Añadir presets visuales/instrucciones para episodios largos con muchas tracks.
- Preparar una carpeta de fixtures o episodios dummy para pruebas.
- Añadir tests para discovery, planes de ejecucion y reglas de naming.
- Documentar el setup minimo en macOS para permisos de automatizacion.

## Done

- Repo `daw-podcast-automation` creado.
- Git inicializado.
- Estructura base del proyecto creada.
- CLI inicial en Python montado.
- Targets iniciales de loudness definidos para podcast.
- Documentacion base del MVP creada.
- Archivo interno ignorado por git preparado.
- Runner base para abrir Logic Pro y disparar bounce creado.
- Medicion real con `ffmpeg loudnorm` integrada.
- Correccion automatica de loudness integrada.
- Launcher macOS con dialogs nativos añadido.
- Builder para generar `DAW Podcast Automation.app` añadido.
- Launcher actualizado para correr visible en Terminal.
- Comando `prepare-mix` añadido.
- Primera pasada de ganancia base por archivo de voz antes del bounce añadida.
- Comando `analyze-track` preparado con `librosa` como dependencia opcional.
- Desktop app con ventana propia y logs embebidos añadida.

## Ideas

- Mantener la automatizacion final de LUFS siempre en master, no repartir ese target entre tracks.
- Usar ajuste base por archivo o track de voz para alinear speakers.
- Si luego vamos a automatizacion por fragmentos, hacerlo por ventanas con limites de ganancia y suavizado, no con saltos bruscos.
- Traducir a Logic solo cuando tengamos claro el modelo: `track automation`, `region gain`, o render destructivo sobre la working copy.
- Si los nombres no ayudan, probar deteccion de voz por rasgos del audio y excluir musica/fx por heuristicas antes de tocar ganancia.
- Para lanes tipo la imagen, generar primero puntos candidatos de automation en JSON antes de escribirlos en Logic.
- Cuando implementemos plugins, empezar por cadenas fijas de stock plugins: voz y master, sin intentar configurar todo de una sola vez.

## Notas

- Los proyectos originales no se tocan.
- El flujo del MVP parte siempre de una copia de trabajo.
- El ajuste de loudness final se hara sobre bounce y salida, no moviendo ciegamente todos los faders por track.
- La ganancia base de voz previa al bounce es una primera pasada utilitaria, no mezcla final.
- Algunos proyectos de Logic viven como `project folder` con `Audio Files` fuera del `.logicx`; esos assets tambien hay que clonar.
