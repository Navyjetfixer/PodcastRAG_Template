"""
Application settings and configuration.
Loads settings from podcast_config.yaml and environment variables.
"""
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List
import os
import yaml
from pathlib import Path


def load_podcast_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from podcast_config.yaml file.

    Args:
        config_path: Path to config file. If None, searches for podcast_config.yaml

    Returns:
        Dictionary of configuration values
    """
    # Find config file
    if config_path is None:
        # Search in project root (two levels up from this file)
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "podcast_config.yaml"
    else:
        config_path = Path(config_path)

    # Load YAML if file exists
    if config_path.exists():
        print(f"📄 Loading config from: {config_path}")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    else:
        print(f"⚠️  Config file not found: {config_path}")
        print("   Using default settings and environment variables")
        return {}


class Settings(BaseSettings):
    """
    Application settings loaded from podcast_config.yaml and environment variables.

    Priority order (highest to lowest):
    1. Environment variables
    2. podcast_config.yaml
    3. Default values
    """

    # ============================================
    # Podcast Information
    # ============================================
    podcast_name: str = "My Podcast"
    podcast_description: str = "Podcast transcript search and Q&A"
    podcast_url: str = ""
    podcast_itunes_id: str = ""
    podcast_logo: str = "podcast_logo.png"

    # ============================================
    # Branding
    # ============================================
    app_title: str = "Podcast Search"
    primary_color: str = "#3B82F6"
    secondary_color: str = "#8B5CF6"
    accent_color: str = "#10B981"

    # ============================================
    # Milvus Settings
    # ============================================
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "podcast_segments"

    # ============================================
    # Embedding Model Settings
    # ============================================
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_device: str = "auto"

    # ============================================
    # LLM Settings
    # ============================================
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 500
    llm_system_prompt: str = """You are a helpful AI assistant that answers questions based on podcast transcripts.
