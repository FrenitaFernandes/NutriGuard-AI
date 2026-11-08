
import faiss
import pickle
import re
import math
import numpy as np

from pathlib import Path
from collections import Counter
from sentence_transformers import SentenceTransformer


# ==========================================
# 1. PROJECT PATHS AND MODEL
# ==========================================

BASE_DIR = Path(__file__).resolve().parents[2]

INDEX_PATH = BASE_DIR / "data" / "faiss_index" / "index.faiss"
METADATA_PATH = BASE_DIR / "data" / "faiss_index" / "metadata.pkl"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# ==========================================
# 2. LOAD EMBEDDING MODEL
# ==========================================

print("Loading Sentence Transformer model...")

model = SentenceTransformer(MODEL_NAME)

print("Embedding model loaded successfully!")


# ==========================================
# 3. LOAD FAISS DATABASE
# ==========================================

def load_faiss_database():

    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"FAISS index not found: {INDEX_PATH}")

    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {METADATA_PATH}")

    index = faiss.read_index(str(INDEX_PATH))

    with open(METADATA_PATH, "rb") as file:
        chunks = pickle.load(file)

    if index.ntotal != len(chunks):
        raise ValueError("FAISS index and metadata count do not match!")

    print("\nFAISS database loaded successfully!")
    print("Total vectors:", index.ntotal)

    return index, chunks


index, chunks = load_faiss_database()


# ==========================================
# 4. TEXT PREPROCESSING
# ==========================================

def tokenize(text):

    return re.findall(r"[a-z0-9]+", text.lower())


STOP_WORDS = {
    "what", "is", "are", "the", "a", "an",
    "of", "in", "for", "to", "and", "or",
    "with", "does", "do", "how", "why",
    "tell", "me", "about", "explain"
}


# ==========================================
# 5. QUERY EXPANSION
# ==========================================

def expand_query(query):

    expanded_terms = tokenize(query)
    query_lower = query.lower()

    aliases = {
        "msg": ["monosodium", "glutamate", "621"],
        "ins 621": ["msg", "monosodium", "glutamate"],
        "monosodium glutamate": ["msg", "621"],
        "e621": ["msg", "monosodium", "glutamate"]
    }

    for phrase, related_terms in aliases.items():

        if phrase in query_lower:
            expanded_terms.extend(related_terms)

    expanded_terms = [
        word for word in expanded_terms
        if word not in STOP_WORDS
    ]

    return list(dict.fromkeys(expanded_terms))


# ==========================================
# 6. BM25 KEYWORD SEARCH
# ==========================================

class BM25Search:

    def __init__(self, documents, k1=1.5, b=0.75):

        self.documents = documents
        self.k1 = k1
        self.b = b

        self.tokenized_docs = [
            tokenize(doc["page_content"])
            for doc in documents
        ]

        self.doc_lengths = [
            len(doc) for doc in self.tokenized_docs
        ]

        self.avgdl = (
            sum(self.doc_lengths) / len(self.doc_lengths)
            if self.doc_lengths else 0
        )

        self.doc_frequency = Counter()

        for doc in self.tokenized_docs:
            self.doc_frequency.update(set(doc))

        self.total_docs = len(self.tokenized_docs)

        self.term_frequencies = [
            Counter(doc) for doc in self.tokenized_docs
        ]

    def search(self, query):

        query_terms = expand_query(query)
        scores = []

        for i, frequencies in enumerate(self.term_frequencies):

            score = 0.0
            doc_length = self.doc_lengths[i]

            for term in query_terms:

                frequency = frequencies.get(term, 0)

                if frequency == 0:
                    continue

                df = self.doc_frequency.get(term, 0)

                idf = math.log(
                    1 + (
                        self.total_docs - df + 0.5
                    ) / (df + 0.5)
                )

                denominator = frequency + self.k1 * (
                    1 - self.b +
                    self.b * doc_length / max(self.avgdl, 1)
                )

                score += idf * (
                    frequency * (self.k1 + 1)
                ) / denominator

            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        return scores


print("\nBuilding BM25 keyword search...")

bm25 = BM25Search(chunks)

print("BM25 keyword search ready!")


# ==========================================
# 7. HYBRID SEARCH
# ==========================================

def search_documents(query, top_k=5):

    if not query or not query.strip():
        return []

    if top_k < 1:
        return []

    # Semantic search
    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32"
    )

    candidate_k = min(max(top_k * 5, 20), index.ntotal)

    semantic_scores, semantic_indices = index.search(
        query_embedding,
        candidate_k
    )

    semantic_rank = {
        int(idx): rank
        for rank, idx in enumerate(
            semantic_indices[0], start=1
        )
        if idx != -1
    }

    # Keyword search
    keyword_results = bm25.search(query)[:candidate_k]

    keyword_rank = {
        idx: rank
        for rank, (idx, score) in enumerate(
            keyword_results, start=1
        )
    }

    # Reciprocal Rank Fusion
    rrf_scores = {}

    all_indices = set(semantic_rank) | set(keyword_rank)

    for idx in all_indices:

        score = 0.0

        if idx in semantic_rank:
            score += 1 / (60 + semantic_rank[idx])

        if idx in keyword_rank:
            score += 1 / (60 + keyword_rank[idx])

        rrf_scores[idx] = score

    # ======================================
    # 8. MSG LABELLING KEYWORD BOOST
    # ======================================

    query_lower = query.lower()

    labeling_terms = [
        "label",
        "labelling",
        "labeling",
        "declaration",
        "package",
        "packaging"
    ]

    is_labeling_query = any(
        term in query_lower
        for term in labeling_terms
    )

    if is_labeling_query:

        for idx in all_indices:

            document_text = chunks[idx]["page_content"].lower()

            has_msg_declaration = (
                "monosodium glutamate" in document_text
                and (
                    "contains added" in document_text
                    or "added monosodium glutamate" in document_text
                )
            )

            if has_msg_declaration:
                rrf_scores[idx] += 0.02

    # Sort combined results
    ranked_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Original semantic scores for reference
    semantic_score_lookup = {
        int(idx): float(score)
        for idx, score in zip(
            semantic_indices[0],
            semantic_scores[0]
        )
        if idx != -1
    }

    results = []

    for idx, combined_score in ranked_results[:top_k]:

        results.append({
            "score": float(combined_score),
            "semantic_score": semantic_score_lookup.get(idx),
            "text": chunks[idx]["page_content"],
            "metadata": chunks[idx]["metadata"]
        })

    return results


# ==========================================
# 9. TEST HYBRID RETRIEVAL
# ==========================================

def test_retrieval():

    questions = [
        "What is INS 621?",
        "What are the food labelling requirements for added MSG?",
        "What is the chemical identity of monosodium glutamate?"
    ]

    for question in questions:

        print("\n" + "=" * 70)
        print("QUESTION:", question)
        print("=" * 70)

        results = search_documents(
            question,
            top_k=5
        )

        if not results:
            print("No relevant documents found.")
            continue

        for i, result in enumerate(results, start=1):

            print(f"\n--- RESULT {i} ---")

            print(
                "Hybrid score:",
                round(result["score"], 5)
            )

            print(
                "Semantic score:",
                result["semantic_score"]
            )

            print(
                "Document:",
                result["metadata"]["source"]
            )

            print(
                "Page:",
                result["metadata"]["page"]
            )

            print("\nRetrieved content:")
            print(result["text"][:400])

            print("-" * 50)


# ==========================================
# 10. RUN
# ==========================================

if __name__ == "__main__":
    test_retrieval()
