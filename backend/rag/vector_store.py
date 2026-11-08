
import faiss
import pickle
import numpy as np
from pathlib import Path

from document_loader import load_pdf_documents
from text_splitter import split_documents
from embedding_service import generate_embeddings


# Project directories
BASE_DIR = Path(__file__).resolve().parents[2]

INDEX_FOLDER = BASE_DIR / "data" / "faiss_index"

INDEX_FOLDER.mkdir(parents=True, exist_ok=True)

INDEX_PATH = INDEX_FOLDER / "index.faiss"
METADATA_PATH = INDEX_FOLDER / "metadata.pkl"


def create_faiss_index():

    print("\nLoading PDF documents...")

    documents = load_pdf_documents()

    print("\nSplitting documents into chunks...")

    chunks = split_documents(documents)

    print("\nGenerating embeddings...")

    embeddings = generate_embeddings(chunks)

    # Convert embeddings to FAISS-compatible format
    embeddings = np.asarray(embeddings, dtype="float32")

    # Create FAISS index
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    # Add embeddings to the index
    index.add(embeddings)

    # Save FAISS index
    faiss.write_index(index, str(INDEX_PATH))

    # Save chunks and metadata
    with open(METADATA_PATH, "wb") as file:
        pickle.dump(chunks, file)

    print("\nFAISS index created successfully!")
    print("Total vectors:", index.ntotal)
    print("Vector dimensions:", dimension)
    print("Index saved at:", INDEX_PATH)
    print("Metadata saved at:", METADATA_PATH)


if __name__ == "__main__":
    create_faiss_index()
