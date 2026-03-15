# AI-Based Palo Alto GlobalProtect Log Analyzer

A production-grade RAG (Retrieval-Augmented Generation) system for SOC and MSP network engineers to troubleshoot GlobalProtect issues with full visibility.

## Features
- **Live SOC Visibility**: Real-time SSE (Server-Sent Events) streaming of the backend intel pipeline.
- **Log Analysis**: Automatically extracts the core issue from uploaded GlobalProtect logs with strict dynamic chunking.
- **Semantic Search**: Uses FAISS and sentence-transformers to find relevant Palo Alto KB articles.
- **AI Troubleshooting**: Generates concise steps using local Ollama LLMs (`mistral` primary, `phi3` fail-safe fallback).
- **Graceful Control**: Includes abort controllers to manually stop and reset analysis seamlessly.

## Tech Stack
- **Frontend**: React.js, Tailwind CSS, Axios, Lucide-React
- **Backend**: FastAPI, FAISS, Sentence-Transformers
- **LLM Engine**: Ollama (Mistral, Phi3)
- **Database**: FAISS (Local Vector Storage)

## Setup Instructions

### Prerequisites
1. Install [Ollama](https://ollama.com/).
2. Pull the required models in your terminal:
   ```bash
   ollama pull mistral
   ollama pull phi3
   ```
3. Clone the repository:
   ```bash
   git clone https://github.com/Tutelar-Tech-Labs/troubleshooting_rag.git
   cd troubleshooting_rag
   ```

### Backend
1. Navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   # On Windows: venv\Scripts\activate
   # On MacOS/Linux: source venv/bin/activate  
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
