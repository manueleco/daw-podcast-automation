# Project TODO

## In Progress

- Validar el flujo real de bounce sobre un proyecto de Logic con permisos de sistema completos.
- Ajustar la navegacion del cuadro de bounce segun la UI real del equipo.
- Afinar el perfil de salida para episodios con mas canales y casos con musica.

## Todo

- Implementar copia segura de proyectos `.logicx` y proyectos en carpeta.
- Implementar deteccion de proyectos y lotes de episodios.
- Diseñar el mapper de tracks y buses para podcast con mas canales.
- Definir la cadena base de voz, musica y master para el MVP.
- Implementar lectura de configuracion por perfil.
- Añadir reintentos o fallback manual para bounce si la UI no coincide.
- Afinar el launcher GUI con mejor feedback de progreso y errores.
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

## Notas

- Los proyectos originales no se tocan.
- El flujo del MVP parte siempre de una copia de trabajo.
- El ajuste de loudness final se hara sobre bounce y salida, no moviendo ciegamente todos los faders por track.
