
from pathlib import Path
import pymupdf


# Project root directory
BASE_DIR = Path(__file__).resolve().parents[2]

# Folder containing trusted reference PDFs
PDF_FOLDER = BASE_DIR / "data" / "knowledge_base"


def load_pdf_documents():
    documents = []

    # Find all PDF files inside knowledge_base and its subfolders
    pdf_files = list(PDF_FOLDER.rglob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in knowledge_base!")
        return documents

    print(f"Found {len(pdf_files)} PDF file(s).")

    for pdf_path in pdf_files:
        try:
            pdf = pymupdf.open(pdf_path)

            print(f"\nReading: {pdf_path.name}")

            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()

                # Skip pages without extractable text
                if not text:
                    continue

                documents.append({
                    "page_content": text,
                    "metadata": {
                        "source": pdf_path.name,
                        "page": page_number,
                        "category": pdf_path.parent.name
                    }
                })

            pdf.close()

        except Exception as error:
            print(f"Error reading {pdf_path.name}: {error}")

    print(f"\nTotal pages extracted: {len(documents)}")

    return documents


if __name__ == "__main__":
    pages = load_pdf_documents()

    if pages:
        print("\n----- SAMPLE EXTRACTED TEXT -----")
        print(pages[0]["page_content"][:1000])

        print("\n----- SOURCE INFORMATION -----")
        print(pages[0]["metadata"])
