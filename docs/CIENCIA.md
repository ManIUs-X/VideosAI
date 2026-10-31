# Base científica — Ep. 01 «La luz que acelera» (beep-speed illusion)

## Fuente principal (leída en texto completo)

Merz, S., Sommerfeld, J., Frings, C., & Meyerhoff, H. S. (2026). *Not proportional after all: Investigating speed perception with the beep-speed illusion.* Attention, Perception, & Psychophysics, 88(2). https://doi.org/10.3758/s13414-025-03211-6. Es de acceso abierto (PMC12795862); el texto completo se obtuvo de Europe PMC.

Antecedente: Meyerhoff, H. S., Gehrer, N. A., Merz, S., & Frings, C. (2022). *The beep-speed illusion: Non-spatial tones increase perceived speed of visual objects in a forced-choice paradigm.* Cognition, 219, 104978. Es el paradigma original, con movimiento lineal. No consulté el texto completo de este artículo; lo cito tal como lo cita Merz et al.

## Qué es la ilusión

Un objeto que se mueve en línea recta o en círculo se percibe **más rápido** si sus cambios de dirección coinciden con un sonido breve, en comparación con un objeto puramente visual de la misma velocidad física. El sonido no es espacial: llega igual por ambos canales.

## Parámetros del paradigma (Merz et al., 2026, Exp. 1 y 2) y cómo se implementan

| Parámetro | Artículo | Implementación (`pudulab/illusions/beep_speed.py`) |
|---|---|---|
| Estímulos | 2 puntos blancos sobre fondo gris, trayectorias circulares invisibles | 2 luces cálidas idénticas sobre un bosque nocturno, con trayectorias circulares invisibles |
| Radio | 0,1 × altura de pantalla | **0,07 × altura** (formato 9:16; ver desviaciones) |
| Centros | ±0,2 × altura del centro | **±0,13 × altura**, desplazados +0,06 hacia arriba |
| Diámetro | 0,0125 × altura | núcleo de 0,015 × altura + halo gaussiano de luminancia constante |
| Velocidad AV | 0,25 rps (Exp. 2: también 1/24 y 1,5 rps) | 0,25 rps |
| Velocidad V | razón 0,2 – 1,8 respecto de AV | razón **1,0** en el corto (velocidad física idéntica); parametrizable |
| Duración | 3 s | 3 s |
| Cambios de dirección | 1 por cada intervalo de 1000 ms, nunca en los primeros ni en los últimos 100 ms | idéntico, cuantizado a frames de 60 fps |
| Separación AV–V | ≥ 200 ms | ≥ 200 ms (verificado para cada ensayo) |
| Beep | seno de 440 Hz, 68 ms, simultáneo con cada cambio de dirección AV | idéntico, más rampas coseno de 5 ms (añadidas para evitar clics) |
| Control | — (el objeto V es el control interno) | (a) objeto V dentro de cada ensayo; (b) **MP4 de control** con las mismas trayectorias y sin beeps; (c) repetición silenciosa de T2a dentro del corto |

## Resultados del artículo (para no exagerar)

- Exp. 1 (0,25 rps): PSE = 1,05, d = 0,57, JND ≈ 0,27.
- Exp. 2: PSE = 1,14 (1/24 rps), 1,13 (0,25 rps) y 1,02 (1,5 rps). JND = 0,59, 0,32 y 0,14 respectivamente.
- Interpretación del PSE: la luz sin sonido debe ir alrededor de un 5–14 % más rápido para *parecer* igual de rápida que la luz con beep.

**Consecuencia honesta para el video:** el efecto es pequeño comparado con el JND. Con velocidades físicas idénticas, un espectador típico elegirá la luz con beep como "más rápida" algo más de la mitad de las veces, no siempre. El corto no promete una aceleración visible y dramática. Plantea la pregunta, el pudú dramatiza la contradicción y la revelación declara el tamaño de laboratorio (≈5–14 %).

Elegí 0,25 rps porque es la condición con mejor relación entre desplazamiento del PSE y JND. A 1/24 rps el JND (59 %) hace la ilusión prácticamente imperceptible en un único ensayo; a 1,5 rps la ilusión casi desaparece (2 %).

## Desviaciones respecto del laboratorio (y por qué)

1. **Geometría 9:16.** Con radio 0,1 y centros a ±0,2 de la altura, el círculo izquierdo se saldría del cuadro vertical. Se escaló a radio 0,07 y centros ±0,13 conservando la velocidad angular (rps). La velocidad lineal en pantalla es menor que en el artículo, aunque idéntica entre ambas luces.
2. **Fondo con escena.** El artículo usa fondo gris uniforme y un marco blanco. Aquí el fondo es un bosque en penumbra. Para reducir distractores, durante los ensayos: la cámara está fija; no hay esporas flotantes; la música está en silencio; el ambiente se atenúa unos 14 dB; el pudú sólo respira (sin movimientos ligados a los beeps); y las luces 3D que iluminan la escena son las mismas que las del estímulo.
3. **Pantallas móviles.** Merz et al. *excluyeron* smartphones y tablets. Ver el corto en un teléfono es, por definición, una condición no probada en el artículo. La latencia audio-video de cada dispositivo (Bluetooth: típicamente decenas o cientos de ms) puede romper la sincronía y debilitar el efecto. Por eso recomendamos audio por altavoz o con cable.
4. **Un solo espectador, pocos ensayos.** El artículo promedia 320 ensayos por persona. El corto ofrece 2 ensayos por lado más la revelación. Es una demostración, no una medición.
5. **Persecución (3–12 s).** Usa movimiento lineal (zig-zag vertical a velocidad de módulo constante) con beeps en cada inversión. Es narrativa e inspirada en el paradigma lineal original; no es un ensayo controlado.

## Garantías del estímulo (verificadas automáticamente)

- La velocidad angular es exactamente constante, frame a frame, para ambas luces (`bs.verify`).
- Los cambios de dirección cumplen las restricciones del artículo para todas las semillas probadas (200 semillas × 9 razones en `tests/`).
- La luminancia de las luces es constante durante cada ensayo: no hay destellos ni cambios de brillo en los beeps.
- El MP4 de control tiene trayectorias idénticas bit a bit y ningún beep detectable.
- En el MP4 **decodificado** se miden: (a) los onsets de los beeps, con un filtro adaptado; (b) las inversiones de las luces, con seguimiento del centroide; (c) el desfase entre ambos (`pudulab/verify.py`).
