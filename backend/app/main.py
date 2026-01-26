from fastapi import FastAPI

from app.db.base import Base
from app.db.db import engine
from app.routers import agent, extract, health, process, query, upload, summary, files

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="My API",
    root_path="/backend",
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(extract.router)
app.include_router(process.router)
app.include_router(query.router)
app.include_router(agent.router)
app.include_router(summary.router)
app.include_router(files.router)
