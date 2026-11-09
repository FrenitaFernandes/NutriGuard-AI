import hashlib
import json
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, send_file
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
import pillow_avif

from backend.services.allergy_service import compare_user_allergies
from backend.services.ingredient_service import analyze_ingredients
from backend.services.llm_service import answer_question
from backend.services.ocr_service import extract_text_from_image
from backend.services.pdf_service import render_pdf_pages
from backend.storage import (
    add_message,
    clear_current_product,
    create_session,
    ensure_session,
    get_current_product,
    get_messages,
    initialize_database,
    create_analysis_job,
    get_analysis_job,
    update_analysis_job,
    save_product,
)


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "avif", "pdf"}
IMAGE_EXTENSIONS = ALLOWED_EXTENSIONS - {"pdf"}
SESSION_COOKIE = "nutriguard_session"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "0") == "1"
initialize_database()
OCR_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nutriguard-ocr")


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def current_session():
    session_id = ensure_session(request.cookies.get(SESSION_COOKIE))
    request.nutriguard_session_id = session_id
    return session_id


@app.after_request
def set_session_cookie(response):
    session_id = getattr(request, "nutriguard_session_id", None)
    if session_id:
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=app.config["SESSION_COOKIE_SECURE"],
            samesite="Lax",
        )
    return response


def aggregate_ocr(results):
    sections = {
        "ingredients": "",
        "contains": "",
        "may_contain": "",
        "nutrition": "",
    }
    raw_lines = []
    warnings = []
    detections = []
    width = height = 0
    for result in results:
        if not result.get("success"):
            continue
        width = max(width, result.get("image_width", 0))
        height += result.get("image_height", 0)
        raw_lines.extend(result.get("lines", []))
        warnings.extend(result.get("warnings", []))
        detections.extend(result.get("detections", []))
        for name, value in result.get("sections", {}).items():
            if name in sections and value and not sections[name]:
                sections[name] = value
    raw_text = "\n".join(raw_lines)
    return {
        "success": bool(raw_text),
        "raw_text": raw_text,
        "lines": raw_lines,
        "detections": detections,
        "warnings": list(dict.fromkeys(warnings)),
        "image_width": width,
        "image_height": height,
        "sections": {"raw_text": raw_text, "cleaned_text": raw_text, **sections},
    }


def run_ocr(source_path, extension):
    if extension != "pdf":
        return extract_text_from_image(str(source_path))
    with tempfile.TemporaryDirectory(prefix="nutriguard-pdf-") as directory:
        pages = render_pdf_pages(source_path, directory)
        return aggregate_ocr(
            [extract_text_from_image(str(page)) for page in pages]
        )


def product_payload(filename, ocr_result, ingredient_result, allergy_result,
                    duration_ms, product_id=None, preview_url=None):
    return {
        "success": True,
        "product_id": product_id,
        "filename": filename,
        "preview_url": preview_url,
        "ocr": {
            "raw_text": ocr_result["raw_text"],
            "sections": ocr_result["sections"],
            "lines": ocr_result.get("lines", []),
            "detections": ocr_result.get("detections", []),
            "warnings": ocr_result.get("warnings", []),
            "image_width": ocr_result.get("image_width", 0),
            "image_height": ocr_result.get("image_height", 0),
            "cache_hit": ocr_result.get("cache_hit", False),
            "timings_ms": ocr_result.get("timings_ms", {}),
        },
        "ingredient_analysis": ingredient_result,
        "allergy_analysis": allergy_result,
        "duration_ms": round(duration_ms, 1),
        "message": "Food label analysis completed.",
    }


