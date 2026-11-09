
import csv
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = PROJECT_ROOT / "data" / "ingredient_reference"
GUIDANCE_SOURCES = [
    {
        "name": "FSSAI Food Safety and Standards",
        "url": "https://www.fssai.gov.in/cms/food-safety-and-standards-regulations.php",
    },
    {
        "name": "WHO Healthy Diet",
        "url": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
    },
]


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

    with open(
        REFERENCE_DIR / "additives.json",
        "r",
        encoding="utf-8",
    ) as file:
        additives = json.load(file)

    return ingredients, allergens, synonyms, additives


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
                    "purpose": item.get("description", "") or (
                        f"Used as a {item.get('category', 'food ingredient').lower()}."
                    ),
                    "alternative_names": [
                        synonym for synonym in terms
                        if normalize_text(synonym) != normalize_text(name)
                    ]
                })

                break

    return matches


def find_additive_codes(text, ingredients, additives):
    """Find explicit INS/E-numbers and explain only reference-backed codes."""
    normalized = normalize_text(text)
    codes = set(
        re.findall(
            r"\b(?:INS|E)\s*[- ]?\s*(\d{3,4}[a-z]?)\b",
            normalized,
            re.I,
        )
    )
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
                "description": item.get("description", ""),
                "purpose": item.get("description", ""),
            })
            matched_codes.add(code.lower().replace(" ", ""))
    for code in codes:
        normalized_code = code.lower().replace(" ", "")
        reference = additives.get(normalized_code)
        if normalized_code not in matched_codes:
            if reference:
                name = reference["name"]
                category = reference.get("category", "")
                description = reference.get("purpose", "")
            else:
                name = f"INS/E-{code}"
                category = "Reference match unavailable"
                description = "The code was detected, but its explanation is not in the local reference database."
            matches.append({
                "ingredient": name,
                "code": code,
                "category": category,
                "matched_term": code,
                "reference_match": bool(reference),
                "description": description,
                "purpose": description,
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


def parse_nutrition(text):
    """Extract only explicitly printed nutrition values and units."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    patterns = {
        "energy": (r"(?:energy|calories?)\s*[:\-]?\s*([\d.,]+)\s*(kcal|kj)\b"),
        "sugar": (r"(?:total\s+)?sugars?\s*[:\-]?\s*([\d.,]+)\s*(g|mg)\b"),
        "saturated_fat": (r"saturated\s+fat\s*[:\-]?\s*([\d.,]+)\s*(g|mg)\b"),
        "fat": (r"(?<!saturated )(?:total\s+)?fat\s*[:\-]?\s*([\d.,]+)\s*(g|mg)\b"),
        "protein": (r"protein\s*[:\-]?\s*([\d.,]+)\s*(g|mg)\b"),
        "carbohydrates": (r"(?:total\s+)?carbohydrates?\s*[:\-]?\s*([\d.,]+)\s*(g|mg)\b"),
        "sodium": (r"sodium\s*[:\-]?\s*([\d.,]+)\s*(g|mg)\b"),
        "serving_size": (r"serving\s+size\s*[:\-]?\s*([\d.,]+)\s*(g|kg|ml|l|oz)\b"),
    }
    values = {}
    global_basis = re.search(
        r"\bper\s+(100\s*(?:g|ml)|serving)\b",
        normalized,
        re.IGNORECASE,
    )
    for name, pattern in patterns.items():
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        values[name] = {
            "value": match.group(1).replace(",", "."),
            "unit": match.group(2),
        }
        basis = re.search(
            r"\bper\s+(100\s*(?:g|ml)|serving)\b",
            normalized[match.end():match.end() + 40],
            re.IGNORECASE,
        )
        if basis:
            values[name]["basis"] = basis.group(1)
    if global_basis:
        for item in values.values():
            item.setdefault("basis", global_basis.group(1))
    return values


def consumption_guidance(nutrition):
    """Give cautious interpretation without setting universal thresholds."""
    if not nutrition:
        return {
            "summary": "No complete nutrition values with units were extracted. Check the original label before deciding how much to consume.",
            "sources": GUIDANCE_SOURCES,
        }
    serving = nutrition.get("serving_size")
    if serving:
        basis = f"the stated serving size of {serving['value']} {serving['unit']}"
    else:
        basis = "the serving basis printed on the label"
    return {
        "summary": (
            f"Use {basis} when comparing this product with your own dietary needs. "
            + (
                "A serving size was not extracted, so do not infer a portion from these values. "
                if not serving else ""
            )
            +
            "This analysis does not set a universal safe amount; people with allergies, medical conditions, or specific dietary advice should follow a qualified professional's guidance."
        ),
        "sources": GUIDANCE_SOURCES,
    }


def analyze_ingredients(
    ingredient_text,
    contains_text="",
    may_contain_text="",
    nutrition_text=""
):
    """Analyze ingredients and allergen declarations separately."""

    ingredients, allergens, synonyms, additives = load_ingredient_database()

    ingredient_matches = match_ingredients(
        ingredient_text,
        ingredients,
        synonyms
    )
    additive_codes = find_additive_codes(ingredient_text, ingredients, additives)

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
    nutrition = parse_nutrition(nutrition_text)

    return {
        "ingredient_matches": ingredient_matches,
        "additive_codes": additive_codes,
        "ingredient_allergens": ingredient_allergens,
        "contains_allergens": declared_allergens,
        "may_contain_allergens": possible_allergens,
        "unmatched_words_for_review": unmatched_words,
        "original_ingredient_text": ingredient_text,
        "nutrition": nutrition,
        "consumption_guidance": consumption_guidance(nutrition),
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
