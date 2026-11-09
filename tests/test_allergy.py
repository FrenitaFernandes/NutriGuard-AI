import unittest

from backend.services.allergy_service import compare_user_allergies
from backend.services.ingredient_service import (
    analyze_ingredients,
    parse_nutrition,
)


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

    def test_explicit_nutrition_values_are_structured(self):
        result = parse_nutrition(
            "Serving Size: 30 g Energy: 120 kcal Protein: 4 g "
            "Total Sugars: 6 g Total Fat: 2 g Saturated Fat: 1 g "
            "Carbohydrates: 20 g Sodium: 80 mg per serving"
        )
        self.assertEqual(result["serving_size"]["value"], "30")
        self.assertEqual(result["serving_size"]["unit"], "g")
        self.assertEqual(result["energy"]["unit"], "kcal")
        self.assertEqual(result["sodium"]["value"], "80")
        self.assertEqual(result["sugar"]["value"], "6")
        self.assertEqual(result["fat"]["value"], "2")
        self.assertEqual(result["saturated_fat"]["value"], "1")
        self.assertEqual(result["carbohydrates"]["unit"], "g")
        self.assertEqual(result["energy"]["basis"], "serving")

    def test_missing_units_are_not_displayed_as_values(self):
        result = parse_nutrition("Calories 120 Protein 4")
        self.assertNotIn("energy", result)
        self.assertNotIn("protein", result)

    def test_reference_database_explains_multiple_additives(self):
        result = analyze_ingredients(
            "INS 211, INS 415, E955",
        )
        codes = {item["code"]: item for item in result["additive_codes"]}
        self.assertEqual(codes["211"]["ingredient"], "Sodium benzoate")
        self.assertEqual(codes["415"]["category"], "Thickener and stabiliser")
        self.assertTrue(codes["955"]["purpose"])
        self.assertTrue(all(item["reference_match"] for item in codes.values()))

    def test_guidance_does_not_set_universal_threshold(self):
        result = analyze_ingredients("", nutrition_text="Energy 120 kcal")
        self.assertIn("serving size was not extracted", result["consumption_guidance"]["summary"])
        result = analyze_ingredients("", nutrition_text="Energy 120 kcal Protein 4 g")
        self.assertIn("does not set a universal safe amount", result["consumption_guidance"]["summary"])


if __name__ == "__main__":
    unittest.main()
