import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from backend.services.ocr_service import (
    extract_sections_from_detections,
    extract_sections_from_text,
)


class OcrSectionTests(unittest.TestCase):
    def test_sections_use_detected_positions(self):
        detections = [
            {"text": "INGREDIENTS:", "confidence": 0.99, "coordinates": [[10, 10], [100, 10], [100, 30], [10, 30]]},
            {"text": "Wheat flour, sugar", "confidence": 0.99, "coordinates": [[10, 35], [180, 35], [180, 55], [10, 55]]},
            {"text": "MAY CONTAIN: SESAME", "confidence": 0.99, "coordinates": [[10, 70], [180, 70], [180, 90], [10, 90]]},
        ]
        sections, positioned = extract_sections_from_detections(detections, 200, 100)
        self.assertIn("Wheat flour", sections["ingredients"])
        self.assertEqual(sections["may_contain"], "SESAME")
        self.assertEqual(len(positioned), 3)

    def test_text_fallback_separates_complete_ocr_block(self):
        sections = extract_sections_from_text(
            "Nutrition Facts Calories 100 "
            "INGREDIENTS: Wheat flour, sugar "
            "CONTAINS: wheat MAY CONTAIN: sesame"
        )
        self.assertIn("Wheat flour", sections["ingredients"])
        self.assertEqual(sections["contains"], "wheat")
        self.assertEqual(sections["may_contain"], "sesame")

    def test_ocr_cache_reports_cache_hit_and_timing(self):
        from backend.services import ocr_service

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "label.png"
            path.write_bytes(b"test-image")
            fake = {
                "success": True,
                "raw_text": "INGREDIENTS: wheat",
                "lines": ["INGREDIENTS: wheat"],
                "detections": [],
                "warnings": [],
                "sections": {"ingredients": "wheat"},
                "image_width": 10,
                "image_height": 10,
            }
            ocr_service._ocr_cache.clear()
            with patch.object(
                ocr_service, "_ocr_cache", { "hash": fake }
            ):
                with patch("hashlib.sha256") as digest:
                    digest.return_value.hexdigest.return_value = "hash"
                    result = ocr_service.extract_text_from_image(path)
            self.assertTrue(result["cache_hit"])
            self.assertIn("total", result["timings_ms"])


if __name__ == "__main__":
    unittest.main()
