"""
Embedder for generating text embeddings using sentence-transformers.
"""
from sentence_transformers import SentenceTransformer
from typing import List, Union
import numpy as np

class Embedder:
    """Handles text embedding generation."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedder with a specific model.
        
        Args:
            model_name: Name of the sentence-transformers model to use
        """
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.embedding_dim
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)
        
        # Convert to list and ensure it's float type
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            show_progress: Whether to show progress bar
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Handle empty texts
        processed_texts = [text if text and text.strip() else " " for text in texts]
        
        # Generate embeddings in batch
        embeddings = self.model.encode(
            processed_texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        # Convert to list of lists
        return [emb.tolist() for emb in embeddings]
    
    def get_dimension(self) -> int:
        """
        Get the dimensionality of the embeddings.
        
        Returns:
            Embedding dimension
        """
        return self.embedding_dim
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score between -1 and 1
        """
        emb1 = np.array(self.embed(text1))
        emb2 = np.array(self.embed(text2))
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        return float(similarity)
    
    def compute_similarity_batch(self, query: str, texts: List[str]) -> List[float]:
        """
        Compute similarity between a query and multiple texts.
        
        Args:
            query: Query text
            texts: List of texts to compare against
        
        Returns:
            List of similarity scores
        """
        query_emb = np.array(self.embed(query))
        text_embs = np.array(self.embed_batch(texts, show_progress=False))
        
        # Compute cosine similarities
        similarities = np.dot(text_embs, query_emb) / (
            np.linalg.norm(text_embs, axis=1) * np.linalg.norm(query_emb)
        )
        
        return similarities.tolist()