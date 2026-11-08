import unittest

from backend.services.allergy_service import compare_user_allergies
from backend.services.ingredient_service import analyze_ingredients


class AllergyMatchingTests(unittest.TestCase):
    def test_synonym_and_contains_matches_are_confirmed(self):
        analysis = analyze_ingredients(
            "Whey, Sugar",
            contains_text="MILK",
            may_contain_text="SESAME",
        )
        result = compare_user_allergies(["milk", "sesame"], analysis)
        self.assertEqual(result["results"][0]["status"], "MATCH_FOUND")
        self.assertEqual(
            result["results"][1]["status"],
            "POSSIBLE_CROSS_CONTAMINATION",
        )

    def test_no_match_is_not_safe_claim(self):
        result = compare_user_allergies(
            ["peanut"],
            {"review_required": True},
        )
        self.assertEqual(result["results"][0]["status"], "NO_MATCH_DETECTED")
        self.assertIn("does not establish", result["safety_note"])

    def test_ins_number_is_recognized(self):
        result = analyze_ingredients("Monosodium glutamate (INS 621)")
        self.assertEqual(result["additive_codes"][0]["code"], "621")


if __name__ == "__main__":
    unittest.main()
