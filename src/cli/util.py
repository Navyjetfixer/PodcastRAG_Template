"""
Utility functions for CLI operations.
"""
from pathlib import Path
from typing import List, Dict
import re

def parse_srt(srt_path: str) -> List[Dict]:
    """
    Parse an SRT file into a list of segments.
    
    Args:
        srt_path: Path to the SRT file
    
    Returns:
        List of dictionaries with segment data
    """
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by double newlines to separate segments
    raw_segments = content.strip().split('\n\n')
    
    segments = []
    for raw_seg in raw_segments:
        lines = raw_seg.strip().split('\n')
        if len(lines) < 3:
            continue
        
        try:
            # Line 0: index
            index = int(lines[0])
            
            # Line 1: timestamps
            timestamps = lines[1]
            start_time, end_time = timestamps.split(' --> ')
            
            # Lines 2+: text
            text = ' '.join(lines[2:])
            
            segments.append({
                'index': index,
                'start_time': start_time.strip(),
                'end_time': end_time.strip(),
                'text': text.strip()
            })
        except (ValueError, IndexError) as e:
            print(f"Warning: Could not parse segment: {raw_seg[:50]}... Error: {e}")
            continue
    
    return segments

def reconstruct_full_text_from_srt(srt_segments: List[Dict]) -> str:
    """
    Reconstruct full transcript text from SRT segments.
    
    This function combines all SRT segment texts into a single continuous
    transcript, applying the same cleaning that read_transcript_txt() used to do.
    
    Args:
        srt_segments: List of parsed SRT segments with 'text' field
    
    Returns:
        Clean full transcript text
    """
    if not srt_segments:
        return ""
    
    # Join all segment texts with spaces
    full_text = ' '.join(seg['text'].strip() for seg in srt_segments)
    
    # Clean up formatting (same as read_transcript_txt did)
    full_text = re.sub(r'\n\s*\n', '\n\n', full_text)  # Normalize paragraph breaks
    full_text = re.sub(r' +', ' ', full_text)  # Remove multiple spaces
    
    return full_text.strip()

def read_transcript_txt(txt_path: str) -> str:
    """
    Read a plain text transcript file.
    
    DEPRECATED: This function is kept for backwards compatibility.
    New code should use reconstruct_full_text_from_srt() instead.
    
    Args:
        txt_path: Path to the TXT file
    
    Returns:
        Full transcript text
    """
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Clean up extra whitespace
    content = re.sub(r'\n\s*\n', '\n\n', content)  # Normalize paragraph breaks
    content = re.sub(r' +', ' ', content)  # Remove multiple spaces
    
    return content.strip()

def format_time(seconds: float) -> str:
    """
    Convert seconds to SRT time format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
    
    Returns:
        Formatted time string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def parse_srt_time(time_str: str) -> float:
    """
    Convert SRT time format to seconds.
    
    Args:
        time_str: Time string in format HH:MM:SS,mmm
    
    Returns:
        Time in seconds
    """
    # Handle both comma and period as decimal separator
    time_str = time_str.replace(',', '.')
    
    # Parse: HH:MM:SS.mmm
    pattern = r'(\d+):(\d+):(\d+)\.(\d+)'
    match = re.match(pattern, time_str)
    
    if not match:
        return 0.0
    
    hours, minutes, seconds, millis = match.groups()
    
    total_seconds = (
        int(hours) * 3600 +
        int(minutes) * 60 +
        int(seconds) +
        int(millis) / 1000
    )
    
    return total_seconds

def validate_episode_files(episode_json: str, transcript_srt: str) -> bool:
    """
    Validate that all required files exist.
    
    Args:
        episode_json: Path to episode JSON
        transcript_srt: Path to SRT file
    
    Returns:
        True if all files exist
    """
    files = [episode_json, transcript_srt]
    missing = []
    
    for file_path in files:
        if not Path(file_path).exists():
            missing.append(file_path)
    
    if missing:
        print("❌ Missing files:")
        for f in missing:
            print(f"   - {f}")
        return False
    
    return True

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def format_score(score: float) -> str:
    """
    Format similarity score as percentage.
    
    Args:
        score: Similarity score (0-1)
    
    Returns:
        Formatted string
    """
    return f"{score * 100:.1f}%"

def print_segment_preview(segment: Dict, index: int = 1):
    """
    Print a nicely formatted segment preview.
    
    Args:
        segment: Segment dictionary
        index: Segment number
    """
    print(f"\n{index}. [{segment.get('episode_title', 'Unknown')}]")
    
    if 'score' in segment:
        print(f"   Score: {format_score(segment['score'])} | ", end="")
    
    if 'start_time' in segment and 'end_time' in segment:
        print(f"Time: {segment['start_time']} - {segment['end_time']}")
    else:
        print()
    
    text = segment.get('text', '')
    print(f"   {truncate_text(text, 200)}")
    
    if 'word_count' in segment:
        print(f"   Words: {segment['word_count']}")