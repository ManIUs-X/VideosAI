# Continuidad de la serie

## Activos fijos (se reutilizan sin cambios)
- **Personaje:** `blender/pudu.py`, determinista. Mismo modelo, mismos materiales y mismo rig en todos los episodios. Las acciones están en `blender/anim.py`; para añadir nuevas, se suman capas al bucle de `compute()`.
- **Bosque:** `blender/forest.py`, con semilla. `seed=7` corresponde al "claro del tronco" del Ep. 01; otras semillas generan otros rincones del mismo bosque.
- **Tipografía, paleta de luces y marca:** `assets/fonts/Baloo2.ttf`, `light_style` en el plan y el rótulo «NEXO NEUROLAB».
- **Pipeline:** `run.py`. Se encarga del plan, la capa 3D, la composición a 60 fps, el audio, la mezcla de ilusión y de control, y la verificación.

## Plantilla de un episodio
1. Crea `pudulab/illusions/<ilusion>.py` con: dataclass de parámetros del paradigma, `generate()`, `verify()` (que levanta una excepción si se viola el paradigma), `control_of()` y un diccionario `PAPER` con la cita, el DOI y los resultados reportados.
2. Crea `episodes/epNN_<nombre>/episode.py` con `build_plan()`: ensayos, planos, actuación del pudú y rótulos.
3. Crea `episodes/epNN_<nombre>/score.py` con `build_stems()`. Los estímulos sonoros van en un stem propio para poder derivar el control.
4. Amplía `pudulab/verify.py` con la medida que corresponda al nuevo estímulo.
5. Añade pruebas en `tests/`. Documenta los parámetros y las desviaciones en `docs/`.

## Episodios candidatos (referencias localizadas, sin leer todavía a texto completo)

### Twinkle-goes illusion
Nakayama, R., & Holcombe, A. O. (2021). *A dynamic noise background reveals perceptual motion extrapolation: The twinkle-goes illusion.* Journal of Vision, 21(11):14. doi:10.1167/jov.21.11.14 (PMC8543404).
Fenómeno: sobre un fondo de ruido dinámico, el punto donde desaparece un objeto en movimiento se percibe desplazado en la dirección del movimiento. Atender a dos objetos reduce el efecto.
Requisitos técnicos: fondo de ruido dinámico generado por frame (NumPy) en una región de la escena y desaparición del objeto en un frame exacto; el control es el mismo movimiento sobre fondo estático. Encaja con el compositor actual, porque el estímulo es 2D a 60 fps.
Seguimiento: hay un estudio de 2025 en Experimental Brain Research (doi:10.1007/s00221-025-07187-5) que propone un mecanismo de "sobrepaso de la predicción posicional".

### Auditory reverse-phi
Preprint de 2024 en bioRxiv (doi:10.1101/2024.08.03.606481, PMC11312537). Describe estímulos de ruido con correlaciones espectro-temporales negativas que producen una dirección de tono (sube/baja) invertida, como análogo auditorio del reverse-phi visual.
**Por verificar:** autores, si ya fue revisado por pares y los parámetros exactos. No lo he leído completo.
Requisitos técnicos: síntesis de estímulos auditivos (ampliar `pudulab/audio.py`). La animación sería un correlato narrativo y no puede sustituir al estímulo, que es auditivo.

## Reglas que conviene mantener
- El estímulo nunca se "embellece" con cambios de brillo, tamaño o color ligados a los eventos críticos.
- Cada episodio publica también su MP4 de control y su `verification.json`.
- Los rótulos citan el tamaño real del efecto reportado, no uno exagerado.
