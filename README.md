# NutriGuard AI – Food Ingredient & Allergen Detection

An AI-powered food analysis application that helps users understand packaged food ingredients, identify potential allergens, and make informed food choices using OCR, Retrieval-Augmented Generation (RAG), and Generative AI.

## Problem Statement

Food packaging often contains complex ingredient names, INS/E-numbers, and allergen declarations that consumers may find difficult to understand. NutriGuard AI simplifies this information and provides personalized alerts based on user-selected allergies.

## Key Features

- **Food Label Scanning:** Upload an image of a packaged food ingredients label.
- **Ingredient Analysis:** Extract and explain ingredients in simple language.
- **Allergen Detection:** Identify supported allergen labels and ingredient aliases.
- **Contains & May Contain:** Display declared allergens separately.
- **Personalized Allergy Alerts:** Highlight potential concerns based on selected allergies.
- **INS/E-number Explanation:** Explain food additives and their categories.
- **Explain This Product:** Get an easy-to-understand product summary.
- **AI Assistant:** Ask general food questions or questions about the analyzed product.
- **Regulatory Information:** Provide FSSAI/JECFA-grounded answers with sources.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend development |
| Flask | Web application framework |
| HTML, CSS, JavaScript | Frontend |
| OCR / PyMuPDF | Text extraction and document processing |
| Sentence Transformers | Text embeddings |
| FAISS | Vector similarity search |
| RAG | Context-based information retrieval |
| Google Gemini API | AI-powered explanations |
| Python Libraries | Data processing and integration |

## How It Works

1. User uploads a food ingredients label image.
2. OCR extracts the ingredient text.
3. The application processes and identifies ingredients, additives, and allergen declarations.
4. User-selected allergies are compared with the extracted information.
5. RAG retrieves relevant information from the ingested reference documents.
6. Gemini generates understandable explanations and answers.
7. The user can ask follow-up questions through the AI Assistant using the analyzed product context.

## Project Structure

```text
NutriGuard-AI/
│
├── app.py
├── ingredient_service.py
├── llm_service.py
├── requirements.txt
├── .env
├── .gitignore
│
├── templates/
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── data/
│   └── reference_documents/
│
└── tests/
```

*Note: Adjust this structure to match the actual folders in your repository.*

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/FrenitaFernandes/NutriGuard-AI.git
```

### 2. Navigate to the project

```bash
cd NutriGuard-AI
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file and add your Gemini API key using the variable name expected by your application.

```env
GEMINI_API_KEY=your_api_key_here
```

Never upload your actual API key to GitHub.

### 6. Run the application

```bash
python app.py
```

Open the local URL displayed in your terminal.

## Testing

- 8 existing tests passed.
- Python syntax validation passed.
- JavaScript syntax validation passed.

## Future Enhancements

- Support for additional food packaging formats.
- Improved OCR accuracy for unclear images.
- Multilingual ingredient explanations.
- Expanded food additive and allergen knowledge base.
- More comprehensive product analysis.

## Disclaimer

NutriGuard AI is an informational tool and is not a substitute for professional medical advice. Users with food allergies should always verify product labels and consult qualified healthcare professionals when necessary.

## Developer

**Frenita Fernandes**

GitHub: https://github.com/FrenitaFernandes