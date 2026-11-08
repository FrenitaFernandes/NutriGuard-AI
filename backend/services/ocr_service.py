
import os
import re
import tempfile
import time
import logging
import hashlib
from copy import deepcopy

import pillow_avif
from PIL import Image, ImageOps, ImageEnhance
from paddleocr import PaddleOCR


logger = logging.getLogger(__name__)
_ocr_cache = {}
_OCR_CACHE_LIMIT = 4


# Keep the model lightweight for CPU-only demonstrations. The model remains
# initialized once per Flask process and is reused for every upload.
ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    # oneDNN is not compatible with the installed Paddle runtime on some
    # Windows machines, so keep it disabled for reliability.
    enable_mkldnn=False,
    text_det_limit_side_len=800,
    text_det_limit_type="max",
    text_recognition_batch_size=1,
)


def prepare_image_for_ocr(image):
    """
    Prepare images of different dimensions for OCR.
    Coordinates are converted back to the original image afterward.
    """

    original_width, original_height = image.size

    # Avoid expensive super-resolution-like upscaling while retaining enough
    # pixels for small label text.
    longest_side = max(original_width, original_height)

    if longest_side < 640:
        scale = 640 / longest_side
    elif longest_side > 1200:
        scale = 1200 / longest_side
    else:
        scale = 1.0

    if scale != 1.0:
        new_size = (
            max(1, int(original_width * scale)),
            max(1, int(original_height * scale))
        )
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    # Mild enhancement without aggressively changing text.
    image = ImageEnhance.Contrast(image).enhance(1.15)
    image = ImageEnhance.Sharpness(image).enhance(1.2)

    return image, scale


def get_box_bounds(coordinates):
    """Convert OCR polygon or rectangle coordinates into bounds."""

    if coordinates is None:
        return None

    try:
        if hasattr(coordinates, "tolist"):
            coordinates = coordinates.tolist()

        # Polygon: [[x1,y1], [x2,y2], ...]
        if (
            isinstance(coordinates, list)
            and coordinates
            and isinstance(coordinates[0], (list, tuple))
        ):
            xs = [float(point[0]) for point in coordinates]
            ys = [float(point[1]) for point in coordinates]

            return min(xs), min(ys), max(xs), max(ys)

        # Rectangle: [x1, y1, x2, y2]
        if len(coordinates) >= 4:
            return (
                float(coordinates[0]),
                float(coordinates[1]),
                float(coordinates[2]),
                float(coordinates[3])
            )

    except (TypeError, ValueError, IndexError):
        pass

    return None


def identify_heading(text):
    """Identify important food-label section headings."""

    patterns = [
        ("may_contain", r"\bMAY\s+CONTAIN(?:S)?\b"),
        ("contains", r"\bCONTAINS?\b"),
        ("ingredients", r"\bINGREDIENTS?\b"),
        (
            "nutrition",
            r"\b(?:NUTRITION\s+FACTS|NUTRITION\s+INFORMATION|"
            r"NUTRITIONAL\s+INFORMATION)\b"
        )
    ]

    for section, pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return section, match

    return None, None


def extract_sections_from_text(raw_text):
    """Fallback section extraction from OCR text when box geometry is incomplete."""
    sections = {
        "ingredients": "",
        "contains": "",
        "may_contain": "",
        "nutrition": "",
    }
    matches = []
    heading_pattern = re.compile(
        r"\b(MAY\s+CONTAINS?|CONTAINS?|INGREDIENTS?|"
        r"NUTRITION\s+FACTS|NUTRITION\s+INFORMATION|"
        r"NUTRITIONAL\s+INFORMATION)\b\s*:?",
        re.IGNORECASE,
    )
    section_names = {
        "ingredients": "ingredients",
        "ingredient": "ingredients",
        "contains": "contains",
        "contain": "contains",
        "may contain": "may_contain",
        "may contains": "may_contain",
        "nutrition facts": "nutrition",
        "nutrition information": "nutrition",
        "nutritional information": "nutrition",
    }
    for match in heading_pattern.finditer(raw_text or ""):
        heading = re.sub(r"\s+", " ", match.group(1).lower()).strip()
        matches.append((section_names.get(heading), match.start(), match.end()))

    for index, (section, start, end) in enumerate(matches):
        if not section:
            continue
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(raw_text)
        content = raw_text[end:next_start].strip(" \t\r\n:,-")
        if content and not sections[section]:
            sections[section] = re.sub(r"\s+", " ", content).strip()
    return sections


