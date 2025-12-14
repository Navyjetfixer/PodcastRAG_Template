"""
Boilerplate detection and filtering for podcast transcripts.
"""
import re
from typing import List, Dict

# Patterns that indicate boilerplate content
BOILERPLATE_PATTERNS = [
    # Only filter obvious sponsor/ad content
    r'this episode is brought to you by',
    r'thanks to our sponsor',
    r'use promo code',
    r'visit.*\.com.*for.*discount',
]

# Minimum word count for a valid segment
MIN_WORDS = 10  # Reduced from a higher number

# Maximum ratio of special characters to total characters
MAX_SPECIAL_CHAR_RATIO = 0.3

def is_boilerplate(text: str) -> bool:
    """
    Determine if a text segment is boilerplate/low-quality.
    
    Args:
        text: Text segment to check
    
    Returns:
        True if segment should be filtered out
    """
    text_lower = text.lower()
    
    # Check for explicit boilerplate patterns (only obvious ads)
    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    
    # Check minimum word count
    word_count = len(text.split())
    if word_count < MIN_WORDS:
        return True
    
    # Check for excessive special characters (likely corrupt text)
    special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    if len(text) > 0 and (special_chars / len(text)) > MAX_SPECIAL_CHAR_RATIO:
        return True
    
    return False

def filter_boilerplate(segments: List[Dict]) -> List[Dict]:
    """
    Filter out boilerplate segments from a list.
    
    Args:
        segments: List of segment dictionaries with 'text' field
    
    Returns:
        Filtered list of segments
    """
    filtered = []
    for segment in segments:
        text = segment.get('text', '')
        if not is_boilerplate(text):
            filtered.append(segment)
    
    return filtered

def get_filter_stats(original_count: int, filtered_count: int) -> str:
    """
    Get statistics about filtering.
    
    Args:
        original_count: Number of segments before filtering
        filtered_count: Number of segments after filtering
    
    Returns:
        Formatted statistics string
    """
    removed = original_count - filtered_count
    if original_count == 0:
        percentage = 0
    else:
        percentage = (removed / original_count) * 100
    
    return f"Filtered {removed} of {original_count} segments ({percentage:.1f}%)"