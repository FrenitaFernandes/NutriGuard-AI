
from sentence_transformers import SentenceTransformer


# Load the embedding model
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Loading embedding model...")

embedding_model = SentenceTransformer(MODEL_NAME)

print("Embedding model loaded successfully!")


def generate_embeddings(chunks):

    # Extract text from all chunks
    texts = [chunk["page_content"] for chunk in chunks]

    print(f"Generating embeddings for {len(texts)} chunks...")

    # Convert text into numerical vectors
    embeddings = embedding_model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    print("Embeddings generated successfully!")
    print("Embedding shape:", embeddings.shape)

    return embeddings


if __name__ == "__main__":

    from text_splitter import split_documents
    from document_loader import load_pdf_documents

    documents = load_pdf_documents()
    chunks = split_documents(documents)

    embeddings = generate_embeddings(chunks)

    print("\n----- SAMPLE EMBEDDING -----")
    print(embeddings[0][:10])

    print("\nTotal vectors:", len(embeddings))
    print("Dimensions per vector:", embeddings.shape[1])