Provide accurate, concise answers using the context provided.
If you don't know the answer, say so."""
    openai_api_key: Optional[str] = None

    # ============================================
    # Re-ranker Settings
    # ============================================
    use_reranker: bool = True
    reranker_model: str = "balanced"  # Options: fast, balanced, quality, large
    reranker_candidates: int = 20

    # ============================================
    # Search Settings
    # ============================================
    default_top_k: int = 5
    default_min_score: float = 0.3
    max_context_length: int = 10000

    # ============================================
    # Transcription Settings
    # ============================================
    whisper_model: str = "tiny.en"
    use_faster_whisper: bool = True
    beam_size: int = 5
    vad_filter: bool = True
    save_timestamps: bool = True

    # ============================================
    # Chunking Strategy
    # ============================================
    chunk_size: int = 3500
    chunk_overlap: int = 200
    chunking_strategy: str = "fixed"

    # ============================================
    # Web Server Settings
    # ============================================
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    web_reload: bool = True
    web_workers: int = 1

    # ============================================
    # Data Paths
    # ============================================
    data_dir: str = "data"
    transcripts_dir: str = "transcripts"
    conversations_dir: str = ".web_conversations"
    logs_dir: str = "logs"

    # ============================================
    # Feature Flags
    # ============================================
    feature_conversations: bool = True
    feature_episode_management: bool = True
    feature_transcription_ui: bool = True
    feature_analytics: bool = False

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"

    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """
        Initialize settings with YAML config and environment variable overrides.

        Args:
            config_path: Optional path to podcast_config.yaml
            **kwargs: Additional overrides
        """
        # Load from YAML first
        yaml_config = load_podcast_config(config_path)

        # Flatten YAML structure to match pydantic fields
        flattened = self._flatten_config(yaml_config)

        # Merge with kwargs (kwargs take precedence)
        merged = {**flattened, **kwargs}

        # Initialize parent
        super().__init__(**merged)

        # Override from environment if set
        if os.getenv("OPENAI_API_KEY"):
            self.openai_api_key = os.getenv("OPENAI_API_KEY")

    def _flatten_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten nested YAML config to match pydantic field names.

        Example:
            {"podcast": {"name": "X"}} -> {"podcast_name": "X"}
        """
        flattened = {}

        # Podcast section
        if "podcast" in config:
            p = config["podcast"]
            flattened["podcast_name"] = p.get("name", self.podcast_name)
            flattened["podcast_description"] = p.get("description", self.podcast_description)
            flattened["podcast_url"] = p.get("url", self.podcast_url)
            flattened["podcast_itunes_id"] = p.get("itunes_id", self.podcast_itunes_id)
            flattened["podcast_logo"] = p.get("logo", self.podcast_logo)

        # Branding section
        if "branding" in config:
            b = config["branding"]
            flattened["app_title"] = b.get("app_title", self.app_title)
            flattened["primary_color"] = b.get("primary_color", self.primary_color)
            flattened["secondary_color"] = b.get("secondary_color", self.secondary_color)
            flattened["accent_color"] = b.get("accent_color", self.accent_color)

        # Milvus section
        if "milvus" in config:
            m = config["milvus"]
            flattened["milvus_host"] = m.get("host", self.milvus_host)
            flattened["milvus_port"] = m.get("port", self.milvus_port)
            flattened["milvus_collection"] = m.get("collection_name", self.milvus_collection)

        # Embeddings section
        if "embeddings" in config:
            e = config["embeddings"]
            flattened["embedding_model"] = e.get("model", self.embedding_model)
            flattened["embedding_dim"] = e.get("dimension", self.embedding_dim)
            flattened["embedding_device"] = e.get("device", self.embedding_device)

        # LLM section
        if "llm" in config:
            l = config["llm"]
            flattened["llm_model"] = l.get("model", self.llm_model)
            flattened["llm_temperature"] = l.get("temperature", self.llm_temperature)
            flattened["llm_max_tokens"] = l.get("max_tokens", self.llm_max_tokens)
            if "system_prompt" in l:
                flattened["llm_system_prompt"] = l["system_prompt"]

        # Search section
        if "search" in config:
            s = config["search"]
            flattened["default_top_k"] = s.get("default_top_k", self.default_top_k)
            flattened["default_min_score"] = s.get("min_score", self.default_min_score)
            flattened["max_context_length"] = s.get("max_context_length", self.max_context_length)
            flattened["use_reranker"] = s.get("use_reranker", self.use_reranker)
            flattened["reranker_model"] = s.get("reranker_model", self.reranker_model)
            flattened["reranker_candidates"] = s.get("reranker_candidates", self.reranker_candidates)

        # Transcription section
        if "transcription" in config:
            t = config["transcription"]
            flattened["whisper_model"] = t.get("whisper_model", self.whisper_model)
            flattened["use_faster_whisper"] = t.get("use_faster_whisper", self.use_faster_whisper)
            flattened["beam_size"] = t.get("beam_size", self.beam_size)
            flattened["vad_filter"] = t.get("vad_filter", self.vad_filter)
            flattened["save_timestamps"] = t.get("save_timestamps", self.save_timestamps)

        # Chunking section
        if "chunking" in config:
            c = config["chunking"]
            flattened["chunk_size"] = c.get("chunk_size", self.chunk_size)
            flattened["chunk_overlap"] = c.get("chunk_overlap", self.chunk_overlap)
            flattened["chunking_strategy"] = c.get("strategy", self.chunking_strategy)

        # Web section
        if "web" in config:
            w = config["web"]
            flattened["web_host"] = w.get("host", self.web_host)
            flattened["web_port"] = w.get("port", self.web_port)
            flattened["web_reload"] = w.get("reload", self.web_reload)
            flattened["web_workers"] = w.get("workers", self.web_workers)

        # Paths section
        if "paths" in config:
            p = config["paths"]
            flattened["data_dir"] = p.get("data_dir", self.data_dir)
            flattened["transcripts_dir"] = p.get("transcripts_dir", self.transcripts_dir)
            flattened["logs_dir"] = p.get("logs_dir", self.logs_dir)

        # Features section
        if "features" in config:
            f = config["features"]
            flattened["feature_conversations"] = f.get("conversations", self.feature_conversations)
            flattened["feature_episode_management"] = f.get("episode_management", self.feature_episode_management)
            flattened["feature_transcription_ui"] = f.get("transcription_ui", self.feature_transcription_ui)
            flattened["feature_analytics"] = f.get("analytics", self.feature_analytics)

        return flattened

    def get_milvus_uri(self) -> str:
        """Get Milvus connection URI."""
        return f"{self.milvus_host}:{self.milvus_port}"

    def validate_settings(self) -> bool:
        """
        Validate that all required settings are present.

        Returns:
            True if all settings are valid
        """
        issues = []

        # Check OpenAI API key
        if not self.openai_api_key:
            issues.append("⚠️  OPENAI_API_KEY not set")

        # Check Milvus connection info
        if not self.milvus_host:
            issues.append("⚠️  MILVUS_HOST not set")

        if issues:
            print("❌ Configuration issues found:")
            for issue in issues:
                print(f"   {issue}")
            return False

        print("✅ Configuration validated successfully")
        return True

    def print_settings(self):
        """Print current settings (masking sensitive values)."""
        print("\n" + "=" * 60)
        print("⚙️  Application Settings")
        print("=" * 60)

        print("\n🎙️  Podcast:")
        print(f"   Name: {self.podcast_name}")
        print(f"   iTunes ID: {self.podcast_itunes_id or 'Not set'}")

        print("\n🎨 Branding:")
        print(f"   Title: {self.app_title}")

        print("\n🔌 Milvus:")
        print(f"   Host: {self.milvus_host}")
        print(f"   Port: {self.milvus_port}")
        print(f"   Collection: {self.milvus_collection}")

        print("\n🧠 Embedding Model:")
        print(f"   Model: {self.embedding_model}")
        print(f"   Dimension: {self.embedding_dim}")
        print(f"   Device: {self.embedding_device}")

        print("\n🤖 LLM:")
        print(f"   Model: {self.llm_model}")
        print(f"   Temperature: {self.llm_temperature}")
        print(f"   Max Tokens: {self.llm_max_tokens}")
        print(f"   API Key: {'✅ Set' if self.openai_api_key else '❌ Not set'}")

        print("\n🎯 Re-ranker:")
        print(f"   Enabled: {self.use_reranker}")
        if self.use_reranker:
            print(f"   Model: {self.reranker_model}")
            print(f"   Candidates: {self.reranker_candidates}")

        print("\n🔍 Search:")
        print(f"   Default Top-K: {self.default_top_k}")
        print(f"   Min Score: {self.default_min_score}")

        print("\n🎤 Transcription:")
        print(f"   Model: {self.whisper_model}")
        print(f"   Backend: {'faster-whisper' if self.use_faster_whisper else 'openai-whisper'}")

        print("\n📐 Chunking:")
        print(f"   Size: {self.chunk_size}")
        print(f"   Overlap: {self.chunk_overlap}")

        print("\n🌐 Web Server:")
        print(f"   Host: {self.web_host}")
        print(f"   Port: {self.web_port}")
        print(f"   Reload: {self.web_reload}")

        print("\n📁 Data Paths:")
        print(f"   Data Dir: {self.data_dir}")
        print(f"   Transcripts: {self.transcripts_dir}")
        print(f"   Conversations: {self.conversations_dir}")

        print("\n🎛️  Features:")
        print(f"   Conversations: {'✅' if self.feature_conversations else '❌'}")
        print(f"   Episode Management: {'✅' if self.feature_episode_management else '❌'}")
        print(f"   Transcription UI: {'✅' if self.feature_transcription_ui else '❌'}")

        print("=" * 60 + "\n")


# ============================================
# Global Settings Instance
# ============================================

settings = Settings()

# ==============================================
# Transcripts Directory Setting
# ==============================================

transcripts_dir = os.getenv('TRANSCRIPTS_DIR') or settings.transcripts_dir
TRANSCRIPTS_DIR = Path(transcripts_dir).resolve()
TRANSCRIPTS_DIR.mkdir(exist_ok=True, parents=True)

# ============================================
# Module-level test
# ============================================

if __name__ == "__main__":
    print("🧪 Testing settings...")

    settings.print_settings()
    settings.validate_settings()

    print("\n✅ Settings test complete!")
