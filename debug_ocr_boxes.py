
from pathlib import Path
from PIL import Image, ImageDraw
from backend.services.ocr_service import extract_text_from_image

image_path = Path("data/uploads/food_label.avif")

print("Running OCR to get text coordinates...")

result = extract_text_from_image(str(image_path))

if not result["success"]:
    print("OCR failed:", result.get("message"))
    raise SystemExit

image = Image.open(image_path).convert("RGB")
draw = ImageDraw.Draw(image)

detections = result["detections"]

for i, item in enumerate(detections):
    coordinates = item.get("coordinates")

    if not coordinates:
        continue

    points = [tuple(point) for point in coordinates]

    draw.polygon(points, outline="red", width=2)

    x, y = points[0]
    draw.text((x, max(0, y - 14)), str(i + 1), fill="blue")

output_path = Path("data/uploads/food_label_ocr_boxes.jpg")
image.save(output_path)

print("\nOCR box visualization saved successfully!")
print("Output:", output_path)

print("\nDETECTED TEXT REGIONS:")

for i, item in enumerate(detections):
    print(
        f"{i + 1}. {item['text']} "
        f"| Confidence: {item['confidence']:.2f}"
    )
