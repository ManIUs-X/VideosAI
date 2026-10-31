# Ejecutar desde un teléfono Android (sin computador)

## Opción A — Google Colab (gratis; recomendada para empezar)

1. **Token de GitHub** (necesario porque el repositorio es privado). Hazlo una sola vez:
   - En Chrome, entra en github.com → foto de perfil → *Settings* → *Developer settings* → *Personal access tokens* → *Fine-grained tokens* → *Generate new token*.
   - En *Repository access*, elige sólo `manius-x/videosai`; en *Contents*, permiso *Read-only*. Copia el token.
2. Abre https://colab.research.google.com → *GitHub* (o *Archivo → Abrir cuaderno → GitHub*). Inicia sesión y elige `manius-x/videosai`, rama `claude/pudu-perceptual-shorts-x7bxef`, archivo `notebooks/pudu_shorts_colab.ipynb`.
   - Si Colab no muestra repositorios privados, descarga el `.ipynb` desde GitHub en el teléfono y súbelo con *Archivo → Subir cuaderno*.
3. En Colab: ícono de llave 🔑 (*Secretos*) → *Agregar* → nombre `GITHUB_TOKEN`, pega el token y activa *Acceso del cuaderno*.
4. *Entorno de ejecución → Cambiar tipo de entorno de ejecución → T4 GPU*. Si no hay GPU disponible, sigue en CPU (más lento).
5. Ejecuta las celdas 1 a 5 en orden, con ▶. En la celda 3 elige el modo:
   - `test`: prototipo de 8 s (siempre conviene hacerlo primero).
   - `final`: corto completo, con GPU.
   - `animatic`: corto completo en baja calidad, rápido incluso sin GPU.
6. La celda 5 muestra el video, imprime la verificación y descarga el MP4 al teléfono. Con `SAVE_TO_DRIVE` lo copia a Drive (`PuduShorts/`).

**Advertencias reales de Colab gratuito:**
- La GPU no está garantizada y la sesión se corta tras inactividad o tras unas horas.
- El render es reanudable dentro de la misma sesión: si se interrumpe, vuelve a ejecutar la celda 4.
- Si la sesión muere, se pierde el disco de Colab. Para trabajos largos conviene activar `SAVE_TO_DRIVE` o usar RunPod.
- No he medido tiempos en una T4. La estimación es de 30 a 60 min para `final`, a confirmar en la primera ejecución.

## Opción B — RunPod (de pago; sólo con tu autorización)

1. runpod.io → *Pods* → *Deploy* → una GPU NVIDIA (p. ej., RTX 4090 o A4000) con la plantilla *RunPod PyTorch* (Ubuntu + CUDA). Elige un volumen de 20 GB.
2. *Connect* → *Start Web Terminal* (funciona en el navegador del teléfono).
3. En la terminal:
   ```bash
   git clone -b claude/pudu-perceptual-shorts-x7bxef https://<TOKEN>@github.com/manius-x/videosai.git
   cd videosai && bash tools/install_blender.sh && pip install -r requirements.txt
   python run.py --mode test --device OPTIX
   python run.py --mode final_hd --device OPTIX
   ```
4. Descarga `output/ep01_beep_speed/final_hd/*.mp4` desde *Connect → Jupyter Lab* (clic derecho → *Download*).
5. **Detén el pod al terminar** (*Stop* / *Terminate*): cobra por minuto mientras está encendido.

Si OptiX falla, usa `--device CUDA`.

## Al publicar

- Revisa el MP4 con audio por altavoz o auriculares con cable. El Bluetooth añade retraso y puede desincronizar el beep de la inversión.
- Instagram, TikTok y YouTube Shorts aceptan 1080×1920 H.264 + AAC. Los rótulos están dentro de las zonas seguras: no hay texto en el 10 % superior salvo la marca, ni en el 18 % inferior salvo los créditos.
