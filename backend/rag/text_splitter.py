
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents(documents):

    # Configure the text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = []

    # Process every extracted PDF page
    for document in documents:

        text = document["page_content"]
        metadata = document["metadata"]

        # Split the page text into smaller chunks
        page_chunks = splitter.split_text(text)

        # Preserve source information for every chunk
        for chunk in page_chunks:
            chunks.append({
                "page_content": chunk,
                "metadata": metadata.copy()
            })

    print(f"Total extracted pages: {len(documents)}")
    print(f"Total generated chunks: {len(chunks)}")

    return chunks


if __name__ == "__main__":

    from document_loader import load_pdf_documents

    # Step 1: Extract PDF text
    documents = load_pdf_documents()

    # Step 2: Split extracted text
    chunks = split_documents(documents)

    # Display sample chunk
    if chunks:
        print("\n----- SAMPLE CHUNK -----")
        print(chunks[0]["page_content"])

        print("\n----- CHUNK METADATA -----")
        print(chunks[0]["metadata"])
