# Vision Supervision

**Librería nativa de supervisión por computadora, construida desde principios fundamentales.**

Sin dependencias externas de ML. Sin APIs cloud. Sin roboflow. Solo OpenCV + NumPy + Python puro.

> **Toolchain unificado.** El motor canónico vive en un solo lugar:
> `C:/æ/supervisionvidaeo/supervisionvidaeo/vision/`. Este paquete es un
> **shim** que re-exporta el motor bajo el nombre histórico `vision_supervision`
> (incluidos los imports profundos, vía alias en `sys.modules`). No hay copias
> que derivan: `vision_supervision.X is supervisionvidaeo.vision.X`.

## Filosofía

| Principio | Implementación |
|---|---|
| **Local primero** | Todo corre en tu máquina, sin enviar datos a APIs externas |
| **Desde cero** | Cada algoritmo está implementado y documentado, no es una caja negra |
| **Sin ML obligatorio** | Funciona sin modelos de deep learning — color, movimiento, IoU |
| **Extensible** | Agrega tus propios detectores, rastreadores y anotadores |
| **Español nativo** | Documentación, comentarios y mensajes en español |

## Instalación

```bash
# Desde el directorio del proyecto
cd C:/æ/vision-supervision
pip install -e .
```

## Uso rápido

### Detectar objetos por color

```python
import cv2
from vision_supervision import DetectorColor, Anotador

# Inicializar
detector = DetectorColor(colores=["rojo", "verde", "azul"])
anotador = Anotador()

# Procesar imagen
imagen = cv2.imread("imagen.jpg")
lote = detector.detectar(imagen)
anotada = anotador.anotar(imagen, lote)

cv2.imwrite("resultado.jpg", anotada)
```

### Rastrear objetos en video

```python
from vision_supervision import DetectorMovimiento, RastreadorIOU, Anotador, ProcesadorVideo

detector = DetectorMovimiento()
rastreador = RastreadorIOU(umbral_iou=0.3, max_edad=5)
anotador = Anotador()

procesador = ProcesadorVideo(detector, rastreador, anotador)

for frame in procesador.procesar("video.mp4", mostrar=True):
    pass  # procesamiento en tiempo real
```

### Evaluar detecciones

```python
from vision_supervision import Metricas

# Un frame
pr = Metricas.precision_recall(predichas, ground_truth, umbral_iou=0.5)
print(f"Precision: {pr['precision']:.2f}, Recall: {pr['recall']:.2f}")

# Múltiples frames
map_score = Metricas.map_promedio(predichas_por_frame, gt_por_frame)
print(f"mAP: {map_score:.2f}")
```

## Estructura

```
vision_supervision/
├── __init__.py          # Exportaciones públicas
├── deteccion.py         # Deteccion, LoteDetecciones
├── anotador.py          # Anotador visual (bounding boxes, etiquetas)
├── rastreador.py        # RastreadorIOU (asignación greedy)
├── procesador.py        # ProcesadorVideo (pipeline frame a frame)
├── metricas.py          # Metricas (precision, recall, mAP)
└── detectores.py        # DetectorColor, DetectorMovimiento
```

## Detectores incluidos

| Detector | Descripción | Requiere ML |
|---|---|---|
| `DetectorColor` | Segmentación por color HSV | No |
| `DetectorMovimiento` | Diferencia de frames consecutivos | No |

## Tests

```bash
pytest tests/ -v
```

## Licencia

Open Sourceware — libre para usar, modificar y distribuir.
