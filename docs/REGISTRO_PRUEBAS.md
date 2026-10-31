# Registro de pruebas ejecutadas

Entorno: contenedor en la nube de Claude Code (Linux x86-64, 4 vCPU, 15 GB RAM, **sin GPU**), Python 3.13, FFmpeg 6.1.1, Blender 4.2.23 LTS (tarball oficial). Fecha: 2026-10-31.

## 1. Entorno y motores de render (medido)
| Prueba | Resultado |
|---|---|
| `nvidia-smi` | no existe: **no hay GPU**; todo se renderizó en CPU |
| Cycles CPU, escena por defecto, 540×960, 16 spp | 4,3 s |
| EEVEE Next (OpenGL por software llvmpipe, tras instalar libegl1) | funciona; 1.er frame 46–53 s (compilación de shaders), después 9–10 s/frame: **no mejora a Cycles** |
| Workbench | 1,2 s/frame |

## 2. Optimización de Cycles sobre la escena real (frame 120, 540×960)
| Variante | s/frame |
|---|---|
| 12 spp + motion blur + SSS | 15,9 |
| sin motion blur | 13,2 |
| + sin SSS | 12,9 |
| + GI rápida (AO), 1 rebote difuso | 10,4 |
| + 6 spp | 6,8 |
| sin muestreo de emisión | sin mejora relevante |

Decisión: preset `test`/`final_cpu` = GI rápida, sin motion blur, 8–10 spp + OIDN ≈ 8,3 s/frame (medido en la prueba de 8 s). Los presets con GPU (`final`, `final_hd`) mantienen motion blur y más muestras; **no se han ejecutado aquí** porque no hay GPU.

## 3. Pruebas unitarias (`python tests/test_pipeline.py`): todas pasan
- Restricciones del paradigma en 200 semillas × 9 razones de velocidad: 3 inversiones por objeto, ninguna en los primeros ni últimos 100 ms de cada segundo, separación AV–V ≥ 200 ms, velocidad angular constante.
- Control: trayectorias idénticas bit a bit, sin beeps.
- Persecución: módulo de velocidad constante.
- Beep: 68 ms, pico espectral en 440 Hz. El detector recupera 3 onsets con error < 2 ms bajo ruido. *Primera versión del detector:* sesgo de −4,8 ms (por la envolvente de un filtro de fase cero). Se reemplazó por un filtro adaptado.
- Plan: duración ≤ 60 s, luminancia constante de las luces en todos los frames de todos los ensayos, sin estímulo durante la persecución.
- Animación determinista.

## 4. Revisión visual de fotogramas clave (Cycles, 8 spp)
Primera pasada, problemas encontrados y corregidos:
- El pudú quedaba fuera de cuadro en la persecución y detrás de las nalcas, que estaban sobre el sendero.
- La cámara del plano final quedaba dentro de las hojas.
- La imagen era demasiado oscura.
- Había helechos tapando la cámara en el lado del sendero.
- Aparecía una costura oscura entre cuello y cabeza.

Segunda pasada: todos los planos legibles, salvo el final, que se corrigió de nuevo (sector frontal del parche abierto).

## 5. Prototipo de 8 s (`python run.py --mode test`): EJECUTADO
- Render 3D: 240 frames a 540×960 con Cycles CPU en 1954 s (8,1 s/frame). Composición a 60 fps: unos 2 min.
- Archivo: `ep01_beep_speed_test.mp4`. Medido con ffprobe: H.264 High, yuv420p, 1080×1920, 60 fps, AAC 48 kHz estéreo, 8,0 s. Más `ep01_beep_speed_test_control.mp4`.
- Medido sobre el MP4 **decodificado**:
  - beeps detectados 8/8; error de onset de −0,04 a +0,46 ms;
  - control: 0 beeps detectados;
  - ensayo del gancho: inversiones medidas en el video = inversiones planificadas (error de 0 frames, sin inversiones espurias); velocidad medida 0,2528 / 0,2525 rps (objetivo 0,25); error máximo de posición 2,7 px; beep − inversión visual = 0,00 a 0,02 ms;
  - flashes: 0 transiciones grandes opuestas por segundo (cambio máximo de luminancia media entre frames: 0,023);
  - sonoridad: −15,1 LUFS integrados, pico real −1,0 dBFS.

