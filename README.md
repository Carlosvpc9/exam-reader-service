# OMR Vision API — Lector de Hojas de Respuesta con Claude AI

API REST que usa **Claude Vision** para leer cualquier tipo de hoja de respuesta de examen, sin importar el formato, diseño o número de opciones.

## ¿Por qué Claude Vision?

A diferencia de OpenCV (que requiere hojas estandarizadas con marcadores de esquina), Claude Vision puede leer **cualquier formato** de hoja de respuesta: con o sin marcadores, con 4 opciones, 5 opciones, numeración arbitraria, etc.

## Setup

### Variables de entorno requeridas

| Variable | Descripción |
|---|---|
| `ANTHROPIC_API_KEY` | Tu API key de Anthropic (console.anthropic.com) |

### Deploy en Railway

1. Sube este proyecto a GitHub
2. Ve a [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. En **Variables**, agrega `ANTHROPIC_API_KEY` con tu clave
4. Railway hace el deploy automáticamente ✅

### Correr localmente

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

## Endpoints

### `GET /`
Health check.

### `POST /scan`

**Request:**
- Content-Type: `multipart/form-data`
- Campo: `image` (JPG, PNG, WebP — máx 10MB)
- Query params opcionales:
  - `start`: número de la primera pregunta
  - `end`: número de la última pregunta

**Ejemplo:**
```bash
curl -X POST https://tu-api.up.railway.app/scan \
  -F "image=@hoja.jpg"

# Con rango de preguntas
curl -X POST https://tu-api.up.railway.app/scan?start=96&end=105 \
  -F "image=@hoja.jpg"
```

**Response:**
```json
{
  "success": true,
  "total_questions": 10,
  "answered": 9,
  "answers": {
    "96": "C",
    "97": "C",
    "98": "B",
    "99": "B",
    "100": "D",
    "101": "C",
    "102": "C",
    "103": "C",
    "104": "B",
    "105": "A"
  },
  "notes": "La pregunta 98 tiene una respuesta poco clara",
  "usage": {
    "input_tokens": 1423,
    "output_tokens": 87
  }
}
```

## Costo estimado

Con `claude-sonnet`, cada escaneo cuesta aproximadamente **$0.002 USD** por imagen (varía según tamaño).
