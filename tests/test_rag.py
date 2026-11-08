import unittest

from backend.rag.retriever import BM25Search, expand_query


class RagTests(unittest.TestCase):
    def test_query_expansion_and_keyword_retrieval(self):
        self.assertIn("621", expand_query("What is MSG?"))
        search = BM25Search([
            {"page_content": "Monosodium glutamate INS 621 labelling", "metadata": {}},
            {"page_content": "Packaging material", "metadata": {}},
        ])
        self.assertEqual(search.search("MSG")[0][0], 0)


if __name__ == "__main__":
    unittest.main()
