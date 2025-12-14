"""
Transcription endpoints for downloading and transcribing podcast episodes.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
import sys
from pathlib import Path
import uuid
import requests
import feedparser
import subprocess
import json
import os
from config.settings import TRANSCRIPTS_DIR

router = APIRouter()

# Track transcription jobs in memory (use Redis/DB in production)
transcription_jobs: Dict[str, Dict] = {}

# Path to the transcription script
SCRIPT_DIR = Path(__file__).parent.parent.parent
TRANSCRIBE_SCRIPT = SCRIPT_DIR  / "cli" / "Podcast_Transcript_FasterWhisper.py"

# Check if script exists
HAS_TRANSCRIBER = TRANSCRIBE_SCRIPT.exists()

# ============================================================================
# MODELS
# ============================================================================

class TranscriptionConfig(BaseModel):
    """Configuration for transcription job."""
    podcast_id: str = "1681418502"
    max_episodes: Optional[int] = 1
    whisper_model: str = "tiny.en"
    beam_size: int = 5
    use_timestamps: bool = True
    reprocess: bool = False
    use_openai_whisper: bool = False
    vad_filter: bool = True
    output_dir: Optional[str] = None


class EpisodeStatus(BaseModel):
    """Status of a single episode."""
    title: str
    episode_number: Optional[int]
    published: Optional[str]
    duration: Optional[int]
    description: Optional[str]
    status: str  # queued, downloading, transcribing, completed, failed
    progress_detail: Optional[str] = None


class JobStatus(BaseModel):
    """Status of transcription job."""
    job_id: str
    status: str  # queued, processing, completed, failed
    progress: float  # 0-100
    total: int
    completed: int
    current_episode: Optional[str]
    episodes: List[EpisodeStatus]
    is_complete: bool
    error: Optional[str] = None


# ============================================================================
# PODCAST INFO
# ============================================================================

@router.get("/info/{podcast_id}")
async def get_podcast_info(podcast_id: str):
    """Get podcast information from iTunes API."""
    try:
        # Fetch from iTunes API
        itunes_api = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
        response = requests.get(itunes_api, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['resultCount'] == 0:
            raise HTTPException(status_code=404, detail="Podcast not found")
        
        podcast_data = data['results'][0]
        rss_url = podcast_data['feedUrl']
        
        # Parse RSS to count episodes
        feed = feedparser.parse(rss_url)
        total_episodes = len(feed.entries)
        
        # Count new episodes (check against processed_episodes.json)
        output_dir = TRANSCRIPTS_DIR
        tracking_file = TRANSCRIPTS_DIR / "processed_episodes.json"
        processed_count = 0
        
        if tracking_file.exists():
            with open(tracking_file, 'r') as f:
                processed = json.load(f)
                processed_count = len(processed)
        
        new_episodes = max(0, total_episodes - processed_count)
        
        return {
            "success": True,
            "name": podcast_data['collectionName'],
            "artist": podcast_data.get('artistName', 'Unknown'),
            "total_episodes": total_episodes,
            "new_episodes": new_episodes,
            "processed_episodes": processed_count,
            "rss_url": rss_url,
            "artwork": podcast_data.get('artworkUrl600', ''),
            "genres": podcast_data.get('genres', [])
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch podcast info: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# START TRANSCRIPTION
# ============================================================================

@router.post("/start")
async def start_transcription(
    config: TranscriptionConfig,
    background_tasks: BackgroundTasks
):
    """Start a transcription job."""
    if not HAS_TRANSCRIBER:
        raise HTTPException(
            status_code=503,
            detail=f"Transcription script not found at: {TRANSCRIBE_SCRIPT}"
        )
    
    job_id = f"transcribe_{uuid.uuid4().hex[:8]}"
    
    # Initialize job status
    transcription_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "total": config.max_episodes or 0,
        "completed": 0,
        "current_episode": None,
        "episodes": [],
        "is_complete": False,
        "error": None,
        "config": config.dict()
    }
    
    # Build command arguments
    def transcribe_task():
        try:
            transcription_jobs[job_id]["status"] = "processing"
            
            # Build command
            cmd = [
                sys.executable,
                str(TRANSCRIBE_SCRIPT),
                "--podcast-id", config.podcast_id,
                "--model", config.whisper_model,
                "--beam-size", str(config.beam_size)
            ]
            
            if config.max_episodes:
                cmd.extend(["-n", str(config.max_episodes)])
            
            if config.use_timestamps:
                cmd.append("--timestamps")
            
            if config.reprocess:
                cmd.append("--reprocess")
            
            if config.use_openai_whisper:
                cmd.append("--use-openai-whisper")
            
            if not config.vad_filter:
                cmd.append("--no-vad")
            
            if config.output_dir:
                cmd.extend(["-o", config.output_dir])
            else:
                cmd.extend(["-o", str(TRANSCRIPTS_DIR)])
            
            # Run the script with proper encoding and memory settings
            print(f"Running command: {' '.join(cmd)}")
            
            # Set environment to use UTF-8 and optimize memory
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'  # Disable output buffering
            
            # Run with proper encoding
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid chars instead of crashing
                bufsize=1,  # Line buffered
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Monitor output
            current_episode_title = None
            episodes_dict = {}
            total_episodes = config.max_episodes or 0
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                    
                print(line)  # Log to console
                
                # Parse total episodes from output
                if "New episodes to process:" in line:
                    try:
                        total = int(line.split(":")[-1].strip())
                        if config.max_episodes:
                            total = min(total, config.max_episodes)
                        transcription_jobs[job_id]["total"] = total
                        total_episodes = total
                    except:
                        pass
                
                # Parse processing stages
                if "Processing:" in line:
                    current_episode_title = line.split("Processing:", 1)[1].strip()
                    transcription_jobs[job_id]["current_episode"] = current_episode_title

                    episode_status = {
                        "title": current_episode_title,
                        "episode_number": None,
                        "published": None,
                        "duration": None,
                        "description": None,
                        "status": "queued",
                        "progress_detail": "Queued for processing"
                    }
                    episodes_dict[current_episode_title] = episode_status
                    transcription_jobs[job_id]["episodes"] = list(episodes_dict.values())

                elif "EPISODE_META:" in line and current_episode_title:
                    # Parse episode metadata: EPISODE_META: {"episode_number": 123, "published": "...", "duration": 456}
                    try:
                        meta_json = line.split("EPISODE_META:", 1)[1].strip()
                        metadata = json.loads(meta_json)
                        episodes_dict[current_episode_title]["episode_number"] = metadata.get("episode_number")
                        episodes_dict[current_episode_title]["published"] = metadata.get("published")
                        episodes_dict[current_episode_title]["duration"] = metadata.get("duration")
                        transcription_jobs[job_id]["episodes"] = list(episodes_dict.values())
                    except Exception as e:
                        print(f"Failed to parse episode metadata: {e}")
                
                elif "Downloading audio" in line and current_episode_title:
                    episodes_dict[current_episode_title]["status"] = "downloading"
                    episodes_dict[current_episode_title]["progress_detail"] = "Downloading audio..."
                    transcription_jobs[job_id]["episodes"] = list(episodes_dict.values())
                
                elif "Transcribing with" in line and current_episode_title:
                    episodes_dict[current_episode_title]["status"] = "transcribing"
                    episodes_dict[current_episode_title]["progress_detail"] = "Transcribing with Whisper..."
                    transcription_jobs[job_id]["episodes"] = list(episodes_dict.values())
                
                elif "Transcript saved" in line and current_episode_title:
                    episodes_dict[current_episode_title]["status"] = "completed"
                    episodes_dict[current_episode_title]["progress_detail"] = "✅ Transcription complete"
                    transcription_jobs[job_id]["completed"] += 1
                    
                    # Update progress
                    if total_episodes > 0:
                        progress = (transcription_jobs[job_id]["completed"] / total_episodes) * 100
                        transcription_jobs[job_id]["progress"] = progress
                    
                    transcription_jobs[job_id]["episodes"] = list(episodes_dict.values())
                
                elif "Error transcribing:" in line and current_episode_title:
                    # Extract just the error message
                    error_msg = line.split("Error transcribing:", 1)[1].strip() if ":" in line else line
                    episodes_dict[current_episode_title]["status"] = "failed"
                    episodes_dict[current_episode_title]["progress_detail"] = f"❌ {error_msg[:100]}"
                    transcription_jobs[job_id]["episodes"] = list(episodes_dict.values())
                
                elif "Successfully transcribed:" in line:
                    try:
                        parts = line.split("Successfully transcribed:", 1)[1].strip()
                        completed = int(parts.split("/")[0])
                        transcription_jobs[job_id]["completed"] = completed
                    except:
                        pass
            
            # Wait for completion
            return_code = process.wait()
            
            # Update final status
            if return_code == 0:
                transcription_jobs[job_id]["status"] = "completed"
                transcription_jobs[job_id]["progress"] = 100
            else:
                transcription_jobs[job_id]["status"] = "failed"
                transcription_jobs[job_id]["error"] = f"Script exited with code {return_code}"
            
            transcription_jobs[job_id]["is_complete"] = True
            
        except Exception as e:
            transcription_jobs[job_id]["status"] = "failed"
            transcription_jobs[job_id]["is_complete"] = True
            transcription_jobs[job_id]["error"] = str(e)
            print(f"❌ Error in transcription task: {e}")
            import traceback
            traceback.print_exc()
    
    # Add background task
    background_tasks.add_task(transcribe_task)
    
    return {
        "success": True,
        "message": "Transcription job started",
        "job_id": job_id
    }


# ============================================================================
# JOB STATUS
# ============================================================================

@router.get("/status/{job_id}")
async def get_transcription_status(job_id: str):
    """Get the status of a transcription job."""
    if job_id not in transcription_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return transcription_jobs[job_id]


@router.post("/stop/{job_id}")
async def stop_transcription(job_id: str):
    """Stop a transcription job."""
    if job_id not in transcription_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Mark as stopped (actual process stopping would require tracking the subprocess)
    transcription_jobs[job_id]["status"] = "stopped"
    transcription_jobs[job_id]["is_complete"] = True
    
    return {
        "success": True,
        "message": "Transcription job stopped (process may still be running)"
    }


@router.get("/jobs")
async def list_transcription_jobs():
    """List all transcription jobs."""
    return {
        "jobs": list(transcription_jobs.values()),
        "total": len(transcription_jobs)
    }


@router.delete("/jobs/{job_id}")
async def clear_transcription_job(job_id: str):
    """Clear a specific transcription job."""
    if job_id in transcription_jobs:
        del transcription_jobs[job_id]
        return {"success": True, "message": f"Job {job_id} cleared"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check for transcription service."""
    
    # Check if dependencies are installed
    dependencies_ok = True
    missing_deps = []
    
    try:
        import faster_whisper
    except ImportError:
        dependencies_ok = False
        missing_deps.append("faster-whisper")
    
    return {
        "status": "healthy" if (HAS_TRANSCRIBER and dependencies_ok) else "degraded",
        "service": "transcription",
        "has_script": HAS_TRANSCRIBER,
        "script_path": str(TRANSCRIBE_SCRIPT),
        "dependencies_ok": dependencies_ok,
        "missing_dependencies": missing_deps,
        "active_jobs": len([j for j in transcription_jobs.values() if j["status"] == "processing"])
    }