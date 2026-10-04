"""ASGI entry point without workflow or business endpoints."""

from fastapi import FastAPI

app = FastAPI(title="Agentic SDLC Orchestrator", version="0.1.0")
