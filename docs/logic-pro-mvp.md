# Logic Pro MVP

## Objetivo

Construir un flujo repetible para preparar episodios de podcast en Logic Pro con una salida lista para distribucion, manteniendo los proyectos originales intactos.

## Enfoque

El MVP no va a editar el formato interno de Logic. Va a trabajar por fuera:

1. descubrir proyecto
2. crear copia de trabajo
3. abrir la copia en Logic Pro
4. aplicar perfil base de podcast
5. hacer bounce temporal
6. medir `Integrated LUFS` y `True Peak`
7. corregir salida
8. generar export final

## Por que asi

- es mas estable que tocar `.logicx` por dentro
- sirve aunque cambie el numero de canales entre episodios
- deja margen para automatizar mas sin rehacer el flujo

## Perfil base de podcast

El perfil inicial del MVP asume un podcast de voz hablada con posibilidad de musica o stingers.

Bloques del perfil:

- `voice bus`: control de dinamica y claridad
- `music bus`: nivel contenido y ducking si hace falta
- `master`: medicion de loudness y control final de pico

Targets de salida:

- `podcast-stereo`: `-16 LUFS`, `<= -1 dBTP`
- `podcast-mono`: `-19 LUFS`, `<= -1 dBTP`

## Fases

### Fase 1

CLI para:

- descubrir proyectos
- definir planes de trabajo
- generar nombres de copia
- validar perfil de salida

### Fase 2

Runner real para:

- duplicar proyecto
- lanzar Logic Pro
- abrir copia de trabajo
- disparar bounce automatizado

### Fase 3

Motor de medicion y ajuste:

- medir loudness sobre bounce
- calcular correccion
- generar un master corregido

## Dudas abiertas

- Mejor punto de insercion para la correccion final dentro de Logic.
- Cuanto del flujo inicial merece ser manual-asistido para validar antes de automatizar del todo.
- Convencion de nombres para detectar voces, musica y FX cuando cambian los canales entre temporadas.
- Como responde el dialogo de bounce real de Logic en este equipo con permisos completos.
