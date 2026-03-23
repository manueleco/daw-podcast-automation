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
- Afinar la UI nueva de `Logic Podcast Automation` con feedback de progreso mas granular si hace falta.
- Probar Essentia por instalacion manual en macOS y compararlo con el analisis actual sobre episodios reales.
- Decidir si Essentia queda solo como capa de QC/envelope o si reemplaza una parte concreta del backend actual.

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
- Evaluar marcadores por tipo de contenido (`Dialogo`, `Musica`) a partir del analisis y guardarlos en JSON para luego llevarlos a Logic.
- Definir una estrategia de loudness por capas: `short-term` para nivelado local de speech y `integrated` para cierre final del episodio.
- Escribir markers y automation draft dentro de Logic Pro a partir del JSON consolidado.
- Resolver el posicionamiento exacto de markers por tiempo en Logic Pro desde `Go To Position` o una ruta equivalente accesible.
- Añadir cancelacion de procesos y barra de progreso mas detallada en la desktop app.
- Añadir presets visuales/instrucciones para episodios largos con muchas tracks.
- Preparar una carpeta de fixtures o episodios dummy para pruebas.
- Añadir tests para discovery, planes de ejecucion y reglas de naming.
- Documentar el setup minimo en macOS para permisos de automatizacion.
- Evaluar una vista de resumen final con accesos al bounce, master corregido y reportes JSON.
- Si Essentia termina siendo viable, aislar solo lo que aporta valor real: `envelope`, `EBU short-term` y QC.
- Si Essentia sigue siendo fragil en macOS, mantener `librosa + ffmpeg` como base y usar Essentia solo en entornos preparados.

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
- Builder para generar la app macOS clickable anadido.
- Launcher actualizado para correr visible en Terminal.
- Comando `prepare-mix` añadido.
- Primera pasada de ganancia base por archivo de voz antes del bounce añadida.
- Comando `analyze-track` preparado con `librosa` como dependencia opcional.
- Desktop app con ventana propia y logs embebidos añadida.
- UI renovada con look mas musical y nombre visible `Logic Podcast Automation`.
- Launcher y bundle macOS renombrados a `Logic Podcast Automation.app`.
- UI rehecha con layout mas limpio tipo app macOS y sin tipografia cursiva.
- `Analyze track` ampliado con RMS, short-term loudness, clasificacion heuristica, segmentos, marcadores y automation draft en JSON.
- Logs persistentes anadidos en `runtime-logs/` para general, errores y sesiones.
- Marker List validado en Logic Pro real: abrir lista, crear marker y renombrarlo por Accessibility.
- Capa opcional `essentia_analyze.py` añadida para research de `RMS + envelope + EBU short-term + QC`.
- Comando de comparacion entre backends anadido para contrastar el analisis actual con la ruta Essentia.

## Ideas

- Mantener la automatizacion final de LUFS siempre en master, no repartir ese target entre tracks.
- Usar ajuste base por archivo o track de voz para alinear speakers.
- Si luego vamos a automatizacion por fragmentos, hacerlo por ventanas con limites de ganancia y suavizado, no con saltos bruscos.
- Traducir a Logic solo cuando tengamos claro el modelo: `track automation`, `region gain`, o render destructivo sobre la working copy.
- Si los nombres no ayudan, probar deteccion de voz por rasgos del audio y excluir musica/fx por heuristicas antes de tocar ganancia.
- Para lanes tipo la imagen, generar primero puntos candidatos de automation en JSON antes de escribirlos en Logic.
- Cuando implementemos plugins, empezar por cadenas fijas de stock plugins: voz y master, sin intentar configurar todo de una sola vez.
- Mantener el branding de la app separado del nombre tecnico del repo para poder iterar sin tocar el paquete Python.
- Si distinguimos speech y musica, usar objetivos distintos por segmento y no una sola regla de ganancia para todo el track.
- Si Essentia entra, usarlo como backend secundario para validar envelope/QC, no como dependencia critica del MVP mientras la instalacion siga siendo friccionada.

## Notas

- Los proyectos originales no se tocan.
- El flujo del MVP parte siempre de una copia de trabajo.
- El ajuste de loudness final se hara sobre bounce y salida, no moviendo ciegamente todos los faders por track.
- La ganancia base de voz previa al bounce es una primera pasada utilitaria, no mezcla final.
- Algunos proyectos de Logic viven como `project folder` con `Audio Files` fuera del `.logicx`; esos assets tambien hay que clonar.
- El intento de instalar `essentia` por `pip` en este Mac fallo por build nativo y dependencias del toolchain, asi que por ahora no debe asumirse disponible.
