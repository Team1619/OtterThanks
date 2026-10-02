from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.routers import auth, health, kudos, mentor, slack


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Kudos & Appreciation API for Up-A-Creek Robotics",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(kudos.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(mentor.router)
app.include_router(slack.router)

# Mount React frontend if compiled dist directory exists
dist_path = Path(settings.static_dist_dir)
if dist_path.exists() and dist_path.is_dir():
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_candidate = dist_path / full_path
        if file_candidate.is_file():
            return FileResponse(file_candidate)
        index_file = dist_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Not found")