def extract_sections_from_detections(detections, image_width, image_height):
    """
    Extract label sections using OCR positions rather than fixed crops.
    Uses image-relative horizontal distances.
    """

    sections = {
        "ingredients": "",
        "contains": "",
        "may_contain": "",
        "nutrition": ""
    }

    positioned = []

    for detection in detections:
        bounds = get_box_bounds(detection.get("coordinates"))

        if not bounds:
            continue

        x1, y1, x2, y2 = bounds

        positioned.append({
            **detection,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "center_x": (x1 + x2) / 2,
            "center_y": (y1 + y2) / 2
        })

    # Reading order: top to bottom, then left to right.
    positioned.sort(key=lambda item: (item["center_y"], item["x1"]))

    headings = []

    for item in positioned:
        section, match = identify_heading(item["text"])

        if section:
            headings.append({
                "section": section,
                "item": item,
                "match": match
            })

    headings.sort(key=lambda item: item["item"]["y1"])

    # Each heading defines the beginning of a section.
    for index, heading in enumerate(headings):

        section_name = heading["section"]
        anchor = heading["item"]
        match = heading["match"]

        next_heading_y = (
            headings[index + 1]["item"]["y1"]
            if index + 1 < len(headings)
            else image_height
        )

        # Dynamic horizontal tolerance based on image dimensions.
        horizontal_tolerance = image_width * 0.35

        content_lines = []

        # Include text appearing after the heading in the same OCR box.
        inline_content = anchor["text"][match.end():].strip()
        inline_content = inline_content.lstrip(" :,-")

        if inline_content:
            content_lines.append(inline_content)

        for item in positioned:

            if item is anchor:
                continue

            # Ignore text above this heading or beyond the next section.
            if item["center_y"] < anchor["y2"] - 2:
                continue

            if item["y1"] >= next_heading_y:
                continue

            # Keep nearby text from the same likely label region.
            if abs(item["center_x"] - anchor["center_x"]) > horizontal_tolerance:
                continue

            # Do not include another section heading.
            other_section, _ = identify_heading(item["text"])

            if other_section:
                continue

            content_lines.append(item["text"])

        # Do not overwrite an earlier section with an empty result.
        section_text = " ".join(content_lines).strip()

        if section_text and not sections[section_name]:
            sections[section_name] = section_text

    return sections, positioned


