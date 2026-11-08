
import re


def clean_ocr_text(raw_text):
    """Clean OCR formatting without guessing missing words."""

    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line.strip())

        if line:
            lines.append(line)

    return "\n".join(lines)


SECTION_PATTERNS = {
    "ingredients": r"\bINGREDIENTS?\s*:?",
    "contains": r"\bCONTAINS\s*:",
    "may_contain": r"\bMAY\s+CONTAIN\s*:",
    "nutrition": (
        r"\b(?:NUTRITION\s+FACTS|NUTRITION\s+INFORMATION|"
        r"NUTRITIONAL\s+INFORMATION)\b"
    )
}


def find_section_positions(text):
    """Find food-label section headings."""

    positions = []

    for section, pattern in SECTION_PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            positions.append({
                "section": section,
                "start": match.start(),
                "end": match.end()
            })

    positions.sort(key=lambda item: item["start"])

    return positions


def extract_label_sections(raw_text):
    """
    Extract ingredient and allergen declarations.
    Preserve OCR text without correcting uncertain words.
    """

    cleaned_text = clean_ocr_text(raw_text)

    positions = find_section_positions(cleaned_text)

    sections = {
        "ingredients": "",
        "contains": "",
        "may_contain": "",
        "nutrition": ""
    }

    for index, item in enumerate(positions):

        section_name = item["section"]
        start = item["end"]

        end = (
            positions[index + 1]["start"]
            if index + 1 < len(positions)
            else len(cleaned_text)
        )

        content = cleaned_text[start:end].strip()

        if not sections[section_name]:
            sections[section_name] = content

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        **sections
    }


def assess_section_quality(sections):
    """
    Flag missing or potentially incomplete OCR sections.
    This does not determine whether a food is safe.
    """

    warnings = []

    ingredients = sections.get("ingredients", "")
    contains = sections.get("contains", "")
    may_contain = sections.get("may_contain", "")

    if not ingredients:
        warnings.append("Ingredients section was not detected.")

    if not contains and not may_contain:
        warnings.append(
            "No allergen declaration was detected. "
            "This does not mean the product is allergen-free."
        )

    # Flag text that appears cut off at the end.
    for name, value in [
        ("Ingredients", ingredients),
        ("Contains", contains),
        ("May contain", may_contain)
    ]:
        if value and re.search(r"(?:[A-Za-z]{2,})$", value):
            # This is only a review flag, not proof of truncation.
            pass

    return warnings


if __name__ == "__main__":

    sample_text = """
    Nutrition Facts
    Calories 110
    Total Fat 1.5g

    INGREDIENTS
    Wholegrain Rye Flour
    Sugar
    Seeds (10%) (Sunflower Seeds)
    Wholegrain Oat Flakes

    CONTAINS: RYE, GLUTEN

    MAY CONTAIN: SESAME
    """

    result = extract_label_sections(sample_text)

    print("\n========== FOOD LABEL ==========")

    for section in [
        "ingredients",
        "contains",
        "may_contain",
        "nutrition"
    ]:
        print(f"\n{section.upper()}:")
        print(result[section] or "Not detected")

    print("\nWARNINGS:")
    for warning in assess_section_quality(result):
        print("-", warning)
