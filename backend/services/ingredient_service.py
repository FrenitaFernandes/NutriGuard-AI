
import csv
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = PROJECT_ROOT / "data" / "ingredient_reference"


def load_ingredient_database():
    """Load ingredient, allergen and synonym reference files."""

    with open(
        REFERENCE_DIR / "ingredients.csv",
        "r",
        encoding="utf-8-sig"
    ) as file:
        ingredients = list(csv.DictReader(file))

    with open(
        REFERENCE_DIR / "allergens.json",
        "r",
        encoding="utf-8"
    ) as file:
        allergens = json.load(file).get("allergens", [])

    with open(
        REFERENCE_DIR / "synonyms.json",
        "r",
        encoding="utf-8"
    ) as file:
        synonyms = json.load(file)

    return ingredients, allergens, synonyms


def normalize_text(text):
    """Normalize text for comparison."""

    text = text.lower()
    text = re.sub(r"[()]", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*%", " ", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _terms_for_reference(name, synonyms):
    terms = [name]
    normalized_name = normalize_text(name)
    for key, values in synonyms.items():
        if normalize_text(key) == normalized_name:
            terms.extend(values)
    return list(dict.fromkeys(terms))


def find_allergen_matches(text, allergens):
    """Match allergens using declared names and synonyms."""

    normalized = normalize_text(text)
    matches = []

    for allergen in allergens:

        for synonym in allergen.get("synonyms", []):

            term = normalize_text(synonym)

            if not term:
                continue

            pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"

            if re.search(pattern, normalized):

                matches.append({
                    "allergen": allergen["name"],
                    "matched_term": synonym
                })

                break

    return matches


def match_ingredients(text, ingredients, synonyms):
    """Find known ingredients using names and synonyms."""

    normalized = normalize_text(text)
    matches = []

    for item in ingredients:

        name = item.get("ingredient", "").strip()

        if not name:
            continue

        terms = _terms_for_reference(name, synonyms)

        for term in terms:

            normalized_term = normalize_text(term)

            if not normalized_term:
                continue

            pattern = (
                r"(?<!\w)"
                + re.escape(normalized_term)
                + r"(?!\w)"
            )

            if re.search(pattern, normalized):

                matches.append({
                    "ingredient": name,
                    "matched_term": term,
                    "category": item.get("category", ""),
                    "allergen": item.get("allergen", ""),
                    "description": item.get("description", ""),
                    "alternative_names": [
                        synonym for synonym in terms
                        if normalize_text(synonym) != normalize_text(name)
                    ]
                })

                break

    return matches


def find_additive_codes(text, ingredients):
    """Find explicit INS/E-number declarations without guessing their identity."""
    normalized = normalize_text(text)
    codes = set(re.findall(r"\b(?:INS|E)\s*[- ]?\s*(\d{3,4}[a-z]?)\b", normalized, re.I))
    known_additives = {
        "621": ("Monosodium glutamate", "Flavour enhancer"),
        "627": ("Disodium guanylate", "Flavour enhancer"),
        "631": ("Disodium inosinate", "Flavour enhancer"),
        "330": ("Citric acid", "Acidity regulator"),
        "322": ("Lecithins", "Emulsifier"),
    }
    matches = []
    matched_codes = set()
    for item in ingredients:
        code = item.get("ins_number", "").strip()
        if code and code.lower().replace(" ", "") in {
            value.lower().replace(" ", "") for value in codes
        }:
            matches.append({
                "ingredient": item.get("ingredient", ""),
                "code": code,
                "category": item.get("category", ""),
                "matched_term": code,
                "description": item.get("description", "")
            })
            matched_codes.add(code.lower().replace(" ", ""))
    for code in codes:
        normalized_code = code.lower().replace(" ", "")
        if normalized_code in known_additives and normalized_code not in matched_codes:
            name, category = known_additives[normalized_code]
            matches.append({
                "ingredient": name,
                "code": code,
                "category": category,
                "matched_term": code,
                "reference_match": True,
                "description": {
                    "621": "A flavour enhancer that brings out savoury taste.",
                    "627": "A flavour enhancer used to strengthen savoury taste.",
                    "631": "A flavour enhancer used with other savoury flavour enhancers.",
                    "330": "Citric acid, used to add acidity and help control taste.",
                    "322": "Lecithins, used to help oil and water mix smoothly."
                }[normalized_code]
            })
    return matches


def find_unmatched_words(text, matches):
    """Return words for manual review, not automatic correction."""

    normalized = normalize_text(text)

    matched_terms = []

    for item in matches:
        matched_terms.extend([
            normalize_text(item["ingredient"]),
            normalize_text(item["matched_term"])
        ])

    # This is a simple review aid, not a complete ingredient parser.
    words = normalized.split()

    return [
        word for word in words
        if len(word) >= 4
        and not any(word in term.split() for term in matched_terms)
        and not word.isdigit()
    ]


def analyze_ingredients(
    ingredient_text,
    contains_text="",
    may_contain_text=""
):
    """Analyze ingredients and allergen declarations separately."""

    ingredients, allergens, synonyms = load_ingredient_database()

    ingredient_matches = match_ingredients(
        ingredient_text,
        ingredients,
        synonyms
    )
    additive_codes = find_additive_codes(ingredient_text, ingredients)

    ingredient_allergens = find_allergen_matches(
        ingredient_text,
        allergens
    )

    declared_allergens = find_allergen_matches(
        contains_text,
        allergens
    )

    possible_allergens = find_allergen_matches(
        may_contain_text,
        allergens
    )

    unmatched_words = find_unmatched_words(
        ingredient_text,
        ingredient_matches
    )

    return {
        "ingredient_matches": ingredient_matches,
        "additive_codes": additive_codes,
        "ingredient_allergens": ingredient_allergens,
        "contains_allergens": declared_allergens,
        "may_contain_allergens": possible_allergens,
        "unmatched_words_for_review": unmatched_words,
        "original_ingredient_text": ingredient_text,
        "review_required": (
            not bool(ingredient_text)
            or bool(unmatched_words)
            or bool(additive_codes) and not all(
                item.get("ingredient") for item in additive_codes
            )
        )
    }


if __name__ == "__main__":

    result = analyze_ingredients(
        ingredient_text=(
            "Wholegrain Rye Flour (51%), Sugar, "
            "Sunflower Seeds (10%), Wholegrain Oat Flakes, Whey"
        ),
        contains_text="RYE, GLUTEN",
        may_contain_text="SESAME"
    )

    print("\n========== INGREDIENT ANALYSIS ==========")

    for key, value in result.items():
        print(f"\n{key.upper()}:")
        print(value)