def extract_text_from_image(image_path):
    """Extract text and label sections from a complete food image."""

    temp_path = None
    started = time.perf_counter()

    try:
        with open(image_path, "rb") as image_file:
            image_hash = hashlib.sha256(image_file.read()).hexdigest()
        cached_result = _ocr_cache.get(image_hash)
        if cached_result is not None:
            logger.info("OCR cache hit in %.3fs", time.perf_counter() - started)
            return deepcopy(cached_result)

        image_started = time.perf_counter()
        image = Image.open(image_path)
        image = ImageOps.exif_transpose(image).convert("RGB")

        original_width, original_height = image.size
        logger.info("OCR image loaded in %.3fs (%sx%s)", time.perf_counter() - image_started, original_width, original_height)

        preprocessing_started = time.perf_counter()
        processed_image, scale = prepare_image_for_ocr(image)

        with tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False
        ) as temp:
            temp_path = temp.name

        processed_image.save(temp_path, format="JPEG", quality=95)
        logger.info("OCR preprocessing completed in %.3fs", time.perf_counter() - preprocessing_started)

        ocr_started = time.perf_counter()
        logger.info("Running PaddleOCR on the complete image...")
        results = ocr.predict(temp_path)
        logger.info("PaddleOCR inference completed in %.3fs", time.perf_counter() - ocr_started)

        detections = []

        for result in results:

            result_data = result.json

            if callable(result_data):
                result_data = result_data()

            data = result_data.get("res", result_data)

            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            polygons = data.get("rec_polys", [])
            boxes = data.get("rec_boxes", [])

            for i, text in enumerate(texts):

                text = str(text).strip()

                if not text:
                    continue

                confidence = (
                    float(scores[i])
                    if i < len(scores)
                    else 0.0
                )

                coordinates = None

                if i < len(polygons):
                    coordinates = polygons[i]
                elif i < len(boxes):
                    coordinates = boxes[i]

                if hasattr(coordinates, "tolist"):
                    coordinates = coordinates.tolist()

                # Convert OCR coordinates to original image coordinates.
                if coordinates is not None and scale != 0:
                    if (
                        isinstance(coordinates, list)
                        and coordinates
                        and isinstance(coordinates[0], (list, tuple))
                    ):
                        coordinates = [
                            [
                                round(float(point[0]) / scale, 2),
                                round(float(point[1]) / scale, 2)
                            ]
                            for point in coordinates
                        ]
                    else:
                        coordinates = [
                            round(float(value) / scale, 2)
                            for value in coordinates
                        ]

                detections.append({
                    "text": text,
                    "confidence": confidence,
                    "coordinates": coordinates
                })

        extraction_started = time.perf_counter()
        # Sort OCR text spatially for readable output.
        sections, positioned = extract_sections_from_detections(
            detections,
            original_width,
            original_height
        )

        raw_lines = [item["text"] for item in detections]
        raw_text = "\n".join(raw_lines)
        text_sections = extract_sections_from_text(raw_text)
        for section_name, section_text in text_sections.items():
            # When OCR returns a complete text block, heading boundaries are
            # more reliable than geometry assembled from unrelated columns.
            if section_text:
                sections[section_name] = section_text

        # Detect text boxes touching the image boundary.
        edge_warnings = []

        for item in positioned:
            if (
                item["x1"] <= original_width * 0.01
                or item["y1"] <= original_height * 0.01
                or item["x2"] >= original_width * 0.99
                or item["y2"] >= original_height * 0.99
            ):
                edge_warnings.append(
                    "Some detected text is close to the image boundary. "
                    "It may be clipped."
                )
                break

        warnings = list(edge_warnings)
        low_confidence_count = sum(
            1 for item in detections if item["confidence"] and item["confidence"] < 0.55
        )
        if low_confidence_count:
            warnings.append(
                f"{low_confidence_count} OCR text region(s) have low confidence; "
                "review the original image."
            )
        if not raw_lines:
            warnings.append(
                "No readable text was detected. Upload a clearer, well-lit image."
            )

        if not sections["ingredients"]:
            warnings.append("Ingredients section was not detected.")
        elif "ingredient" in raw_text.lower() and not text_sections["ingredients"]:
            warnings.append(
                "An ingredient heading was detected but its text could not be separated."
            )

        if not sections["contains"] and not sections["may_contain"]:
            warnings.append(
                "No allergen declaration was detected. "
                "This does not mean the product is allergen-free."
            )
        logger.info("OCR text extraction completed in %.3fs", time.perf_counter() - extraction_started)
        logger.info("Total OCR processing time %.3fs", time.perf_counter() - started)

        result = {
            "success": True,
            "image_width": original_width,
            "image_height": original_height,
            "raw_text": raw_text,
            "lines": raw_lines,
            "detections": detections,
            "sections": {
                "raw_text": raw_text,
                "cleaned_text": raw_text,
                **sections
            },
            "warnings": list(dict.fromkeys(warnings)),
            "message": "OCR completed successfully."
        }
        _ocr_cache[image_hash] = result
        while len(_ocr_cache) > _OCR_CACHE_LIMIT:
            _ocr_cache.pop(next(iter(_ocr_cache)))
        return deepcopy(result)

    except Exception as e:

        return {
            "success": False,
            "image_width": 0,
            "image_height": 0,
            "raw_text": "",
            "lines": [],
            "detections": [],
            "sections": {},
            "warnings": [],
            "message": str(e)
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