### Fallos encontrados en el prototipo y corregidos (iteraciones reales)
1. Recuadros visibles alrededor de cada luz: el parche del sprite cortaba la cola del halo ancho. Se amplió el radio del parche.
2. Rótulos más anchos que el cuadro: ahora se ajustan automáticamente al 86 % del ancho.
3. **Música con notas La4 (440 Hz)** durante la persecución: el detector encontró 2 "beeps" extra en la versión con ilusión y 4 en el control. Diluía la asociación beep↔giro. Regla nueva: el beep es el único evento de 440 Hz del episodio (`score.safe()`). Tras el cambio: 8/8 detecciones y 0 en el control.
4. El verificador de video se enganchaba a la oreja del pudú, iluminada por la luz 3D del estímulo. Medía 0,04 rps y luego 0,149 rps en un lado. Cambios: (a) la luz 3D del gancho baja de 1,6 a 0,5 W y el estímulo sube (center_y de 0,215 a 0,25) para alejarlo de la cabeza; (b) el rastreo se hace en una ventana alrededor de la posición planificada y reporta el error de posición en px.
5. Desfase de 1 frame en el verificador (`ffmpeg -ss` descarta el frame en T−0,5/fps): corregido.
6. Sesgo del estimador de velocidad (mediana de |Δθ| sobre posiciones cuantizadas: +8–12 %): reemplazado por una regresión lineal por tramo.

Nota: tras los cambios 3–6, el MP4 de prueba se recompuso y se volvió a verificar (`--skip-render`) sobre los frames 3D ya renderizados. Su iluminación 3D del gancho corresponde aún a la posición antigua del estímulo. El render completo usa la configuración nueva.

## 6. Animática
- **Workbench (3D):** se lanzó y se **detuvo**. Con OpenGL por software iba a ~9 s/frame, igual que Cycles, así que no ahorraba tiempo en este entorno.
- **Animática 2D (`--mode animatic2d`): EJECUTADA.** Duración completa de 54,5 s, con fondo provisional rotulado con plano y tiempo, estímulo exacto, rótulos, mezcla final y control. Medido en el MP4 decodificado:
  - especificaciones correctas (1080×1920, 60 fps, H.264 High, AAC 48 kHz estéreo, 54,5 s);
  - beeps 24/24 detectados, error máximo de 0,46 ms; control con 0 beeps;
  - **6 ensayos** (hook, T1a, T1b, T2a, T2b, revelación): 0 frames de error en todas las inversiones, sin inversiones espurias, velocidad medida de 0,2476 a 0,2523 rps (objetivo 0,25), error de posición ≤ 1,74 px, beep − inversión visual entre −0,02 y +0,02 ms, revelación sin beeps;
  - flashes: 0; sonoridad: −17,5 LUFS, pico real −1,1 dBFS.

## 7. Render final en CPU (`--mode final_cpu`)
Lanzado a las 06:08 (hora del contenedor). 1635 frames 3D a 540×960, 10 spp + OIDN, compuestos a 1080×1920 y 60 fps.
- **Render 3D completado:** 1635 frames en 15205 s (4 h 13 min; ≈ 9,3 s/frame). El primer compuesto se descartó porque tenía el rótulo antiguo de la revelación. Se recompuso con `--skip-render` en 16 min.
- **Archivos:** `ep01_beep_speed_final_cpu.mp4` (23,1 MB) y `ep01_beep_speed_final_cpu_control.mp4`.
- **Medido sobre el MP4 decodificado (`verification.json`, `all_ok: true`):**
  - especificaciones: 1080×1920, 60 fps, H.264 High, AAC 48 kHz estéreo, 54,5 s;
  - beeps: 24/24, error de onset máximo de 0,46 ms; control: 0 beeps;
  - 6 ensayos (hook, T1a, T1b, T2a, T2b, revelación): 0 frames de error en todas las inversiones y 0 inversiones espurias;
  - velocidad medida: 0,2477–0,2557 rps (objetivo 0,25);
  - error de posición ≤ 3,97 px, sobre el fondo 3D real con ruido de render;
  - beep − inversión visual: −0,02 a +0,02 ms;
  - flashes: 0 (cambio máximo de luminancia media entre frames: 0,031);
  - sonoridad: −17,5 LUFS, pico real −1,1 dBFS.
