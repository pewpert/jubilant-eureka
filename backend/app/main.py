import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import create_tables
from app.api.routes import search, listings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema management is owned by Alembic (run in the container entrypoint when
    # RUN_MIGRATIONS=1). When migrations are NOT enabled — e.g. running the API
    # directly outside Docker for local dev — fall back to create_all so the app
    # still boots against a fresh DB.
    if os.environ.get("RUN_MIGRATIONS", "0") != "1":
        await create_tables()
    yield


app = FastAPI(
    title="Tokyo Apartment Search API",
    description="Aggregates rental listings from Suumo, Homes, Chintai and more.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(listings.router, prefix="/api/listings", tags=["listings"])


@app.get("/health")
async def health():
    return {"status": "ok"}
