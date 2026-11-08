import io
import unittest
from unittest.mock import patch

from PIL import Image

from app import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_health_and_validation(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.post("/api/analyze").status_code, 400)
        response = self.client.post(
            "/api/analyze",
            data={"image": (io.BytesIO(b"not an image"), "label.exe")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.extract_text_from_image")
    def test_analysis_response_contract(self, extract_text):
        extract_text.return_value = {
            "success": True,
            "raw_text": "INGREDIENTS: Whey",
            "lines": ["INGREDIENTS: Whey"],
            "detections": [],
            "warnings": [],
            "image_width": 10,
            "image_height": 10,
            "sections": {
                "ingredients": "Whey",
                "contains": "",
                "may_contain": "",
                "nutrition": "",
            },
        }
        image_bytes = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(image_bytes, format="PNG")
        image_bytes.seek(0)
        response = self.client.post(
            "/api/analyze",
            data={"image": (image_bytes, "label.png"), "allergies": "milk"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertIn("warnings", body["ocr"])


if __name__ == "__main__":
    unittest.main()
