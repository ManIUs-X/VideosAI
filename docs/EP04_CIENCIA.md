# Episodio 04 — «Los destellos fantasma»: base científica, adaptación y seguridad

## Referencia
Yang H, Ding D, Qin H, Miao H, Wang C, Zang Y, Chi L, Wu B (2026). *Perceptual decision-making in the sound-induced flash illusion: a trial-level hierarchical Bayesian integration of EEG and behavior.* Behavioral and Brain Functions 22:48. doi:[10.1186/s12993-026-00344-y](https://doi.org/10.1186/s12993-026-00344-y). Acceso abierto: PMC13637232, licencia CC BY-NC-ND 4.0.

El artículo **solo se cita**. El episodio no reproduce ninguna figura ni texto suyo.

Efecto original: Shams, Kamitani y Shimojo (2000), *Nature* 408, 788.

## Parámetros del artículo (Methods, «Design and stimuli»; leídos en el texto completo)
| Parámetro | Yang et al. 2026 | Este episodio |
|---|---|---|
| Pantalla | 60 Hz, 1024×768 | Video a 60 fps, 1080×1920 |
| Destello | Disco blanco de radio 2°, sobre negro | Disco crema (250, 242, 220) de radio 30 px (~0,3–0,4° en un móvil a 30 cm), sobre el bosque oscurecido |
| Posición | Dos discos simultáneos a 7° a izquierda y derecha de la fijación | Un disco a la derecha, a 380 px de la cruz (~4–5°) |
| Duración del destello | 17 ms (1 frame) | **33 ms (2 frames)**; ver «Desviaciones» |
| Bip | Tono puro de 3,5 kHz, 17 ms, 75 dB SPL, auriculares | Tono puro de 3,5 kHz, 17 ms, rampas de 2 ms; nivel moderado, sin control de SPL |
| Intervalo entre bips | 66 ms | 66 ms |
| Inicio relativo destello/bip | «Simultáneo» (sin cifra) | Primer bip exactamente en el inicio del destello |
| Condiciones | B0F1, B0F2, B1F1, B1F2, B2F1, B2F2 | B2F1 (×4) y B0F1 (×1, control) |
| Ensayos | 400 por persona | 5 destellos en total en el video |

## Qué dice el resultado (honestamente)
- Precisión en la tabla 1 (n = 25):
  - B0F1 (un destello sin sonido): 0,952;
  - **B2F1 (un destello con dos bips): 0,808**.
- Es decir, con dos bips se informó «dos destellos» en **≈19 %** de los ensayos B2F1, frente a ≈5 % sin sonido.
- El efecto es real y robusto en promedio, pero **la mayoría de las veces la mayoría de las personas ve un solo destello**.
  - Otros estudios con el mismo efecto reportan tasas más altas, que dependen de la excentricidad, del contraste y de la persona. Este episodio no puede garantizar la ilusión.
  - El guion lo dice explícitamente al final: «No todos la ven: en laboratorio, ~1 de cada 5 ensayos».
- En un móvil, sin control de distancia, de fijación ni de volumen, y con posibles retrasos de audio Bluetooth (100–300 ms), cabe esperar un efecto **igual o menor**. Con auriculares Bluetooth, el bip puede llegar después de que el destello termine y anular la sincronía.

## Desviaciones y por qué
1. **El destello dura 2 frames (33 ms), no 1.**
   - Instagram, TikTok y otras plataformas pueden recodificar a 30 fps. Un destello de un solo frame a 60 fps puede desaparecer (o no) según qué frames se descarten.
   - Con 2 frames que empiezan en un frame par, cualquier diezmado a 30 fps conserva exactamente 1 frame de 33 ms. Eso se comprueba por código (ver abajo).
   - Un destello más largo podría reducir algo la ilusión: es una compensación consciente a favor de que el estímulo exista siempre.
2. **Un solo disco lateral** (el guion pide «una luz lateral»), más pequeño y menos luminoso que el de laboratorio, sobre fondo oscurecido y no negro. Motivos: seguridad (luminancia moderada) y estética.
3. **Excentricidad menor (~4–5° frente a 7°).** Una pantalla vertical de móvil no da 7° a cada lado de forma fiable. La ilusión suele ser más fuerte en la periferia, así que esto también puede reducirla.
4. **Pocos ensayos.** Esto es una demostración, no una medición.

## Regla central
**En la condición experimental hay un único evento visual físico.**
- **No se añade en posproducción ningún segundo destello.** El disco se dibuja una sola vez por presentación, encima de todo, a intensidad constante durante sus 2 frames.
- **No hay otros cambios en pantalla:** durante ±0,6 s alrededor de cada destello no se mueve la cámara, el pudú no parpadea ni respira, no cambian los rótulos y no hay luciérnagas.
- **Silencio alrededor:** la música y los efectos callan en ±1 s, y el ambiente baja al 25 %.
- **Bip exclusivo:** ningún otro sonido del episodio tiene energía en 3,5 kHz; todos los demás stems pasan por un filtro paso bajo de 2,4 kHz.

## Verificación por código (sobre los MP4 decodificados)
Ver `episodes/ep04_destellos_fantasma/make.py` y `verification.json`:
- **Eventos visuales:** se mide la luminancia de la región del disco en cada frame decodificado. El script cuenta las rachas por encima de la mediana móvil y comprueba el número de eventos, el frame de inicio y la duración (en frames).
- **Recodificación a 30 fps** (`ffmpeg -vf fps=30`): el mismo número de eventos, con 1 frame cada uno.
- **Exclusividad del evento:**
  - en los frames renderizados (antes del códec), de onset−3 a onset+4, sólo cambian píxeles dentro del disco (exacto: 0 píxeles fuera);
  - en el MP4 decodificado se informa el ruido del códec fuera del disco.
- **Eventos auditivos:** filtro adaptado al bip de 3,5 kHz y 17 ms sobre el audio decodificado. Se comprueban el número de bips, el error de onset, el desfase entre el primer bip y el inicio del destello, y el intervalo entre bips.
- **Versiones:**
  - el video es idéntico bit a bit en las tres (md5 del flujo de video);
  - `sin_bips` tiene 0 bips detectados;
  - `sin_sonido` tiene un pico de audio de 0.
- **Seguridad:** conteo de transiciones grandes de luminancia media (estilo WCAG 2.3.1), área del destello, separación mínima entre destellos y sonoridad EBU R128.

## Seguridad fotosensible
- **Solo 5 destellos en 48,5 s, separados ≥ 3,5 s:** muy por debajo de 3 destellos por segundo.
- **Área del destello:** 0,14 % del cuadro. El umbral de WCAG para «destello general» es el 25 % de un campo de 10°.
- **Sin pantalla completa:** no hay destellos de pantalla completa, rojo saturado, patrones ni estroboscopia. Las luciérnagas aparecen y desaparecen con rampas de ≥ 0,45 s.
- Con estas condiciones, la presentación del paradigma es compatible con redes sociales; no fue necesario excluir la demostración.
