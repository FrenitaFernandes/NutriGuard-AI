import os
import re

from dotenv import load_dotenv
from google import genai

from backend.rag.retriever import search_documents


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = None

if api_key:
    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 120000},
    )
    print("Gemini client initialized successfully!")
else:
    print("Gemini API key not found!")


REGULATORY_TERMS = {
    "fssai", "jecfa", "regulation", "regulatory", "standard", "standards",
    "legal", "legally", "permitted", "permissible", "labelling", "labeling",
    "declaration", "compliance", "limit", "limits", "food safety",
}
PRODUCT_TERMS = {
    "this", "product", "label", "scanned", "contains", "ingredient",
    "ingredients", "allergen", "allergens", "serving", "nutrition",
}
STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "of", "in", "for", "to", "and",
    "or", "with", "does", "do", "how", "why", "tell", "me", "about",
}
OFFICIAL_SOURCE_LINKS = {
    "food_additives.pdf": "https://www.fssai.gov.in/cms/food-safety-and-standards-regulations.php",
    "packaging_labelling.pdf": "https://www.fssai.gov.in/cms/food-safety-and-standards-regulations.php",
    "jecfa_compendium_2025.pdf": "https://apps.who.int/food-additives-contaminants-jecfa-database/",
}


def _tokens(text):
    return {
        token for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if token not in STOP_WORDS and len(token) > 2
    }


def classify_question(question, product_context=None):
    """Choose the evidence policy without asking the model to classify itself."""
    question_tokens = _tokens(question)
    if question_tokens & REGULATORY_TERMS:
        return "regulatory"
    if isinstance(product_context, dict) and question_tokens & PRODUCT_TERMS:
        return "product"
    return "general"


def _relevant_results(question, results):
    query_tokens = _tokens(question)
    relevant = []
    for result in results:
        document_tokens = _tokens(result.get("text", ""))
        overlap = query_tokens & document_tokens
        semantic_score = result.get("semantic_score")
        if overlap or (semantic_score is not None and semantic_score >= 0.62):
            relevant.append(result)
    return relevant


def _document_context(question, top_k):
    candidates = search_documents(question, top_k=top_k)
    results = _relevant_results(question, candidates)
    sources = []
    context_parts = []
    for number, result in enumerate(results, start=1):
        metadata = result["metadata"]
        document = metadata["source"]
        source = {
            "type": "document",
            "document": document,
            "page": metadata["page"],
            "url": OFFICIAL_SOURCE_LINKS.get(document),
        }
        if source not in sources:
            sources.append(source)
        context_parts.append(
            f"Document evidence {number}: {document}, page {metadata['page']}\n"
            f"{result['text']}"
        )
    return "\n\n---\n\n".join(context_parts), sources


def answer_question(
    question,
    top_k=5,
    product_context=None,
    conversation_history=None,
):
    if client is None:
        return {"error": "The AI assistant is not configured.", "sources": []}

    try:
        mode = classify_question(question, product_context)
        context = ""
        sources = []
        if mode == "regulatory":
            context, sources = _document_context(question, top_k)

        product_context_text = "No scanned product is currently available."
        if isinstance(product_context, dict):
            product_context_text = (
                "PRODUCT LABEL FACTS (use only what is explicitly present):\n"
                f"{product_context}"
            )

        history_text = "No earlier conversation."
        if conversation_history:
            history_text = "\n".join(
                f"{item.get('role', 'user')}: {item.get('content', '')}"
                for item in conversation_history[-10:]
            )

        evidence_text = context or "No relevant regulatory document evidence was retrieved."
        prompt = f"""
You are NutriGuard AI, a concise food-label assistant.

Answer naturally in a short conversational response. Do not use unnecessary
headings, asterisks, or technical language. Never invent quantities, product
facts, health claims, or citations. If a quantity is not in the label facts,
say it is not available.

Question type: {mode}

Evidence rules:
- PRODUCT LABEL FACTS are facts extracted from the current user's scanned label.
- DOCUMENT EVIDENCE is only relevant for regulatory questions. Cite its exact
  document name and page when you use it.
- GENERAL AI KNOWLEDGE may answer ordinary food, ingredient, additive, and
  nutrition questions, but distinguish it from label facts.
- Do not use unrelated document evidence. Do not claim that a local PDF proves
  a medical or health outcome.
- If reliable external information is needed, say that an external source is
  needed. Do not fabricate a URL. Official document links are returned
  separately as sources.

{product_context_text}

CONVERSATION HISTORY:
{history_text}

RELEVANT DOCUMENT EVIDENCE:
{evidence_text}

USER QUESTION:
{question}
"""

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        return {
            "answer": response.text.strip(),
            "sources": sources,
            "mode": mode,
            "provenance": {
                "product_facts": bool(product_context),
                "document_evidence": bool(context),
                "general_knowledge": mode in {"general", "product"},
            },
        }
    except Exception:
        print("RAG/LLM error")
        return {
            "error": "The AI assistant could not generate a response.",
            "sources": [],
        }
