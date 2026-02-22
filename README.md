# AI-Based Palo Alto GlobalProtect Log Analyzer

A production-style RAG (Retrieval-Augmented Generation) system for MSP network engineers to troubleshoot GlobalProtect issues.

## Features
- **Log Analysis**: Automatically extracts the core issue from uploaded GlobalProtect logs.
- **Semantic Search**: Uses FAISS and sentence-transformers to find relevant Palo Alto KB articles.
- **AI Troubleshooting**: Generates concise steps using a local LLM (Flan-T5).
- **Modular Design**: Easy to swap local LLM with OpenAI, Gemini, etc.

## Tech Stack
- **Frontend**: React.js, Tailwind CSS, Axios, Lucide-React
- **Backend**: FastAPI, FAISS, Sentence-Transformers, Hugging Face Transformers
- **Database**: FAISS (Local Vector Storage)

## Setup Instructions

### Backend
1. Navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run the offline indexing script to prepare the FAISS database:
   ```bash
   python scripts/index_kb.py
   ```
4. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend
1. Navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## Folder Structure
- `backend/app/core`: Base classes and configuration.
- `backend/app/services`: Business logic (LLM, FAISS, Log Parsing).
- `backend/app/api`: FastAPI route definitions.
- `backend/data`: Local storage for KB articles and FAISS index.
- `backend/scripts`: Utility scripts for offline processing.
- `frontend/src`: React components and UI logic.
