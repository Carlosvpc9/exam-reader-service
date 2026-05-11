import anthropic
import base64
import json
import os
import re

from flask import Flask, request, jsonify

app = Flask(__name__)
MAX_SIZE = 10 * 1024 * 1024  # 10MB

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Eres un sistema especializado en leer hojas de respuesta de exámenes.
Tu única tarea es identificar qué opción está marcada en cada pregunta de la imagen.

REGLAS ESTRICTAS:
- Analiza SOLO las burbujas/círculos visiblemente rellenos, oscurecidos o marcados
- Una burbuja marcada se ve más oscura, rellena o tachada que las demás
- Si ninguna burbuja está marcada en una pregunta, usa null
- Si hay ambigüedad (dos marcadas, borrones), usa null
- Responde ÚNICAMENTE con JSON válido, sin texto adicional, sin markdown

FORMATO DE RESPUESTA (JSON puro):
{
  "answers": {
    "96": "C",
    "97": "B",
    "98": null
  },
  "notes": "comentario opcional si hay algo inusual"
}"""


def encode_image(file_bytes: bytes, mime_type: str) -> str:
    return base64.standard_b64encode(file_bytes).decode("utf-8")


def parse_claude_response(text: str) -> dict:
    """Extrae el JSON de la respuesta de Claude de forma segura."""
    text = text.strip()

    # Limpiar bloques markdown si los hay
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    # Intentar parsear directo
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Buscar el primer objeto JSON en el texto
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No se pudo extraer JSON válido de la respuesta: {text[:200]}")


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "message": "OMR Vision API funcionando 🚀",
        "model": "claude-sonnet-4-6"
    })


@app.route("/scan", methods=["POST"])
def scan():
    # ── Validar imagen ──────────────────────────────────────────────
    if "image" not in request.files:
        return jsonify({"error": "Campo 'image' requerido (multipart/form-data)"}), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "El archivo no tiene nombre"}), 400

    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
    mime = file.content_type or "image/jpeg"
    if mime not in allowed:
        return jsonify({"error": f"Tipo de archivo no soportado: {mime}"}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_SIZE:
        return jsonify({"error": "Imagen demasiado grande (máx 10MB)"}), 400

    # ── Parámetros opcionales ───────────────────────────────────────
    # Puedes pasar ?start=1&end=20 para indicar el rango de preguntas
    q_start = request.args.get("start", type=int)
    q_end = request.args.get("end", type=int)

    range_hint = ""
    if q_start and q_end:
        range_hint = f"\nLa hoja contiene preguntas del {q_start} al {q_end}. Identifica todas."
    elif q_start:
        range_hint = f"\nLas preguntas comienzan desde el número {q_start}."

    # ── Llamar a Claude Vision ──────────────────────────────────────
    try:
        image_b64 = encode_image(file_bytes, mime)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Analiza esta hoja de respuestas e identifica todas las respuestas marcadas.{range_hint}"
                        }
                    ],
                }
            ],
        )

        raw_text = response.content[0].text
        parsed = parse_claude_response(raw_text)

        answers = parsed.get("answers", {})
        notes = parsed.get("notes", None)

        # Normalizar: asegurarse que los valores sean letras mayúsculas o null
        clean_answers = {}
        for q, a in answers.items():
            if a is not None:
                clean_answers[str(q)] = str(a).upper().strip()
            else:
                clean_answers[str(q)] = None

        answered = sum(1 for v in clean_answers.values() if v is not None)

        result = {
            "success": True,
            "total_questions": len(clean_answers),
            "answered": answered,
            "answers": clean_answers,
        }

        if notes:
            result["notes"] = notes

        # Info de uso de tokens (útil para monitorear costos)
        result["usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        return jsonify(result)

    except anthropic.AuthenticationError:
        return jsonify({"error": "ANTHROPIC_API_KEY inválida o no configurada"}), 401

    except anthropic.RateLimitError:
        return jsonify({"error": "Límite de requests alcanzado, intenta en unos segundos"}), 429

    except anthropic.APIError as e:
        return jsonify({"error": f"Error de API Anthropic: {str(e)}"}), 502

    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