def process_analysis(session_id, source_path, filename, extension, source_hash,
                     allergies_text, started):
    existing = get_current_product(session_id)
    if existing and existing["source_hash"] == source_hash:
        if source_path.is_file():
            source_path.unlink()
        return existing["payload"] | {
            "product_id": existing["id"],
            "preview_url": f"/api/product/{existing['id']}/preview",
            "message": "This label is already analyzed.",
        }

    if extension in IMAGE_EXTENSIONS:
        try:
            with Image.open(source_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("The uploaded file is not a readable image.") from error
        preview_name = source_path.name
    else:
        with tempfile.TemporaryDirectory(prefix="nutriguard-preview-") as directory:
            preview = render_pdf_pages(source_path, directory)[0]
            preview_name = f"{uuid.uuid4().hex}.png"
            shutil.copyfile(preview, UPLOAD_DIR / preview_name)

    ocr_result = run_ocr(source_path, extension)
    if not ocr_result.get("success"):
        raise ValueError("Unable to extract text from this label.")

    sections = ocr_result["sections"]
    ingredient_result = analyze_ingredients(
        sections.get("ingredients", ""),
        sections.get("contains", ""),
        sections.get("may_contain", ""),
        sections.get("nutrition", ""),
    )
    user_allergies = [
        item.strip() for item in allergies_text.split(",") if item.strip()
    ]
    allergy_result = compare_user_allergies(user_allergies, ingredient_result)
    payload = product_payload(
        filename, ocr_result, ingredient_result, allergy_result,
        (time.perf_counter() - started) * 1000,
    )
    row = save_product(
        session_id, source_hash, filename, source_path.name, preview_name, payload
    )
    payload["product_id"] = row["id"]
    payload["preview_url"] = f"/api/product/{row['id']}/preview"
    return payload


def run_analysis_job(job_id, session_id, source_path, filename, extension,
                     source_hash, allergies_text):
    started = time.perf_counter()
    completed = False
    update_analysis_job(job_id, session_id, "processing")
    try:
        result = process_analysis(
            session_id, source_path, filename, extension, source_hash,
            allergies_text, started,
        )
        update_analysis_job(job_id, session_id, "completed", result=result)
        completed = True
    except ValueError as error:
        update_analysis_job(job_id, session_id, "failed", error=str(error))
    except Exception:
        app.logger.exception("Background food analysis failed")
        update_analysis_job(
            job_id, session_id, "failed",
            error="An error occurred during food analysis.",
        )
    finally:
        if (extension == "pdf" or not completed) and source_path.is_file():
            source_path.unlink()


@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:page>")
def frontend_page(page):
    candidate = (FRONTEND_DIR / page).resolve()
    if FRONTEND_DIR not in candidate.parents or not candidate.is_file():
        return jsonify({"success": False, "message": "Page not found."}), 404
    return send_from_directory(FRONTEND_DIR, page)


@app.route("/api/health")
def health():
    current_session()
    return jsonify({"success": True, "application": "NutriGuard AI", "status": "running"})


@app.route("/api/product", methods=["GET"])
def current_product():
    session_id = current_session()
    product = get_current_product(session_id)
    if not product:
        return jsonify({"success": True, "product": None, "messages": []})
    payload = product["payload"]
    payload["product_id"] = product["id"]
    payload["preview_url"] = f"/api/product/{product['id']}/preview"
    return jsonify({"success": True, "product": payload, "messages": get_messages(session_id, product["id"])})


@app.route("/api/product/<int:product_id>/preview")
def product_preview(product_id):
    session_id = current_session()
    product = get_current_product(session_id)
    if not product or product["id"] != product_id:
        return jsonify({"success": False, "message": "Product not found."}), 404
    path = UPLOAD_DIR / product["preview_filename"]
    if not path.is_file():
        return jsonify({"success": False, "message": "Preview not found."}), 404
    return send_file(path)


@app.route("/api/product/current", methods=["DELETE"])
def delete_current_product():
    session_id = current_session()
    product = get_current_product(session_id)
    clear_current_product(session_id)
    if product:
        for name in (product["stored_filename"], product["preview_filename"]):
            path = UPLOAD_DIR / name
            if path.is_file():
                path.unlink()
    return jsonify({"success": True})


@app.route("/api/analyze", methods=["POST"])
def analyze_food():
    started = time.perf_counter()
    session_id = current_session()
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return jsonify({"success": False, "message": "Please upload a food label."}), 400
    if not allowed_file(upload.filename):
        return jsonify({"success": False, "message": "Unsupported image or PDF format."}), 400

    filename = secure_filename(upload.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    source_path = UPLOAD_DIR / stored_name
    upload.save(source_path)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    allergies_text = request.form.get("allergies", "") or request.form.get("allergy_profile", "")
    if request.form.get("background") == "1":
        job_id = uuid.uuid4().hex
        create_analysis_job(session_id, job_id)
        OCR_EXECUTOR.submit(
            run_analysis_job, job_id, session_id, source_path, filename,
            extension, source_hash, allergies_text,
        )
        return jsonify({
            "success": True,
            "status": "queued",
            "job_id": job_id,
            "message": "Label queued for OCR.",
        }), 202

    completed = False
    try:
        result = process_analysis(
            session_id, source_path, filename, extension, source_hash,
            allergies_text, started,
        )
        completed = True
        return jsonify(result)
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 422
    except Exception:
        app.logger.exception("Food analysis failed")
        return jsonify({"success": False, "message": "An error occurred during food analysis."}), 500
    finally:
        if source_path.is_file() and (extension == "pdf" or not completed):
            source_path.unlink()


@app.route("/api/analyze/status/<job_id>")
def analysis_status(job_id):
    session_id = current_session()
    job = get_analysis_job(job_id, session_id)
    if not job:
        return jsonify({"success": False, "message": "Analysis job not found."}), 404
    response = {
        "success": True,
        "status": job["status"],
        "job_id": job["id"],
        "error": job["error"],
    }
    if job["status"] == "completed":
        response["result"] = job["result"]
    return jsonify(response)


@app.route("/api/chat", methods=["POST"])
def chat():
    session_id = current_session()
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip() if isinstance(data.get("question", ""), str) else ""
    if not question:
        return jsonify({"success": False, "message": "Please enter a question."}), 400
    product = get_current_product(session_id)
    if not product:
        return jsonify({"success": False, "message": "Scan a product before starting a product chat."}), 409
    history = get_messages(session_id, product["id"])
    context = product["payload"]
    try:
        result = answer_question(
            question,
            product_context=context,
            conversation_history=history,
        )
        if result.get("error"):
            return jsonify({"success": False, "message": result["error"]}), 503
    except Exception:
        app.logger.exception("Chat request failed")
        return jsonify({"success": False, "message": "The knowledge assistant is temporarily unavailable."}), 503
    add_message(session_id, product["id"], "user", question)
    add_message(session_id, product["id"], "assistant", result["answer"], result.get("sources", []))
    return jsonify({
        "success": True,
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "mode": result.get("mode"),
        "provenance": result.get("provenance", {}),
    })


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({"success": False, "message": "File is too large. Maximum size is 20 MB."}), 413


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
        use_reloader=False,
    )
