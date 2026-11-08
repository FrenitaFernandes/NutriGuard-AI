import unittest

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


if __name__ == "__main__":
    unittest.main()
