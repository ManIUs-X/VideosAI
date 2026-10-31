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
