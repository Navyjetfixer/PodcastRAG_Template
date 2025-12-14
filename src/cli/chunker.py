"""
Semantic chunking for podcast transcripts.
"""
from typing import List, Dict
import re

def create_semantic_chunks(
    full_text: str,
    srt_segments: List[Dict],
    max_words: int = 500,
    overlap_words: int = 50
) -> List[Dict]:
    """
    Create semantic chunks from transcript with timing information.
    
    This function combines SRT segments into larger semantic chunks while
    preserving timing information. It tries to break at natural boundaries
    (sentence ends) when possible.
    
    Args:
        full_text: Full transcript text
        srt_segments: List of SRT segment dictionaries with timing
        max_words: Maximum words per chunk
        overlap_words: Number of words to overlap between chunks
    
    Returns:
        List of chunk dictionaries with text, timing, and metadata
    """
    if not srt_segments:
        return []
    
    chunks = []
    current_chunk_text = []
    current_chunk_word_count = 0
    current_chunk_start = srt_segments[0]['start_time']
    current_chunk_segments = []
    chunk_id = 0
    
    for seg in srt_segments:
        seg_text = seg['text'].strip()
        seg_words = seg_text.split()
        seg_word_count = len(seg_words)
        
        # Check if adding this segment would exceed max_words
        if current_chunk_word_count + seg_word_count > max_words and current_chunk_text:
            # Save current chunk
            chunk_text = ' '.join(current_chunk_text)
            chunks.append({
                'chunk_id': chunk_id,
                'text': chunk_text,
                'start_time': current_chunk_start,
                'end_time': current_chunk_segments[-1]['end_time'],
                'word_count': current_chunk_word_count,
                'segment_count': len(current_chunk_segments)
            })
            
            chunk_id += 1
            
            # Start new chunk with overlap
            if overlap_words > 0 and current_chunk_word_count > overlap_words:
                # Get last N words for overlap
                all_words = ' '.join(current_chunk_text).split()
                overlap_text = ' '.join(all_words[-overlap_words:])
                current_chunk_text = [overlap_text]
                current_chunk_word_count = overlap_words
            else:
                current_chunk_text = []
                current_chunk_word_count = 0
            
            current_chunk_start = seg['start_time']
            current_chunk_segments = []
        
        # Add segment to current chunk
        current_chunk_text.append(seg_text)
        current_chunk_word_count += seg_word_count
        current_chunk_segments.append(seg)
    
    # Don't forget the last chunk
    if current_chunk_text:
        chunk_text = ' '.join(current_chunk_text)
        chunks.append({
            'chunk_id': chunk_id,
            'text': chunk_text,
            'start_time': current_chunk_start,
            'end_time': current_chunk_segments[-1]['end_time'],
            'word_count': current_chunk_word_count,
            'segment_count': len(current_chunk_segments)
        })
    
    return chunks


def create_sentence_chunks(
    full_text: str,
    srt_segments: List[Dict],
    max_words: int = 500
) -> List[Dict]:
    """
    Create chunks that break at sentence boundaries.
    
    More sophisticated than simple word-count chunking, but requires
    sentence detection.
    
    Args:
        full_text: Full transcript text
        srt_segments: List of SRT segment dictionaries
        max_words: Target maximum words per chunk
    
    Returns:
        List of chunk dictionaries
    """
    # Split into sentences (basic implementation)
    sentences = re.split(r'[.!?]+\s+', full_text)
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    chunk_id = 0
    
    # Try to map sentences to SRT segments for timing
    seg_index = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        words = sentence.split()
        word_count = len(words)
        
        # If adding this sentence exceeds limit, start new chunk
        if current_word_count + word_count > max_words and current_chunk:
            # Find timing from segments
            chunk_text = ' '.join(current_chunk)
            
            # Estimate timing (simplified - could be improved)
            if seg_index < len(srt_segments):
                start_time = srt_segments[max(0, seg_index - len(current_chunk))]['start_time']
                end_time = srt_segments[min(seg_index, len(srt_segments) - 1)]['end_time']
            else:
                start_time = "00:00:00,000"
                end_time = "00:00:00,000"
            
            chunks.append({
                'chunk_id': chunk_id,
                'text': chunk_text,
                'start_time': start_time,
                'end_time': end_time,
                'word_count': current_word_count,
                'segment_count': len(current_chunk)
            })
            
            chunk_id += 1
            current_chunk = []
            current_word_count = 0
        
        current_chunk.append(sentence)
        current_word_count += word_count
        seg_index += 1
    
    # Add final chunk
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        
        if seg_index < len(srt_segments):
            start_time = srt_segments[max(0, seg_index - len(current_chunk))]['start_time']
            end_time = srt_segments[-1]['end_time']
        else:
            start_time = "00:00:00,000"
            end_time = "00:00:00,000"
        
        chunks.append({
            'chunk_id': chunk_id,
            'text': chunk_text,
            'start_time': start_time,
            'end_time': end_time,
            'word_count': current_word_count,
            'segment_count': len(current_chunk)
        })
    
    return chunks


def merge_small_chunks(chunks: List[Dict], min_words: int = 100) -> List[Dict]:
    """
    Merge chunks that are too small with adjacent chunks.
    
    Args:
        chunks: List of chunk dictionaries
        min_words: Minimum words per chunk
    
    Returns:
        List of merged chunks
    """
    if not chunks:
        return []
    
    merged = []
    current = chunks[0].copy()
    
    for i in range(1, len(chunks)):
        chunk = chunks[i]
        
        # If current chunk is too small, merge with next
        if current['word_count'] < min_words:
            # Merge
            current['text'] = current['text'] + ' ' + chunk['text']
            current['end_time'] = chunk['end_time']
            current['word_count'] += chunk['word_count']
            current['segment_count'] += chunk['segment_count']
        else:
            # Save current and start new
            merged.append(current)
            current = chunk.copy()
    
    # Don't forget the last one
    merged.append(current)
    
    # Re-assign chunk IDs
    for i, chunk in enumerate(merged):
        chunk['chunk_id'] = i
    
    return merged


def get_chunk_stats(chunks: List[Dict]) -> Dict:
    """
    Calculate statistics about chunks.
    
    Args:
        chunks: List of chunk dictionaries
    
    Returns:
        Dictionary with statistics
    """
    if not chunks:
        return {
            'count': 0,
            'total_words': 0,
            'avg_words': 0,
            'min_words': 0,
            'max_words': 0
        }
    
    word_counts = [c['word_count'] for c in chunks]
    
    return {
        'count': len(chunks),
        'total_words': sum(word_counts),
        'avg_words': sum(word_counts) / len(word_counts),
        'min_words': min(word_counts),
        'max_words': max(word_counts)
    }