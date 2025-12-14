"""
FastAPI web application for podcast search and Q&A.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup paths FIRST
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create directories if they don't exist
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Import routes AFTER setting up paths
from web.routes import query, ingest, episodes, conversations, transcribe
from api import search

# Initialize FastAPI app
app = FastAPI(
    title="Podcast RAG - Podcast Search",
    description="Semantic search and Q&A system for podcast transcripts using RAG (Retrieval-Augmented Generation)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Add CORS middleware FIRST (middleware is processed in reverse order)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# PAGE ROUTES - Define BEFORE mounting static or including routers
# ============================================================================

@app.get("/")
async def home(request: Request):
    """Main search and Q&A interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/ingest")
async def ingest_page(request: Request):
    """Episode ingestion interface."""
    return templates.TemplateResponse("ingest.html", {"request": request})


@app.get("/episodes")
async def episodes_page(request: Request):
    """Episode management interface."""
    return templates.TemplateResponse("episodes.html", {"request": request})


@app.get("/reingest")
async def reingest_page(request: Request):
    """Re-ingestion interface."""
    return templates.TemplateResponse("reingest.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "podcast-search",
        "version": "1.0.0",
        "features": ["semantic_search", "qa"]
    }


@app.get("/api")
async def api_info():
    """API information."""
    return {
        "name": "Podcast RAG API",
        "version": "1.0.0",
        "endpoints": {
            "query": "/api/query/*",
            "ingest": "/api/ingest/*",
            "episodes": "/api/episodes/*",
            "search": "/api/search/*"
        },
        "docs": "/docs"
    }
    
@app.get("/transcribe")
async def transcribe_page(request: Request):
    """Podcast transcription interface."""
    return templates.TemplateResponse("transcribe.html", {"request": request})


# ============================================================================
# INCLUDE API ROUTERS
# ============================================================================

app.include_router(query.router, prefix="/api/query", tags=["Query & Search"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingestion"])
app.include_router(episodes.router, prefix="/api/episodes", tags=["Episodes"])
app.include_router(search.router, prefix="/api/search", tags=["Enhanced Search"])
app.include_router(conversations.router, prefix="/api/conversation", tags=["Conversations"])
app.include_router(transcribe.router, prefix="/api/transcribe", tags=["Transcription"])


# ============================================================================
# MOUNT STATIC FILES - MUST BE LAST
# ============================================================================

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler - only for page routes, not API."""
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"detail": f"API endpoint not found: {request.url.path}"}
        )
    
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
        status_code=404
    )


""" # Debug: Print registered routes
print("\n" + "="*80)
print("📋 REGISTERED ROUTES:")
for route in app.routes:
    if hasattr(route, 'path'):
        methods = getattr(route, 'methods', ['MOUNT'])
        print(f"  {str(methods):30} {route.path}")
print("="*80 + "\n") """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)