from dotenv import load_dotenv

# Must run before any app.* imports below — several modules (e.g.
# app.auth.tokens) read required environment variables like JWT_SECRET at
# *import time*, so the .env file has to be loaded into the process
# environment first. uvicorn does NOT load .env files on its own.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.routes import router as agent_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.auth.routes import router as auth_router
from app.db import init_db
from app.filesystem.routes import router as filesystem_router
from app.rag.routes import router as rag_router
from app.repository.routes import router as repository_router
from app.validation.routes import router as validation_router

app = FastAPI(
    title="CodeForge AI",
    description="Local-first AI Software Engineering Agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # allow_credentials=True is required for the refresh-token cookie to be
    # sent/received cross-origin during local dev (frontend on :5173, backend
    # on :8000). Keep this origin list exact — never combine
    # allow_credentials=True with allow_origins=["*"], browsers will reject it
    # and, more importantly, it would let any site ride the user's cookies.
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(repository_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(validation_router, prefix="/api")
app.include_router(filesystem_router, prefix="/api")