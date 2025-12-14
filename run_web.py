"""
Quick launcher for the Data Over Dogma web application.
"""
import uvicorn
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Data Over Dogma Web Application")
    print("=" * 60)
    print("\n📍 Access Points:")
    print("   • Main Search:  http://localhost:8000")
    print("   • Ingest Page:  http://localhost:8000/ingest")
    print("   • Episodes:     http://localhost:8000/episodes")
    print("   • Transcribe:   http://localhost:8000/transcribe")
    print("   • API Docs:     http://localhost:8000/docs")
 
    print("\n💡 Press Ctrl+C to stop the server\n")
    print("=" * 60 + "\n")
    
    # Change directory to src for proper imports
    import os
    os.chdir(str(src_path))
    
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )