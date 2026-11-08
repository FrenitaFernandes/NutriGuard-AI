
import os
import time
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
import pillow_avif

from backend.services.ocr_service import extract_text_from_image
from backend.services.ingredient_service import analyze_ingredients
from backend.services.allergy_service import compare_user_allergies
from backend.services.llm_service import answer_question


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "bmp", "avif"
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:page>")
def frontend_page(page):
    """Serve the small static frontend while keeping API routes explicit."""
    candidate = (FRONTEND_DIR / page).resolve()
    if FRONTEND_DIR not in candidate.parents or not candidate.is_file():
        return jsonify({"success": False, "message": "Page not found."}), 404
    return send_from_directory(FRONTEND_DIR, page)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "application": "NutriGuard AI",
        "status": "running"
    })


@app.route("/api/analyze", methods=["POST"])
def analyze_food():
    request_started = time.perf_counter()

    if "image" not in request.files:
        return jsonify({
            "success": False,
            "message": "Please upload a food label image."
        }), 400

    image = request.files["image"]

    if not image.filename:
        return jsonify({
            "success": False,
            "message": "No image selected."
        }), 400

    if not allowed_file(image.filename):
        return jsonify({
            "success": False,
            "message": "Unsupported image format."
        }), 400

    filename = secure_filename(image.filename)
    extension = filename.rsplit(".", 1)[1].lower()

    saved_name = f"{uuid.uuid4().hex}.{extension}"
    image_path = UPLOAD_DIR / saved_name

    try:
        image.save(image_path)
        try:
            with Image.open(image_path) as uploaded_image:
                uploaded_image.verify()
        except (UnidentifiedImageError, OSError) as error:
            app.logger.warning("Rejected invalid image after %.3fs", time.perf_counter() - request_started)
            return jsonify({
                "success": False,
                "message": "The uploaded file is not a readable image.",
            }), 400

        # Step 1: OCR
        app.logger.info("Starting OCR for %s", filename)
        ocr_result = extract_text_from_image(str(image_path))

        if not ocr_result["success"]:
            return jsonify({
                "success": False,
                "message": "Unable to extract text from this image.",
                "warnings": ocr_result.get("warnings", []),
            }), 422

        sections = ocr_result["sections"]

        # Step 2: Ingredient and allergen identification
        ingredient_started = time.perf_counter()
        ingredient_result = analyze_ingredients(
            sections.get("ingredients", ""),
            sections.get("contains", ""),
            sections.get("may_contain", "")
        )
        app.logger.info("Ingredient matching completed in %.3fs", time.perf_counter() - ingredient_started)

        # Step 3: User allergy profile
        allergies_text = request.form.get("allergies", "")
        if not allergies_text and request.form.get("allergy_profile"):
            allergies_text = request.form.get("allergy_profile", "")

        user_allergies = [
            item.strip()
            for item in allergies_text.split(",")
            if item.strip()
        ]

        allergy_started = time.perf_counter()
        allergy_result = compare_user_allergies(
            user_allergies,
            ingredient_result
        )
        app.logger.info("Allergy comparison completed in %.3fs", time.perf_counter() - allergy_started)

        return jsonify({
            "success": True,
            "ocr": {
                "raw_text": ocr_result["raw_text"],
                "sections": sections,
                "lines": ocr_result.get("lines", []),
                "detections": ocr_result.get("detections", []),
                "warnings": ocr_result.get("warnings", []),
                "image_width": ocr_result.get("image_width", 0),
                "image_height": ocr_result.get("image_height", 0)
            },
            "ingredient_analysis": ingredient_result,
            "allergy_analysis": allergy_result,
            "filename": filename,
            "duration_ms": round((time.perf_counter() - request_started) * 1000, 1),
            "message": "Food label analysis completed."
        })

    except Exception as error:
        app.logger.exception("Food analysis failed")

        return jsonify({
            "success": False,
            "message": "An error occurred during food analysis.",
        }), 500

    finally:
        app.logger.info(
            "Total analysis request time %.3fs",
            time.perf_counter() - request_started
        )
        if image_path.exists():
            image_path.unlink()


@app.route("/api/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    question = data.get("question", "").strip() if isinstance(data.get("question", ""), str) else ""

    if not question:
        return jsonify({
            "success": False,
            "message": "Please enter a question."
        }), 400

    try:
        result = answer_question(
            question,
            product_context=data.get("product_context")
        )
    except Exception:
        app.logger.exception("Chat request failed")
        return jsonify({
            "success": False,
            "message": "The knowledge assistant is temporarily unavailable."
        }), 503

    return jsonify({
        "success": True,
        "answer": result["answer"],
        "sources": result["sources"]
    })


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "success": False,
        "message": "Image is too large. Maximum size is 10 MB."
    }), 413


if __name__ == "__main__":
    print("\n===================================")
    print("       NUTRIGUARD AI")
    print("===================================")
    print("Server: http://127.0.0.1:5000")
    print("Health: http://127.0.0.1:5000/api/health")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
