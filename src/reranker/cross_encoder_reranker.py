"""
Cross-encoder re-ranker for improving retrieval quality.

Re-ranking provides a second-stage scoring that's more accurate than
the initial bi-encoder semantic search, at the cost of speed.
"""
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any, Optional
import time


class CrossEncoderReranker:
    """
    Re-rank search results using a cross-encoder model.
    
    Cross-encoders jointly encode query and document, providing more
    accurate relevance scores than bi-encoders (which encode separately).
    
    Trade-off:
    - Bi-encoder (Milvus): Fast, can search millions of docs
    - Cross-encoder (This): Slow, only practical for top-K (e.g., 20-50)
    
    Typical workflow:
    1. Bi-encoder retrieves top 50 candidates (fast)
    2. Cross-encoder re-ranks to top 5 (accurate)
    """
    
    # Available models (ordered by quality/speed tradeoff)
    MODELS = {
        "fast": "cross-encoder/ms-marco-MiniLM-L-2-v2",      # Fastest, good quality
        "balanced": "cross-encoder/ms-marco-MiniLM-L-6-v2",  # Balanced (recommended)
        "quality": "cross-encoder/ms-marco-MiniLM-L-12-v2",  # Best quality, slower
        "large": "cross-encoder/ms-marco-TinyBERT-L-6"       # Alternative balanced
    }
    
    def __init__(
        self,
        model_name: str = "balanced",
        device: Optional[str] = None,
        max_length: int = 512
    ):
        """
        Initialize cross-encoder re-ranker.
        
        Args:
            model_name: Model size ('fast', 'balanced', 'quality', 'large')
                       or full HuggingFace model path
            device: Device to use ('cuda', 'cpu', or None for auto)
            max_length: Maximum sequence length for the model
        """
        # Resolve model name
        if model_name in self.MODELS:
            full_model_name = self.MODELS[model_name]
            self.model_name = model_name
        else:
            full_model_name = model_name
            self.model_name = "custom"
        
        print(f"🔧 Loading cross-encoder: {full_model_name}")
        start_time = time.time()
        
        self.model = CrossEncoder(
            full_model_name,
            max_length=max_length,
            device=device
        )
        
        load_time = time.time() - start_time
        print(f"✅ Cross-encoder loaded in {load_time:.2f}s")
    
    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        score_field: str = "rerank_score",
        text_field: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        Re-rank search results using cross-encoder scoring.
        
        Args:
            query: Original search query
            results: List of search results (dicts with 'text' field)
            top_k: Number of results to return (None = return all)
            score_field: Field name to store re-rank score
            text_field: Field name containing the text to score
        
        Returns:
            Re-ranked and scored results (sorted by rerank_score descending)
        """
        if not results:
            return []
        
        # Prepare query-document pairs
        pairs = []
        for result in results:
            text = result.get(text_field, "")
            if not text:
                print(f"⚠️  Warning: Result missing '{text_field}' field")
                text = str(result)  # Fallback
            pairs.append([query, text])
        
        # Score all pairs
        start_time = time.time()
        scores = self.model.predict(pairs)
        score_time = time.time() - start_time
        
        # Add scores to results
        for result, score in zip(results, scores):
            result[score_field] = float(score)  # Convert numpy float to Python float
        
        # Sort by new score
        reranked = sorted(
            results,
            key=lambda x: x.get(score_field, -float('inf')),
            reverse=True
        )
        
        # Limit to top_k
        if top_k:
            reranked = reranked[:top_k]
        
        print(f"✅ Re-ranked {len(results)} results in {score_time:.3f}s (top_k={top_k})")
        
        return reranked
    
    def rerank_with_comparison(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        original_score_field: str = "score",
        text_field: str = "text"
    ) -> Dict[str, Any]:
        """
        Re-rank and provide comparison metrics between original and re-ranked.
        
        Args:
            query: Original search query
            results: Search results with original scores
            top_k: Number of results to return
            original_score_field: Field name of original scores
            text_field: Field name containing text
        
        Returns:
            Dict with 'reranked_results', 'original_top_k', 'metrics'
        """
        if not results:
            return {
                "reranked_results": [],
                "original_top_k": [],
                "metrics": {}
            }
        
        # Store original rankings
        for idx, result in enumerate(results):
            result['original_rank'] = idx + 1
        
        # Save original top-k
        original_top_k = results[:top_k] if top_k else results.copy()
        
        # Re-rank
        reranked = self.rerank(
            query=query,
            results=results,
            top_k=top_k,
            text_field=text_field
        )
        
        # Calculate metrics
        metrics = self._calculate_rerank_metrics(
            original=original_top_k,
            reranked=reranked,
            original_score_field=original_score_field
        )
        
        return {
            "reranked_results": reranked,
            "original_top_k": original_top_k,
            "metrics": metrics
        }
    
    def _calculate_rerank_metrics(
        self,
        original: List[Dict[str, Any]],
        reranked: List[Dict[str, Any]],
        original_score_field: str
    ) -> Dict[str, Any]:
        """Calculate comparison metrics between original and re-ranked results."""
        if not original or not reranked:
            return {}
        
        # Get IDs for comparison (use segment_id or index)
        original_ids = [r.get('segment_id', i) for i, r in enumerate(original)]
        reranked_ids = [r.get('segment_id', i) for i, r in enumerate(reranked)]
        
        # Calculate overlap
        original_set = set(original_ids)
        reranked_set = set(reranked_ids)
        overlap = len(original_set & reranked_set)
        
        # Calculate rank changes
        rank_changes = []
        for result in reranked:
            seg_id = result.get('segment_id')
            if seg_id:
                original_rank = result.get('original_rank', 0)
                new_rank = reranked_ids.index(seg_id) + 1 if seg_id in reranked_ids else 0
                if original_rank and new_rank:
                    rank_changes.append(abs(new_rank - original_rank))
        
        avg_rank_change = sum(rank_changes) / len(rank_changes) if rank_changes else 0
        
        # Score statistics
        original_scores = [r.get(original_score_field, 0) for r in original]
        rerank_scores = [r.get('rerank_score', 0) for r in reranked]
        
        return {
            "overlap_count": overlap,
            "overlap_percentage": (overlap / len(original)) * 100 if original else 0,
            "average_rank_change": avg_rank_change,
            "max_rank_change": max(rank_changes) if rank_changes else 0,
            "original_score_range": {
                "min": min(original_scores) if original_scores else 0,
                "max": max(original_scores) if original_scores else 0,
                "avg": sum(original_scores) / len(original_scores) if original_scores else 0
            },
            "rerank_score_range": {
                "min": min(rerank_scores) if rerank_scores else 0,
                "max": max(rerank_scores) if rerank_scores else 0,
                "avg": sum(rerank_scores) / len(rerank_scores) if rerank_scores else 0
            }
        }
    
    def batch_rerank(
        self,
        queries_and_results: List[tuple[str, List[Dict[str, Any]]]],
        top_k: Optional[int] = None,
        text_field: str = "text"
    ) -> List[List[Dict[str, Any]]]:
        """
        Re-rank multiple queries in batch (more efficient).
        
        Args:
            queries_and_results: List of (query, results) tuples
            top_k: Number of results per query
            text_field: Field name containing text
        
        Returns:
            List of re-ranked result lists
        """
        all_reranked = []
        
        for query, results in queries_and_results:
            reranked = self.rerank(
                query=query,
                results=results,
                top_k=top_k,
                text_field=text_field
            )
            all_reranked.append(reranked)
        
        return all_reranked
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "model_path": str(self.model.model),
            "max_length": self.model.max_length,
            "device": str(self.model._target_device)
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"CrossEncoderReranker(model={self.model_name})"


# ============================================
# Convenience Functions
# ============================================

def create_reranker(
    model_name: str = "balanced",
    device: Optional[str] = None
) -> CrossEncoderReranker:
    """
    Factory function to create a re-ranker.
    
    Args:
        model_name: Model size ('fast', 'balanced', 'quality')
        device: Device to use ('cuda', 'cpu', or None)
    
    Returns:
        Configured CrossEncoderReranker instance
    """
    return CrossEncoderReranker(model_name=model_name, device=device)


# ============================================
# Module-level test
# ============================================

if __name__ == "__main__":
    print("🧪 Testing CrossEncoderReranker...")
    
    # Create reranker
    reranker = create_reranker("fast")
    
    # Test data
    query = "What did Paul say about grace?"
    
    results = [
        {"segment_id": "1", "text": "Paul discusses law and works in Romans", "score": 0.85},
        {"segment_id": "2", "text": "Paul teaches about grace and faith in Ephesians", "score": 0.82},
        {"segment_id": "3", "text": "Peter writes about suffering in 1 Peter", "score": 0.75},
        {"segment_id": "4", "text": "Paul explains grace in Romans 3-5", "score": 0.80},
    ]
    
    # Re-rank
    reranked = reranker.rerank(query, results, top_k=3)
    
    print("\n📊 Original Results:")
    for r in results:
        print(f"  {r['segment_id']}: {r['text'][:50]}... (score: {r['score']:.3f})")
    
    print("\n📊 Re-ranked Results:")
    for r in reranked:
        print(f"  {r['segment_id']}: {r['text'][:50]}... (rerank: {r['rerank_score']:.3f}, orig: {r['score']:.3f})")
    
    print("\n✅ Test complete!")