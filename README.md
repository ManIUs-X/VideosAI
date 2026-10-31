# NEXO NEUROLAB — Pudú Perceptual Shorts

Serie de cortometrajes verticales en 3D (1080×1920, 60 fps, H.264 + AAC 48 kHz estéreo) protagonizados por un pudú chileno. Cada episodio construye una ilusión perceptiva publicada **a partir de los parámetros del paradigma experimental**, no con efectos visuales arbitrarios, e incluye siempre una versión de control.

**Episodio 01 — «La luz que acelera»**: beep-speed illusion (Merz et al., 2026, doi:10.3758/s13414-025-03211-6). Ver [`docs/CIENCIA.md`](docs/CIENCIA.md).

## Cómo obtener el MP4 sin computador (sólo Android)

Ver [`docs/EJECUCION_ANDROID.md`](docs/EJECUCION_ANDROID.md). Resumen: abre `notebooks/pudu_shorts_colab.ipynb` en Google Colab desde el navegador del teléfono, elige GPU T4, ejecuta las 5 celdas y descarga el MP4.

## Uso (cualquier Linux con Python ≥ 3.10)

```bash
bash tools/install_blender.sh          # Blender 4.2 LTS en /opt/blender
pip install -r requirements.txt
python run.py --mode test              # prototipo de 8 s (CPU: ~35 min)
python run.py --mode animatic2d        # corto completo sin 3D (fondo provisional): valida estímulo, rótulos y audio en ~10 min
python run.py --mode animatic          # corto completo con Workbench (rápido con GPU; en CPU sin GPU tarda lo mismo que Cycles)
python run.py --mode final_cpu         # corto completo, Cycles CPU 540×960 → 1080×1920 (CPU 4 núcleos: ~4 h)
python run.py --mode final --device OPTIX     # GPU NVIDIA: Cycles 720×1280, 32 spp, motion blur
python run.py --mode final_hd --device OPTIX  # GPU NVIDIA: 1080×1920 nativo, 64 spp
```

El render es **reanudable**: si se corta, al volver a ejecutar el mismo comando se saltan los frames ya hechos.

Salidas en `output/<episodio>/<modo>/`:
- `<ep>_<modo>.mp4`: versión con la ilusión.
- `<ep>_<modo>_control.mp4`: misma imagen y mismas trayectorias, sin beeps.
- `verification.json`: especificaciones, sincronía beep↔inversión medida en el MP4 decodificado, velocidad medida, flashes y sonoridad.
- `mix_illusion.wav`, `mix_control.wav`, `stem_beeps.wav`, `plan.json`, `projections.json`, `scene.blend`, `preview/`.

## Arquitectura

```
pudulab/                     # núcleo reutilizable (Python puro + NumPy/SciPy)
  illusions/beep_speed.py    # generador de estímulo + verificación + control
  lights.py                  # estado exacto de cada luz por frame (compartido con Blender)
  audio.py                   # síntesis: beep del paradigma, instrumentos, foley, ambiente, reverb
  compositor.py              # composición 2D a 60 fps (estímulo, rótulos) → FFmpeg
  verify.py                  # verificación independiente del MP4 final
blender/                     # se ejecuta dentro de Blender (bpy)
  pudu.py                    # personaje procedural + rig de pivotes (idéntico en toda la serie)
  anim.py                    # acciones: correr, mirar, sorpresa, salto, asentir, caída, etc.
  forest.py                  # bosque valdiviano: coihues, arrayanes, araucarias, nalcas, helechos
  render_episode.py          # construye la escena a partir del plan y renderiza la capa 3D
episodes/ep01_beep_speed/
  episode.py                 # plan declarativo: ensayos, planos, actuación, rótulos
  score.py                   # música y diseño sonoro originales del episodio
notebooks/pudu_shorts_colab.ipynb
tools/install_blender.sh
tests/test_pipeline.py       # pruebas rápidas sin Blender
```

**Principio de diseño:** el estímulo se dibuja en 2D, a 60 fps exactos y con luminancia constante, a partir de las mismas matrices que generan los beeps. La capa 3D (30 fps, cada frame mostrado dos veces) aporta el mundo, el personaje y la iluminación coherente: luces puntuales 3D situadas detrás de cada luz del estímulo. Así el estímulo nunca depende del ruido del render.

Para un episodio nuevo: crea `episodes/epNN_nombre/episode.py` y `score.py` con `build_plan()` y `build_stems()`, y añade el generador en `pudulab/illusions/`. Ver [`docs/SERIE.md`](docs/SERIE.md).

## Registro de pruebas

[`docs/REGISTRO_PRUEBAS.md`](docs/REGISTRO_PRUEBAS.md) recoge sólo lo que realmente se ejecutó y sus resultados medidos.

## Licencias

Código y assets procedurales: originales de este proyecto. Fuente tipográfica Baloo 2 bajo SIL OFL 1.1 (`assets/fonts/OFL.txt`).
