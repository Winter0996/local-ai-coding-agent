# Architecture

## Milestone 1

```text
React + TypeScript
        |
        | HTTP
        v
FastAPI
        |
        v
Ollama
        |
        v
Local LLM
```

## Planned architecture

```text
React
  |
FastAPI
  |
Agent Orchestrator
  |------ Repository Service
  |------ RAG Retriever
  |------ Tool Registry
  |------ Policy Engine
  |
Ollama
  |
Local Model

Repository -> Code Chunking -> Embeddings -> ChromaDB
```

The system is intentionally local-first so AI inference does not require a paid API.
