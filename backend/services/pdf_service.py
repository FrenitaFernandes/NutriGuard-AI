from pathlib import Path

import pymupdf


def render_pdf_pages(pdf_path, output_dir):
    """Render PDF pages to bounded-resolution PNGs for the OCR pipeline."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    document = pymupdf.open(pdf_path)
    try:
        for page_number, page in enumerate(document, start=1):
            scale = min(2.0, 1800 / max(page.rect.width, page.rect.height))
            output_path = output_dir / f"page-{page_number}.png"
            page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                alpha=False,
            ).save(output_path)
            rendered.append(output_path)
    finally:
        document.close()
    return rendered