- **Revisión visual de 8 fotogramas, defectos conocidos no corregidos:**
  - En el escenario el pudú se ve casi siempre de espaldas, como una silueta oscura, y su expresión apenas se lee.
  - El pelaje se ve gris en la escena con luz de luna.
  - El 3D es de 540×960 escalado a 1080×1920, sin desenfoque de movimiento.
  - Para mejorarlo: render con GPU (`final`/`final_hd`) y un plano frontal del pudú en las pruebas.

## 8. Episodio 04 «Los destellos fantasma» (2.5D, sin Blender)
Comando: `python -m episodes.ep04_destellos_fantasma.make`. Renderiza 2910 frames con 4 procesos, a unos 0,14 s/frame de reloj (unos 7 min), y después hace la verificación.

### Iteraciones reales
1. **Pudú 2.5D:** la luz de borde y la sombra salían en el lado opuesto, por el signo del desplazamiento de las máscaras. Se corrigió, igual que la pezuña levantada, que se veía como «dos dedos» flotando.
2. **Prueba de 7 s (12–19 s):** el verificador encontró cambios de píxeles en el pudú justo antes del destello, cada 6 frames. Causa: la caché de poses usaba claves redondeadas pero dibujaba con valores sin redondear, así que el resultado dependía del historial de cada proceso. Ahora la pose se cuantiza antes de dibujar y el render es determinista; la comprobación exacta da 0 píxeles cambiados fuera del disco.
3. **Ruido del códec:** en el MP4 decodificado, H.264 recuantiza unos pocos bordes de texto (≤ 48 píxeles a media resolución) en el frame del destello. Se distingue de un evento real con una comprobación exacta antes del códec y un umbral tolerante después.
4. **Primer render completo: FALLÓ la verificación.** La luciérnaga del gancho, al irse volando, cruzaba la posición del destello a los 2,88 s y se detectó como un evento visual no planificado. Se cambiaron las trayectorias de esa luciérnaga y de la del final para que nunca pasen a menos de 150 px de esa posición, y se volvió a renderizar.

### Resultado medido (render final, `verification.json`, `all_ok: true`)
- **Especificaciones:** H.264 High, 1080×1920, 60 fps, yuv420p, AAC 48 kHz estéreo, 48,5 s.
- **Eventos visuales detectados en el MP4:** exactamente 5, a 14,0 / 17,5 / 21,0 / 35,0 / 38,5 s, de 2 frames cada uno, y 0 eventos no planificados. Tras recodificar a 30 fps siguen siendo 5, de 1 frame cada uno.
- **Bips:** 8/8 detectados (B2F1 ×4), con un error de onset máximo de 0,02 ms. No hay bips en el control B0F1.
- **Sincronía medida:** inicio del destello → primer bip de 0,00 a 0,02 ms; intervalo entre bips de 65,98 a 66,00 ms.
- **Exclusividad del evento:**
  - antes del códec, 0 píxeles cambian fuera del disco entre onset−3 y onset+4;
  - en el MP4, 11–48 píxeles cambian a media resolución por ruido del códec.
- **Versiones:**
  - el video es idéntico (md5) en las tres;
  - `sin_bips` tiene 0 bips;
  - `sin_sonido` tiene un pico de 0.
- **Seguridad:**
  - 0 transiciones grandes de luminancia;
  - el destello ocupa el 0,14 % del área;
  - los destellos están separados ≥ 3,5 s.
- **Sonoridad:** −16,1 LUFS, pico real de −1,9 dBFS.
- **Pruebas unitarias:** 7/7 pasan (nueva: `test_sifi_schedule_and_detectors`).

### Lo que NO se pudo verificar
- No se midió la percepción: no hubo participantes.
- No se probó el comportamiento real de Instagram o TikTok al recodificar; se simuló con `ffmpeg -vf fps=30`.
- No se midió la latencia de audio en móviles ni con Bluetooth.
