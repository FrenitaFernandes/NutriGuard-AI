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

    @patch("app.extract_text_from_image")
    def test_sessions_have_separate_current_products(self, extract_text):
        extract_text.return_value = {
            "success": True,
            "raw_text": "INGREDIENTS: Whey",
            "lines": ["INGREDIENTS: Whey"],
            "detections": [],
            "warnings": [],
            "image_width": 10,
            "image_height": 10,
            "sections": {"ingredients": "Whey", "contains": "", "may_contain": "", "nutrition": ""},
        }
        first = self.client
        second = app.test_client()
        image_bytes = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(image_bytes, format="PNG")
        image = image_bytes.getvalue()
        response = first.post(
            "/api/analyze",
            data={"image": (io.BytesIO(image), "session-a.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(second.get("/api/product").get_json()["product"])
        self.assertIsNotNone(first.get("/api/product").get_json()["product"])

    @patch("app.OCR_EXECUTOR.submit")
    def test_background_analysis_returns_job_status(self, submit):
        submit.side_effect = lambda _target, _job_id, _session_id, source_path, *_args: source_path.unlink()
        response = self.client.post(
            "/api/analyze",
            data={"image": (io.BytesIO(b"label bytes"), "label.png"), "background": "1"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertEqual(body["status"], "queued")
        self.assertTrue(submit.called)
        status = self.client.get(f"/api/analyze/status/{body['job_id']}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["status"], "queued")


if __name__ == "__main__":
    unittest.main()
