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

## 5. Prototipo de 8 s (`python run.py --mode test`)
(se completa abajo con los resultados medidos)
