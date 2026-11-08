
import os
from dotenv import load_dotenv
from google import genai

from backend.rag.retriever import search_documents

# Load environment variables
load_dotenv()

# Initialize Gemini
api_key = os.getenv("GEMINI_API_KEY")
client = None

if api_key:
    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 120000}
    )
    print("Gemini client initialized successfully!")
else:
    print("Gemini API key not found!")


# RAG question-answering function
def answer_question(question, top_k=5, product_context=None):

    if client is None:
        return {
            "answer": "Gemini client is not initialized.",
            "sources": []
        }

    try:
        # Step 1: Retrieve relevant chunks from FAISS
        print("\nSearching FAISS database...")

        results = search_documents(question, top_k=top_k)

        if not results:
            return {
                "answer": "No relevant information was found in the knowledge base.",
                "sources": []
            }

        # Step 2: Prepare context for Gemini
        context = ""
        sources = []

        for i, result in enumerate(results, start=1):

            metadata = result["metadata"]

            source = {
                "document": metadata["source"],
                "page": metadata["page"]
            }

            if source not in sources:
                sources.append(source)

            context += f"""
            Source {i}: {metadata['source']}
            Page: {metadata['page']}

            Content:
            {result['text']}

            -------------------------
            """

        # Step 3: Create RAG prompt
        product_context_text = ""
        if isinstance(product_context, dict):
            product_context_text = f"""
PRODUCT CURRENTLY BEING DISCUSSED:
{product_context}

Use this product information for product-specific questions. Do not invent
ingredients or allergen findings that are not present in it.
"""

        prompt = f"""
You are NutriGuard AI, a food ingredient information assistant.

Answer the user's question using ONLY the provided reference context.

Instructions:
1. Give a clear and simple explanation.
2. Do not invent facts or unsupported health claims.
3. If the context does not contain the answer, clearly say that
   the available documents do not provide enough information.
4. Do not treat similarity scores as scientific evidence.
5. Mention relevant document names and page numbers.
6. Distinguish regulatory information from health or safety evidence.
7. For regulatory questions, rely on the supplied FSSAI and JECFA documents
   and cite the source document and page in the answer.

REFERENCE CONTEXT:
{context}
{product_context_text}

USER QUESTION:
{question}

Provide a helpful and factual answer.
"""

        # Step 4: Generate answer using Gemini
        print("Generating answer using Gemini...")

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        return {
            "answer": response.text,
            "sources": sources
        }

    except Exception as error:
        print("RAG error:", error)

        return {
            "answer": f"Unable to generate an answer: {error}",
            "sources": []
        }


# Test RAG pipeline
if __name__ == "__main__":

    question = "What is monosodium glutamate (MSG), and why is it used in food?"

    result = answer_question(question)

    print("\n========== NUTRIGUARD AI ANSWER ==========")
    print(result["answer"])

    print("\n========== SOURCES ==========")

    for source in result["sources"]:
        print(f"Document: {source['document']}")
        print(f"Page: {source['page']}")
        print("-------------------------")
