"""
Ingestion endpoints for uploading and processing podcast episodes.
Now uses unified ingestion functions with Bible verse extraction.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import Optional, Dict
import tempfile
import json
from pathlib import Path
import sys
import uuid

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from unified ingest module
from cli.ingest import ingest_episode, ingest_folder

router = APIRouter()

# Track ingestion jobs in memory (use Redis/DB in production)
ingestion_jobs: Dict[str, str] = {}


# ============================================================================
# SINGLE EPISODE INGESTION
# ============================================================================

@router.post("/episode")
async def ingest_single_episode(
    background_tasks: BackgroundTasks,
    episode_json: UploadFile = File(..., description="Episode metadata JSON file"),
    transcript_srt: UploadFile = File(..., description="Transcript SRT file"),
    chunk_size: int = Form(3500, description="Chunk size in characters")
):
    """
    Ingest a single episode from uploaded files.
    
    Files are processed in the background, allowing immediate response.
    Use /api/ingest/status/{job_id} to check progress.
    """
    job_id = str(uuid.uuid4())
    
    try:
        # Read file contents
        episode_json_content = await episode_json.read()
        transcript_srt_content = await transcript_srt.read()
        
        # Parse episode title from JSON
        try:
            episode_data = json.loads(episode_json_content)
            episode_title = episode_data.get("title", "Unknown")
            episode_id = episode_data.get("id", job_id)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        
        # Background ingestion task
        def ingest_task():
            try:
                ingestion_jobs[job_id] = "processing"
                
                # Create temp directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Save files
                    json_path = temp_path / "episode.json"
                    srt_path = temp_path / "transcript.srt"
                    
                    with open(json_path, "wb") as f:
                        f.write(episode_json_content)
                    
                    with open(srt_path, "wb") as f:
                        f.write(transcript_srt_content)
                    
                    # Ingest using unified function
                    result = ingest_episode(
                        episode_json_path=str(json_path),
                        transcript_srt_path=str(srt_path),
                        force=False,
                        chunk_size=chunk_size
                    )
                    
                    if result["success"]:
                        ingestion_jobs[job_id] = "completed"
                    else:
                        ingestion_jobs[job_id] = f"failed: {result.get('error', 'Unknown error')}"
                
            except Exception as e:
                ingestion_jobs[job_id] = f"failed: {str(e)}"
        
        # Add background task
        background_tasks.add_task(ingest_task)
        ingestion_jobs[job_id] = "queued"
        
        return {
            "success": True,
            "message": f"Started ingesting: {episode_title}",
            "job_id": job_id,
            "episode_title": episode_title,
            "episode_id": episode_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ============================================================================
# FOLDER INGESTION
# ============================================================================

@router.post("/folder")
async def ingest_folder_endpoint(
    background_tasks: BackgroundTasks,
    folder_path: str = Form(..., description="Path to folder containing episodes"),
    skip_existing: bool = Form(True, description="Skip already ingested episodes"),
    force: bool = Form(False, description="Force overwrite existing episodes"),
    chunk_size: int = Form(3500, description="Chunk size in characters"),
    max_episodes: Optional[int] = Form(None, description="Maximum episodes to ingest")
):
    """
    Ingest multiple episodes from a folder.
    
    Supports both flat structure and subfolder structure:
    
    Flat structure:
      folder/
        ├── episode1.json
        ├── episode1.srt
        ├── episode2.json
        ├── episode2.srt
    
    Subfolder structure:
      folder/
        ├── episode1/
        │   ├── episode.json
        │   └── transcript.srt
        ├── episode2/
        │   ├── episode.json
        │   └── transcript.srt
    
    Processing happens in background.
    """
    job_id = f"folder_{uuid.uuid4().hex[:8]}"
    
    try:
        # Validate folder exists
        folder = Path(folder_path)
        if not folder.exists():
            raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")
        
        if not folder.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {folder_path}")
        
        # Background ingestion task
        def ingest_task():
            try:
                ingestion_jobs[job_id] = "processing"
                
                # Use the unified ingest_folder function
                result = ingest_folder(
                    folder_path=str(folder),
                    force=force,
                    chunk_size=chunk_size,
                    skip_existing=skip_existing,
                    max_episodes=max_episodes
                )
                
                if result["success"]:
                    ingestion_jobs[job_id] = f"completed: {result['successful']} episodes"
                else:
                    ingestion_jobs[job_id] = f"failed: {result.get('error', 'Unknown error')}"
                
            except Exception as e:
                ingestion_jobs[job_id] = f"failed: {str(e)}"
        
        # Add background task
        background_tasks.add_task(ingest_task)
        ingestion_jobs[job_id] = "queued"
        
        return {
            "success": True,
            "message": f"Started folder ingestion: {folder_path}",
            "job_id": job_id,
            "folder_path": folder_path,
            "max_episodes": max_episodes,
            "note": "Check /api/ingest/status/{job_id} for progress"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Folder ingestion failed: {str(e)}")


# ============================================================================
# JOB STATUS
# ============================================================================

@router.get("/status/{job_id}")
async def get_ingestion_status(job_id: str):
    """Get the status of an ingestion job."""
    status = ingestion_jobs.get(job_id, "not_found")
    
    return {
        "job_id": job_id,
        "status": status,
        "is_complete": status in ["completed", "not_found"] or status.startswith("failed") or status.startswith("completed:")
    }


# @router.get("/jobs")
# async def list_jobs():
#     """List all ingestion jobs."""
#     return {
#         "jobs": [
#             {"job_id": job_id, "status": status}
#             for job_id, status in ingestion_jobs.items()
#         ],
#         "total": len(ingestion_jobs)
#     }
    
@router.get("/jobs")
async def list_jobs():
    """List all ingestion jobs."""
    # Return just the jobs array, not wrapped in an object
    return [
        {"job_id": job_id, "status": status}
        for job_id, status in ingestion_jobs.items()
    ]    


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ingestion",
        "active_jobs": len([j for j in ingestion_jobs.values() if j in ["queued", "processing"]])
    }


@router.delete("/jobs/{job_id}")
async def clear_job(job_id: str):
    """Clear a specific job from tracking."""
    if job_id in ingestion_jobs:
        del ingestion_jobs[job_id]
        return {"success": True, "message": f"Job {job_id} cleared"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")


@router.delete("/jobs")
async def clear_all_jobs():
    """Clear all completed jobs from tracking."""
    completed_jobs = [
        job_id for job_id, status in ingestion_jobs.items()
        if status.startswith("completed") or status.startswith("failed")
    ]
    
    for job_id in completed_jobs:
        del ingestion_jobs[job_id]
    
    return {
        "success": True,
        "message": f"Cleared {len(completed_jobs)} completed/failed jobs",
        "remaining_jobs": len(ingestion_jobs)
    }