
import re


def _normalise(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value.lower())).strip()


def _allergy_aliases(value):
    aliases = {
        "milk": {"milk", "whey", "casein", "lactose", "dairy"},
        "gluten": {"gluten", "wheat", "rye", "barley"},
        "soy": {"soy", "soya", "soybean"},
        "peanut": {"peanut", "groundnut", "arachis"},
        "tree nuts": {"tree nut", "tree nuts", "almond", "cashew", "walnut", "pistachio", "hazelnut"},
        "sesame": {"sesame", "til"},
        "egg": {"egg", "albumin"},
        "fish": {"fish"},
        "crustaceans": {"crustacean", "crustaceans", "crab", "prawn", "shrimp", "lobster"}
    }
    normalized = _normalise(value)
    return {normalized} | aliases.get(normalized, set())


def compare_user_allergies(user_allergies, analysis):
    """
    Compare user allergies with detected ingredient allergens
    and label declarations.
    """

    confirmed = {}
    possible = {}

    def add_matches(items, evidence, target):
        for item in items:
            name = _normalise(item.get("allergen", ""))

            if name:
                target.setdefault(name, set()).add(evidence)

    add_matches(
        analysis.get("ingredient_allergens", []),
        "Identified in ingredient text", confirmed
    )

    add_matches(
        analysis.get("contains_allergens", []),
        "Explicit Contains declaration", confirmed
    )

    add_matches(
        analysis.get("may_contain_allergens", []),
        "May Contain declaration", possible
    )

    # Also include allergen categories from matched ingredients.
    for item in analysis.get("ingredient_matches", []):
        allergen = item.get("allergen", "").strip().lower()

        if allergen and allergen != "none":
            confirmed.setdefault(allergen, set()).add(
                "Associated with a matched ingredient"
            )

    results = []

    for user_allergy in user_allergies:

        allergy = _normalise(user_allergy)

        if not allergy:
            continue

        matching_confirmed = {
            key: evidence for key, evidence in confirmed.items()
            if _allergy_aliases(allergy) & _allergy_aliases(key)
        }
        matching_possible = {
            key: evidence for key, evidence in possible.items()
            if _allergy_aliases(allergy) & _allergy_aliases(key)
        }
        if matching_confirmed:
            results.append({
                "allergen": user_allergy,
                "status": "MATCH_FOUND",
                "evidence": sorted(set().union(*matching_confirmed.values())),
                "confirmed": True,
                "possible_cross_contamination": bool(matching_possible)
            })
        elif matching_possible:
            results.append({
                "allergen": user_allergy,
                "status": "POSSIBLE_CROSS_CONTAMINATION",
                "evidence": sorted(set().union(*matching_possible.values())),
                "confirmed": False,
                "possible_cross_contamination": True
            })
        else:
            results.append({
                "allergen": user_allergy,
                "status": "NO_MATCH_DETECTED",
                "evidence": [],
                "confirmed": False,
                "possible_cross_contamination": False
            })

    return {
        "user_allergies": user_allergies,
        "results": results,
        "confirmed_matches": [item for item in results if item["status"] == "MATCH_FOUND"],
        "possible_cross_contamination": [
            item for item in results
            if item["status"] == "POSSIBLE_CROSS_CONTAMINATION"
            or item.get("possible_cross_contamination")
        ],
        "review_required": analysis.get("review_required", True),
        "safety_note": (
            "No match detected does not establish that a product "
            "is safe. OCR may miss ingredients or allergen declarations."
        )
    }
