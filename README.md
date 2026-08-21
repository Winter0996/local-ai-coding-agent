# CodeForge AI

Local-first AI Software Engineering Agent.

## Goal

CodeForge AI is a zero-cost, local AI engineering assistant designed to analyze software repositories, retrieve relevant code, plan engineering tasks, propose patches, run validation, and expose evaluation metrics.

## Current scaffold

This starter scaffold intentionally implements only the foundation:

- React + TypeScript + Vite frontend
- FastAPI backend
- Ollama provider abstraction
- `/api/health`
- `/api/chat`
- Mock-friendly LLM interface
- Basic tests
- No paid APIs
- No API keys required

## Planned stack

- React + TypeScript + Vite
- FastAPI
- Ollama
- Qwen3 8B (local)
- Sentence-Transformers
- ChromaDB
- SQLite
- Pytest / Vitest
- Docker
- GitHub Actions

## Local-first requirement

The project is designed to run locally and does not require OpenAI, Anthropic, Gemini, hosted vector databases, or a credit card.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Ollama

Install a local model after installing Ollama:

```powershell
ollama pull qwen3:8b
```

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend: http://localhost:8000

## Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

## API

- `GET /api/health`
- `POST /api/chat`

Example:

```json
{
  "message": "Explain dependency injection."
}
```

## Next milestones

1. Repository selection and file tree
2. Code indexing
3. Semantic code retrieval
4. Agent planning
5. Tool registry
6. Human approval
7. Patch generation
8. Test/repair loop
9. Security policies
10. Evaluation benchmark
