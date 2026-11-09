import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.services import llm_service


class LlmRoutingTests(unittest.TestCase):
    def setUp(self):
        self.response = SimpleNamespace(text="A concise answer.")
        self.generate_content = MagicMock(return_value=self.response)
        self.fake_client = SimpleNamespace(
            models=SimpleNamespace(generate_content=self.generate_content)
        )
        self.product = {
            "filename": "label.png",
            "ingredient_analysis": {
                "original_ingredient_text": "Whey, sugar",
                "nutrition": {"energy": {"value": "100", "unit": "kcal"}},
            },
        }

    @patch.object(llm_service, "search_documents")
    def test_general_question_does_not_retrieve_documents(self, search):
        with patch.object(llm_service, "client", self.fake_client):
            result = llm_service.answer_question("What is whey?")
        search.assert_not_called()
        self.assertEqual(result["mode"], "general")
        self.assertFalse(result["sources"])

    @patch.object(llm_service, "search_documents", return_value=[])
    def test_product_question_uses_product_context(self, search):
        with patch.object(llm_service, "client", self.fake_client):
            result = llm_service.answer_question(
                "Does this product contain milk?",
                product_context=self.product,
                conversation_history=[{"role": "user", "content": "Hello"}],
            )
        search.assert_not_called()
        self.assertEqual(result["mode"], "product")
        self.assertTrue(result["provenance"]["product_facts"])

    @patch.object(
        llm_service,
        "search_documents",
        return_value=[
            {
                "text": "FSSAI labelling declaration requirements",
                "semantic_score": 0.4,
                "metadata": {"source": "packaging_labelling.pdf", "page": 4},
            },
            {
                "text": "Unrelated additive discussion",
                "semantic_score": 0.2,
                "metadata": {"source": "food_additives.pdf", "page": 7},
            },
        ],
    )
    def test_regulatory_question_filters_unrelated_documents(self, search):
        with patch.object(llm_service, "client", self.fake_client):
            result = llm_service.answer_question(
                "What are FSSAI labelling requirements?"
            )
        self.assertEqual(result["mode"], "regulatory")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["page"], 4)
        self.assertIn("fssai.gov.in", result["sources"][0]["url"])

    @patch.object(llm_service, "search_documents", return_value=[])
    def test_follow_up_is_sent_with_history(self, search):
        with patch.object(llm_service, "client", self.fake_client):
            llm_service.answer_question(
                "How much should I eat?",
                product_context=self.product,
                conversation_history=[
                    {"role": "user", "content": "What is whey?"},
                    {"role": "assistant", "content": "It is a milk protein."},
                ],
            )
        prompt = self.generate_content.call_args.kwargs["contents"]
        self.assertEqual(search.call_count, 0)
        self.assertIn("What is whey?", prompt)
        self.assertIn("It is a milk protein.", prompt)


if __name__ == "__main__":
    unittest.main()
