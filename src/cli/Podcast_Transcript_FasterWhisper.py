#!/usr/bin/env python3
"""
Podcast Transcriber with faster-whisper support
Version 2.0 - Optimized with faster-whisper (4-10x faster than OpenAI Whisper)

Key improvements:
- faster-whisper library integration (CTranslate2 backend)
- Voice Activity Detection (VAD) for automatic silence skipping
- int8 quantization for CPU (3-4x faster)
- float16 for GPU (10-15x faster)
- Backward compatible with OpenAI Whisper
"""

import requests
import feedparser
import urllib.request
import json
import os
import argparse
from pathlib import Path
from datetime import datetime
import textwrap
from typing import List, Dict, Any, Tuple,Union

current_script_path = Path(__file__)
data_dir_pathlib = current_script_path.parent.parent / 'transcripts'
print(f"Path to Data directory (pathlib): {data_dir_pathlib}")

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("⚠ PyTorch not installed - GPU detection disabled")

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


class PodcastTranscriber:
    def __init__(self, podcast_id: str, output_dir :str = 'transcripts', #Union[str, Path] = data_dir_pathlib,
                 whisper_model: str = "tiny.en", use_timestamps: bool = False,
                 use_faster_whisper: bool = True, beam_size: int = 5, 
                 vad_filter: bool = True):
        self.podcast_id = podcast_id
        self.output_dir = Path(output_dir) if not isinstance(output_dir, Path) else output_dir
        print(f"Output directory set to: {self.output_dir}")
        self.output_dir.mkdir(exist_ok=True)
        self.whisper_model = whisper_model
        self.use_timestamps = use_timestamps
        self.use_faster_whisper = use_faster_whisper and HAS_FASTER_WHISPER
        self.beam_size = beam_size
        self.vad_filter = vad_filter

        # Track processed episodes
        self.tracking_file = self.output_dir / "processed_episodes.json"
        print(f"Tracking file set to: {self.tracking_file}")
        self.processed = self.load_processed_episodes()
        print(f"DEBUG: Loaded {len(self.processed)} processed episodes from file")

        # Master metadata index
        self.metadata_index_file = self.output_dir / "episodes_metadata.json"
        self.metadata_index = self.load_metadata_index()

        # Auto-detect best device for Whisper
        if HAS_TORCH and torch.cuda.is_available():
            self.device = "cuda"
            print(f"✓ CUDA GPU detected")
        else:
            self.device = "cpu"
            print(f"ℹ Using CPU")

        # Load Whisper model
        self._load_model()

    def _load_model(self):
        """Load either faster-whisper or OpenAI Whisper model"""
        if self.use_faster_whisper:
            if not HAS_FASTER_WHISPER:
                print("⚠ faster-whisper not installed. Install with: pip install faster-whisper")
                print("⚠ Falling back to OpenAI Whisper")
                self.use_faster_whisper = False
                self._load_openai_whisper()
                return
            
            self._load_faster_whisper()
        else:
            self._load_openai_whisper()

    def _load_faster_whisper(self):
        """Load faster-whisper model (CTranslate2 backend)"""
        # Determine compute type based on device
        if self.device == "cuda":
            self.compute_type = "float16"
            print(f"Using faster-whisper with float16 (GPU acceleration)")
        else:
            self.compute_type = "int8"  # Quantized for CPU speed
            print(f"Using faster-whisper with int8 quantization (CPU optimized)")
        
        print(f"Loading faster-whisper model ({self.whisper_model})...")
        self.model = WhisperModel(
            self.whisper_model,
            device=self.device,
            compute_type=self.compute_type,
            download_root=None
        )
        print(f"✓ faster-whisper model loaded on {self.device.upper()}")
        print(f"  Beam size: {self.beam_size}")
        print(f"  VAD filter: {'enabled' if self.vad_filter else 'disabled'}")

    def _load_openai_whisper(self):
        """Load original OpenAI Whisper model"""
        if not HAS_WHISPER:
            raise ImportError("Neither faster-whisper nor whisper is installed. "
                            "Install with: pip install faster-whisper OR pip install openai-whisper")
        
        self.use_fp16 = self.device == "cuda"
        print(f"Loading OpenAI Whisper model ({self.whisper_model})...")
        self.model = whisper.load_model(
            self.whisper_model,
            device=self.device,
            download_root=None
        )
        print(f"✓ OpenAI Whisper model loaded on {self.device.upper()}")

    # --- Persistence helpers ---

    def load_processed_episodes(self) -> Dict[str, Any]:
        """Load list of already processed episode IDs"""
        if self.tracking_file.exists():
            print(f"Loading processed episodes from: {self.tracking_file}")
            with open(self.tracking_file, 'r') as f:
                return json.load(f)
        return {}

    def save_processed_episodes(self) -> None:
        """Save updated list of processed episodes"""
        with open(self.tracking_file, 'w') as f:
            json.dump(self.processed, f, indent=2)

    def load_metadata_index(self) -> Dict[str, Any]:
        """Load master metadata index"""
        if self.metadata_index_file.exists():
            with open(self.metadata_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "podcast_info": {
                "id": self.podcast_id,
                "name": "Unknown",
                "last_updated": None
            },
            "episodes": {}
        }

    def save_metadata_index(self) -> None:
        """Save master metadata index"""
        self.metadata_index["podcast_info"]["last_updated"] = datetime.now().isoformat()
        with open(self.metadata_index_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata_index, f, indent=2, ensure_ascii=False)

    # --- Podcast feed/API utilities ---

    def get_podcast_feed(self) -> str:
        """Get RSS feed URL from iTunes API"""
        print(f"Fetching podcast info for ID: {self.podcast_id}")
        itunes_api = f"https://itunes.apple.com/lookup?id={self.podcast_id}&entity=podcast"

        try:
            response = requests.get(itunes_api, timeout=10)
            response.raise_for_status()
            data = response.json()
            print(f"Podcast data: {data['resultCount']}")

            if data['resultCount'] == 0:
                raise Exception("Podcast not found")

            rss_url = data['results'][0]['feedUrl']
            podcast_name = data['results'][0]['collectionName']

            # Update podcast info in metadata index
            self.metadata_index["podcast_info"]["name"] = podcast_name

            print(f"Found podcast: {podcast_name}")
            return rss_url

        except Exception as e:
            print(f"Error fetching podcast info: {e}")
            return None

    def parse_duration(self, duration_str: str) -> int:
        """Convert duration string to seconds"""
        if not duration_str:
            return None

        try:
            # If already in seconds
            if str(duration_str).isdigit():
                return int(duration_str)

            # Parse HH:MM:SS or MM:SS format
            parts = str(duration_str).split(':')
            if len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return duration_str  # Return as-is if parsing fails

        return None

    def get_episodes(self, rss_url: str) -> List[Dict[str, Any]]:
        """Parse RSS feed and extract episode information using feedparser"""
        print("Parsing RSS feed...")

        try:
            # Fetch RSS feed with proper headers (required for some hosts like Megaphone)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            # Fetch with requests first to get proper headers through
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse the fetched content
            feed = feedparser.parse(response.content)
            print(f"Found {len(feed.entries)} total episodes")
            
            episodes: List[Dict[str, Any]] = []

            for entry in feed.entries:
                # Find audio URL - check enclosures first (most common)
                audio_url = None
                file_size = None

                # Check enclosures (where podcast audio URLs are typically stored)
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        enc_type = enclosure.get('type', '').lower()
                        enc_href = enclosure.get('href', '')
                        
                        if ('audio' in enc_type or 
                            enc_href.endswith('.mp3') or 
                            enc_href.endswith('.m4a')):
                            audio_url = enc_href
                            file_size = enclosure.get('length', None)
                            break

                # Fallback: check links for audio
                if not audio_url and hasattr(entry, 'links'):
                    for link in entry.links:
                        if 'audio' in link.get('type', ''):
                            audio_url = link.get('href')
                            file_size = link.get('length', None)
                            break

                if not audio_url:
                    continue

                episode_id = entry.get('id', audio_url)

                title = entry.get('title', 'Unknown')
                published = entry.get('published', 'Unknown')
                description = entry.get('summary', '')

                episode_number = entry.get('itunes_episode', None)
                duration = self.parse_duration(entry.get('itunes_duration', None))

                keywords = []
                if hasattr(entry, 'tags'):
                    keywords = [tag.term for tag in entry.tags]

                episodes.append({
                    'id': episode_id,
                    'title': title,
                    'published': published,
                    'audio_url': audio_url,
                    'description': description,
                    'episode_number': episode_number,
                    'keywords': keywords,
                    'duration': duration,
                    'file_size': file_size
                })

            return episodes

        except Exception as e:
            print(f"Error parsing RSS feed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        return filename[:200]  # Limit length

    # --- Audio I/O and transcription ---

    def download_audio(self, url: str, output_path: str) -> bool:
        """Download audio file from URL"""
        try:
            print("Downloading audio...")
            
            # Use requests instead of urllib for better SSL handling
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            
            # Get total file size for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress bar
            with open(output_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    chunk_size = 8192
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # Simple progress indicator
                            progress = (downloaded / total_size) * 100
                            if downloaded % (chunk_size * 100) == 0:  # Update every ~800KB
                                print(f"  Downloaded: {progress:.1f}%", end='\r')
            
            print(f"  Downloaded: 100.0%")
            print(f"✓ Download complete: {os.path.basename(output_path)}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"Error downloading: {e}")
            return False
        except Exception as e:
            print(f"Error downloading: {e}")
            return False
    def transcribe_audio(self, audio_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Transcribe audio using faster-whisper or OpenAI Whisper"""
        if self.use_faster_whisper:
            return self._transcribe_faster_whisper(audio_path)
        else:
            return self._transcribe_openai_whisper(audio_path)

    def _transcribe_faster_whisper(self, audio_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Transcribe using faster-whisper (CTranslate2)"""
        try:
            print(f"  Transcribing with faster-whisper...")
            
            # Configure transcription parameters
            transcribe_params = {
                "language": "en",
                "beam_size": self.beam_size,
            }
            
            # Add VAD if enabled
            if self.vad_filter:
                transcribe_params["vad_filter"] = True
                transcribe_params["vad_parameters"] = dict(
                    min_silence_duration_ms=500,
                    threshold=0.5
                )
            
            # faster-whisper returns a generator for segments
            segments_generator, info = self.model.transcribe(
                str(audio_path),
                **transcribe_params
            )
            
            # Convert generator to list and build transcript
            segments_list = []
            transcript_parts = []
            
            for segment in segments_generator:
                # Convert faster-whisper Segment to dict format
                segment_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                }
                segments_list.append(segment_dict)
                transcript_parts.append(segment.text)
            
            # Join all text parts
            transcript = " ".join(transcript_parts).strip()
            
            print(f"  ✓ Transcribed {len(segments_list)} segments")
            return transcript, segments_list
            
        except Exception as e:
            print(f"  Error transcribing: {e}")
            import traceback
            traceback.print_exc()
            return None, []

    def _transcribe_openai_whisper(self, audio_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Transcribe using OpenAI Whisper"""
        try:
            print(f"  Transcribing with OpenAI Whisper...")
            result = self.model.transcribe(
                str(audio_path),
                language="en",
                fp16=self.use_fp16
            )
            transcript = result.get("text", "")
            segments = result.get("segments", [])
            print(f"  ✓ Transcribed {len(segments)} segments")
            return transcript, segments
        except Exception as e:
            print(f"  Error transcribing: {e}")
            import traceback
            traceback.print_exc()
            return None, []

    # --- Timestamp helpers (for optional timestamped transcripts) ---

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Format seconds to HH:MM:SS,mmm (SRT-style)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    @staticmethod
    def format_srt(segments: List[Dict[str, Any]]) -> str:
        """Convert Whisper segments to an SRT-like transcript"""
        lines: List[str] = []
        for i, seg in enumerate(segments, start=1):
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            text = seg.get("text", "").strip()
            lines.append(str(i))
            lines.append(f"{PodcastTranscriber.format_timestamp(start)} --> {PodcastTranscriber.format_timestamp(end)}")
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    # --- Episode processing ---

    def process_episode(self, episode: Dict[str, Any]) -> bool:
        """Download and transcribe a single episode"""
        episode_id = episode['id']
        title = episode['title']
        episode_number = episode['episode_number']

        print(f"\nProcessing: {title}")
        # Output episode metadata for web UI parsing
        print(f"EPISODE_META: {{\"episode_number\": {episode_number}, \"published\": \"{episode.get('published', 'Unknown')}\", \"duration\": {episode.get('duration', 0)}}}")

        # Create safe filename
        safe_title = self.sanitize_filename(title)
        audio_file = self.output_dir / f"{safe_title}.mp3"
        transcript_file = self.output_dir / f"{safe_title}.txt"
        metadata_file = self.output_dir / f"{safe_title}.json"

        # Optional: timestamped outputs
        transcript_srt_file = self.output_dir / f"{safe_title}.srt"
        transcript_json_file = self.output_dir / f"{safe_title}_timestamps.json"

        # Download audio
        if not self.download_audio(episode['audio_url'], audio_file):
            return False

        # Transcribe
        transcript, segments = self.transcribe_audio(audio_path=audio_file)
        if transcript is None:
            # Clean up audio file even if transcription fails
            if audio_file.exists():
                os.remove(audio_file)
                print(f"  ✗ Transcription failed - audio file deleted")
            return False

        # Save plain transcript with line wrapping using specified TextWrapper
        wrapper = textwrap.TextWrapper(width=110, break_long_words=False, break_on_hyphens=False, fix_sentence_endings=True)
        wrapped_transcript = wrapper.fill(transcript)

        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(wrapped_transcript)

        # If timestamps requested, generate SRT and JSON payload
        if self.use_timestamps and segments:
            srt_text = self.format_srt(segments)
            with open(transcript_srt_file, 'w', encoding='utf-8') as f:
                f.write(srt_text)

            timestamp_payload = [
                {"start": float(seg.get("start", 0.0)),
                 "end": float(seg.get("end", 0.0)),
                 "text": seg.get("text", "").strip()}
                for seg in segments
            ]
            with open(transcript_json_file, 'w', encoding='utf-8') as f:
                json.dump(timestamp_payload, f, indent=2, ensure_ascii=False)
        else:
            transcript_srt_file = None
            transcript_json_file = None

        # Create metadata object
        metadata = {
            'title': title,
            'published': episode['published'],
            'audio_url': episode['audio_url'],
            'description': episode['description'],
            'episode_number': episode_number,
            'duration': episode['duration'],
            'keywords': episode['keywords'],
            'file_size': episode['file_size'],
            'transcript_file': f"{safe_title}.txt",
            'transcribed_on': datetime.now().isoformat(),
            'transcript_srt_file': str(transcript_srt_file) if transcript_srt_file else None,
            'transcript_json_file': str(transcript_json_file) if transcript_json_file else None,
            'whisper_backend': 'faster-whisper' if self.use_faster_whisper else 'openai-whisper',
            'whisper_model': self.whisper_model,
            'device': self.device
        }

        # Save individual metadata file
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Add to master metadata index
        index_key = str(episode_number) if episode_number else f"ep_{len(self.metadata_index['episodes']) + 1}"
        self.metadata_index["episodes"][index_key] = metadata
        self.save_metadata_index()

        # Delete audio file to save space
        if audio_file.exists():
            os.remove(audio_file)
            print(f"  ✓ Transcript saved - audio file deleted")
        else:
            print(f"  ✓ Transcript saved")

        return True

    # --- Runner ---

    def run(self, max_episodes: int = None, skip_processed: bool = True) -> None:
        """Main processing loop"""
        # Get RSS feed
        rss_url = self.get_podcast_feed()
        if not rss_url:
            return

        # Get all episodes
        episodes = self.get_episodes(rss_url)
        print(f"\nFound {len(episodes)} total episodes")

        if not episodes:
            print("No episodes found in RSS feed!")
            return
        
        
            # ADD THESE DEBUG LINES HERE (after line 429)
        print(f"\n--- DEBUG INFO ---")
        print(f"Sample episode IDs from feed:")
        for ep in episodes[:3]:
            print(f"  {ep['id']}")
        print(f"\nSample processed IDs:")
        for ep_id in list(self.processed.keys())[:3]:
            print(f"  {ep_id}")
        print(f"--- END DEBUG ---\n")
        # END OF DEBUG LINES

        # Filter out already processed episodes
        if skip_processed:
            new_episodes = [ep for ep in episodes if ep['id'] not in self.processed]
            print(f"New episodes to process: {len(new_episodes)}")
        else:
            new_episodes = episodes
            print(f"Processing all episodes (including already processed)")

        if not new_episodes:
            print("No new episodes to process!")
            return

        # Limit number of episodes if specified
        if max_episodes:
            new_episodes = new_episodes[:max_episodes]
            print(f"Processing {len(new_episodes)} episodes (limited by --max-episodes)")

        # Process each episode
        successful = 0
        for i, episode in enumerate(new_episodes, 1):
            print(f"\n[{i}/{len(new_episodes)}]", end=" ")
            if self.process_episode(episode):
                self.processed[episode['id']] = {
                    'title': episode['title'],
                    'episode_number': episode['episode_number'],
                    'processed_on': datetime.now().isoformat()
                }
                self.save_processed_episodes()
                successful += 1
            else:
                print("  ✗ Failed to process episode")

        print(f"\n{'='*60}")
        print(f"Processing complete!")
        print(f"Successfully transcribed: {successful}/{len(new_episodes)} episodes")
        print(f"Total processed episodes: {len(self.processed)}")
        print(f"Transcripts saved in: {self.output_dir}")
        print(f"Master metadata: {self.metadata_index_file}")


# --- CLI entrypoint ---

def main():
    parser = argparse.ArgumentParser(
        description='Transcribe podcast episodes using Whisper AI (OpenAI or faster-whisper)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process 1 episode with faster-whisper tiny.en (default, fastest)
  python podcast_transcriber.py -n 1
  
  # Use higher quality model
  python podcast_transcriber.py -n 1 --model small.en
  
  # Use original OpenAI Whisper
  python podcast_transcriber.py -n 1 --use-openai-whisper
  
  # Ultra-fast mode (beam_size=1, no VAD)
  python podcast_transcriber.py -n 5 --beam-size 1 --no-vad
  
  # High quality mode
  python podcast_transcriber.py -n 5 --beam-size 5 --model medium.en
  
  # Process different podcast
  python podcast_transcriber.py --podcast-id 1234567890 -n 3
  
  # Reprocess episodes (ignore tracking)
  python podcast_transcriber.py -n 2 --reprocess
        '''
    )

    parser.add_argument(
        '--podcast-id',
        type=str,
        default='1681418502',
        help='iTunes podcast ID (default: 1681418502 - Data Over Dogma)'
    )

    parser.add_argument(
        '--max-episodes', '-n',
        type=int,
        default=None,
        help='Maximum number of episodes to process (default: all new episodes)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=None,
        help='Output directory for transcripts (default: transcripts)'
    )

    parser.add_argument(
        '--model', '-m',
        type=str,
        default='tiny.en',
        choices=['tiny', 'tiny.en', 'base', 'base.en', 'small', 'small.en', 'medium', 'medium.en', 'large', 'large-v2', 'large-v3'],
        help='Whisper model to use (default: tiny.en)'
    )

    parser.add_argument(
        '--timestamps',
        action='store_true',
        help='Include per-segment timestamps in transcripts (SRT/JSON)'
    )

    parser.add_argument(
        '--reprocess',
        action='store_true',
        help='Reprocess episodes even if already transcribed'
    )

    parser.add_argument(
        '--use-openai-whisper',
        action='store_true',
        help='Use original OpenAI Whisper instead of faster-whisper'
    )

    parser.add_argument(
        '--beam-size',
        type=int,
        default=5,
        help='Beam size for decoding (1=fastest, 5=best quality, default: 5)'
    )

    parser.add_argument(
        '--no-vad',
        action='store_true',
        help='Disable Voice Activity Detection (process all audio including silence)'
    )

    args = parser.parse_args()

    # Create transcriber and run
    print(f"Configuration:")
    print(f"  Podcast ID: {args.podcast_id}")
    print(f"  Max episodes: {args.max_episodes if args.max_episodes else 'All new episodes'}")
    print(f"  Output directory: {args.output_dir if args.output_dir else data_dir_pathlib}")
    print(f"  Whisper model: {args.model}")
    print(f"  Backend: {'OpenAI Whisper' if args.use_openai_whisper else 'faster-whisper (recommended)'}")
    print(f"  Beam size: {args.beam_size}")
    print(f"  VAD filter: {not args.no_vad}")
    print(f"  Reprocess: {args.reprocess}")
    print(f"  Timestamps: {args.timestamps}")
    print()

  # Build kwargs, only include output_dir if it's not None
    transcriber_kwargs = {
        'podcast_id': args.podcast_id,
        'whisper_model': args.model,
        'use_timestamps': args.timestamps,
        'use_faster_whisper': not args.use_openai_whisper,
        'beam_size': args.beam_size,
        'vad_filter': not args.no_vad
    }
    
    if args.output_dir is not None:
        transcriber_kwargs['output_dir'] = args.output_dir
    
    transcriber = PodcastTranscriber(**transcriber_kwargs)
    
    transcriber.run(
        max_episodes=args.max_episodes,
        skip_processed=not args.reprocess
    )


if __name__ == "__main__":
    main()
