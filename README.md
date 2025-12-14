# Podcast RAG Template

A production-ready **RAG (Retrieval-Augmented Generation)** system for podcast transcripts with semantic search, AI-powered Q&A, and automatic transcription. Built with FastAPI, Milvus, and OpenAI.

**This is a template repository** - customize it for your specific podcast by editing the configuration file!

## Features

- 🎙️ **Automatic Transcription**: Upload podcast audio and get AI transcriptions with Whisper
- 🔍 **Semantic Search**: Vector-based similarity search with cross-encoder re-ranking
- 🤖 **AI Q&A**: Streaming question-answering powered by GPT-4
- 💬 **Conversation Management**: Track, branch, and export conversation histories
- 🎯 **Advanced Filtering**: Filter by episodes, date ranges, and custom metadata
- 🌐 **Modern Web UI**: Clean, responsive interface built with FastAPI
- ⚡ **GPU Acceleration**: CUDA support for faster transcription and embeddings
- 🔧 **Fully Configurable**: YAML-based configuration for easy customization

## Tech Stack

- **Backend**: FastAPI, Python 3.13
- **Vector Database**: Milvus
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: OpenAI GPT-4o-mini (configurable)
- **Transcription**: faster-whisper (4-10x faster than OpenAI Whisper)
- **Environment**: Conda (handles all dependencies including CUDA)

## Quick Start

### Prerequisites

- **Conda** (Miniconda or Anaconda)
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
- **Milvus** running locally or remotely

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd PodcastRAG_Template
```

### 2. Create Conda Environment

```bash
# Create environment from environment.yml
conda env create -f environment.yml

# Activate environment
conda activate podcast-rag
```

The Conda environment automatically handles:
- ✅ Python 3.13
- ✅ PyTorch with CUDA 12.1 support
- ✅ All dependencies (FastAPI, Milvus, sentence-transformers, etc.)
- ✅ CUDA toolkit (no separate installation needed!)

### 3. Configure Your Podcast

Edit `podcast_config.yaml` with your podcast information:

```yaml
podcast:
  itunes_id: "1234567890"  # Your podcast's iTunes ID
  name: "Your Podcast Name"
  description: "Your podcast description"
  logo: "your_logo.png"    # Place in src/web/static/images/

branding:
  app_title: "Your Podcast Search"
  primary_color: "#3B82F6"

# ... see podcast_config.yaml for all options
```

### 4. Set Environment Variables

```bash
# Copy example .env file
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env
```

Add to `.env`:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 5. Start Milvus

**Option A: Docker (Recommended)**
```bash
docker run -d --name milvus-standalone \
  -p 19530:19530 -p 9091:9091 \
  -v milvus_data:/var/lib/milvus \
  milvusdb/milvus:latest
```

**Option B: Standalone Installation**
See [Milvus documentation](https://milvus.io/docs/install_standalone-docker.md)

### 6. Run the Application

```bash
python run_web.py
```

Navigate to:
- **Main Search**: http://localhost:8000
- **Transcribe Episodes**: http://localhost:8000/transcribe
- **Manage Episodes**: http://localhost:8000/episodes
- **API Docs**: http://localhost:8000/docs

## Configuration Guide

The template uses a **three-tier configuration system**:

1. **Default values** (in `src/config/settings.py`)
2. **podcast_config.yaml** (your customizations)
3. **Environment variables** (highest priority)

### Key Configuration Sections

#### Podcast Information
```yaml
podcast:
  itunes_id: "1234567890"
  name: "My Podcast"
  description: "Description here"
```

#### Search & Retrieval
```yaml
search:
  default_top_k: 5          # Number of results
  min_score: 0.3            # Similarity threshold
  use_reranker: true        # Enable re-ranking
  reranker_model: balanced  # fast|balanced|quality|large
```

#### Transcription
```yaml
transcription:
  whisper_model: tiny.en    # tiny.en|base.en|small.en|medium.en|large-v3
  use_faster_whisper: true  # 4-10x faster than OpenAI Whisper
  beam_size: 5              # Quality vs speed (1=fastest, 5=best)
  vad_filter: true          # Skip silence automatically
```

#### LLM Settings
```yaml
llm:
  model: gpt-4o-mini        # OpenAI model
  temperature: 0.7          # 0.0=deterministic, 1.0=creative
  max_tokens: 500
  system_prompt: |
    Your custom system prompt here...
```

See [podcast_config.yaml](podcast_config.yaml) for complete configuration options.

## Usage

### Transcribing Episodes

**Via Web UI:**
1. Go to http://localhost:8000/transcribe
2. Enter podcast iTunes ID or RSS URL
3. Select episodes to transcribe
4. Monitor progress in real-time

**Via Command Line:**
```bash
# Transcribe 5 latest episodes
python -m src.cli.main transcribe --podcast-id 1234567890 --max-episodes 5

# Use higher quality model
python -m src.cli.main transcribe --podcast-id 1234567890 --model small.en
```

### Ingesting Transcripts

**Via Web UI:**
1. Go to http://localhost:8000/ingest
2. Upload transcript files or select from transcripts directory
3. Configure chunking parameters
4. Start ingestion

**Via Command Line:**
```bash
# Ingest single episode
python -m src.cli.ingest episode transcripts/episode1.json transcripts/episode1.srt

# Ingest entire folder
python -m src.cli.ingest folder transcripts/ --chunk-size 3500
```

### Searching & Asking Questions

**Web UI:**
1. Go to http://localhost:8000
2. Enter your search query or question
3. Filter by episodes if needed
4. Get AI-powered answers with source citations

**API:**
```bash
# Search
curl -X POST http://localhost:8000/api/query/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "top_k": 5}'

# Ask question
curl http://localhost:8000/api/query/answer?query=your%20question
```

## Project Structure

```
PodcastRAG_Template/
├── podcast_config.yaml      # Main configuration file
├── environment.yml          # Conda environment definition
├── .env.example             # Environment variables template
├── run_web.py              # Start web application
├── src/
│   ├── api/                # API endpoints
│   ├── cli/                # Command-line tools
│   ├── config/             # Configuration & settings
│   ├── embeddings/         # Embedding generation
│   ├── llm/                # LLM integration
│   ├── models/             # Data models
│   ├── reranker/           # Cross-encoder re-ranking
│   ├── vectorstore/        # Milvus vector store
│   └── web/                # Web application
│       ├── routes/         # API routes
│       ├── static/         # CSS, JS, images
│       └── templates/      # HTML templates
├── transcripts/            # Transcript storage
└── data/                   # Application data
```

## Customization Guide

### Change Branding

1. **Update podcast_config.yaml:**
   ```yaml
   branding:
     app_title: "Your Podcast Search"
     primary_color: "#FF6B6B"
     secondary_color: "#4ECDC4"
   ```

2. **Replace logo image:**
   - Place your logo in `src/web/static/images/`
   - Update `podcast.logo` in config

3. **Customize templates (optional):**
   - Edit HTML in `src/web/templates/`
   - Modify CSS in `src/web/static/style.css`

### Add Custom Metadata

```yaml
features:
  custom_metadata:
    enabled: true
    fields:
      - name: "speaker"
        type: "string"
        searchable: true
      - name: "season"
        type: "integer"
        searchable: true
```

### Change Embedding Model

```yaml
embeddings:
  model: "all-mpnet-base-v2"  # Higher quality, slower
  dimension: 768               # Must match model output
```

**Note:** Changing the embedding model requires:
1. Updating `milvus.vector_dim` to match
2. Re-ingesting all existing episodes
3. Running `python reset_db.py` first

### Use Different LLM

```yaml
llm:
  model: "gpt-4"              # or gpt-4-turbo, gpt-3.5-turbo
  temperature: 0.5
  max_tokens: 1000
```

## Managing Multiple Podcasts

The template supports three different approaches for managing multiple podcasts. Choose based on your needs:

### Option 1: Separate Milvus Instances (Complete Isolation)

**Best for:** Production environments, SaaS platforms, strict isolation requirements

Each podcast gets its own dedicated Milvus database instance.

#### Step-by-Step Setup:

**1. Create separate template copies:**
```bash
# Clone template for each podcast
cp -r PodcastRAG_Template/ MyPodcast_A
cp -r PodcastRAG_Template/ MyPodcast_B
```

**2. Start separate Milvus instances:**
```bash
# Podcast A - Port 19530
docker run -d --name milvus-podcast-a \
  -p 19530:19530 \
  -v milvus_data_a:/var/lib/milvus \
  milvusdb/milvus:latest

# Podcast B - Port 19531 (different port!)
docker run -d --name milvus-podcast-b \
  -p 19531:19530 \
  -v milvus_data_b:/var/lib/milvus \
  milvusdb/milvus:latest
```

**3. Configure each podcast:**

**MyPodcast_A/podcast_config.yaml:**
```yaml
podcast:
  itunes_id: "1111111111"
  name: "Podcast A"

milvus:
  host: "localhost"
  port: 19530  # First Milvus instance
  collection_name: "podcast_segments"
```

**MyPodcast_B/podcast_config.yaml:**
```yaml
podcast:
  itunes_id: "2222222222"
  name: "Podcast B"

milvus:
  host: "localhost"
  port: 19531  # Second Milvus instance (different port!)
  collection_name: "podcast_segments"
```

**4. Run each podcast on different web ports:**
```bash
# Podcast A
cd MyPodcast_A
python run_web.py  # Runs on port 8000

# Podcast B (in another terminal)
cd MyPodcast_B
# Edit podcast_config.yaml: web.port = 8001
python run_web.py  # Runs on port 8001
```

**Pros:**
- ✅ Complete data isolation
- ✅ Independent scaling and backup
- ✅ One failure doesn't affect others
- ✅ Different Milvus versions possible

**Cons:**
- ❌ Higher resource usage (2-4GB RAM per Milvus)
- ❌ More complex infrastructure management
- ❌ Multiple databases to maintain

---

### Option 2: Shared Milvus, Different Collections (Recommended)

**Best for:** Small to medium deployments (2-10 podcasts), local development, cost efficiency

One Milvus instance serves all podcasts using different collection names.

#### Step-by-Step Setup:

**1. Start one Milvus instance:**
```bash
# Single Milvus instance for all podcasts
docker run -d --name milvus-shared \
  -p 19530:19530 \
  -v milvus_shared:/var/lib/milvus \
  milvusdb/milvus:latest
```

**2. Create separate template copies:**
```bash
cp -r PodcastRAG_Template/ MyPodcast_A
cp -r PodcastRAG_Template/ MyPodcast_B
cp -r PodcastRAG_Template/ MyPodcast_C
```

**3. Configure unique collection names:**

**MyPodcast_A/podcast_config.yaml:**
```yaml
podcast:
  itunes_id: "1111111111"
  name: "Tech Talk Podcast"

milvus:
  host: "localhost"
  port: 19530
  collection_name: "tech_talk_segments"  # ← Unique name!

web:
  port: 8000  # Different web port for each
```

**MyPodcast_B/podcast_config.yaml:**
```yaml
podcast:
  itunes_id: "2222222222"
  name: "Business Hour"

milvus:
  host: "localhost"
  port: 19530  # Same Milvus instance
  collection_name: "business_hour_segments"  # ← Different name!

web:
  port: 8001  # Different web port
```

**MyPodcast_C/podcast_config.yaml:**
```yaml
podcast:
  itunes_id: "3333333333"
  name: "Health Hub"

milvus:
  host: "localhost"
  port: 19530  # Same Milvus instance
  collection_name: "health_hub_segments"  # ← Different name!

web:
  port: 8002  # Different web port
```

**4. Run all podcasts:**
```bash
# Terminal 1 - Podcast A
cd MyPodcast_A
conda activate podcast-rag
python run_web.py  # → http://localhost:8000

# Terminal 2 - Podcast B
cd MyPodcast_B
conda activate podcast-rag
python run_web.py  # → http://localhost:8001

# Terminal 3 - Podcast C
cd MyPodcast_C
conda activate podcast-rag
python run_web.py  # → http://localhost:8002
```

**5. Verify data isolation:**
```bash
# Check collections in Milvus
python -c "
from pymilvus import connections, utility
connections.connect(host='localhost', port='19530')
print('Collections:', utility.list_collections())
# Output: ['tech_talk_segments', 'business_hour_segments', 'health_hub_segments']
"
```

**Pros:**
- ✅ Resource efficient (one Milvus ~2GB RAM)
- ✅ Data still completely isolated by collection
- ✅ Easy to manage and backup
- ✅ Simple infrastructure

**Cons:**
- ❌ Single point of failure (Milvus down = all podcasts down)
- ❌ Shared resource limits
- ❌ Must manage multiple web server processes

---

### Option 3: Production Multi-Tenant with Process Manager

**Best for:** Production environments with multiple podcasts on one server

Use a process manager to run multiple instances efficiently.

#### Step-by-Step Setup:

**1. Install PM2 (process manager):**
```bash
npm install -g pm2
```

**2. Create ecosystem config:**

**ecosystem.config.js:**
```javascript
module.exports = {
  apps: [
    {
      name: 'podcast-a',
      script: 'run_web.py',
      cwd: '/home/user/MyPodcast_A',
      interpreter: '/home/user/miniconda3/envs/podcast-rag/bin/python',
      env: {
        PORT: 8000
      }
    },
    {
      name: 'podcast-b',
      script: 'run_web.py',
      cwd: '/home/user/MyPodcast_B',
      interpreter: '/home/user/miniconda3/envs/podcast-rag/bin/python',
      env: {
        PORT: 8001
      }
    },
    {
      name: 'podcast-c',
      script: 'run_web.py',
      cwd: '/home/user/MyPodcast_C',
      interpreter: '/home/user/miniconda3/envs/podcast-rag/bin/python',
      env: {
        PORT: 8002
      }
    }
  ]
};
```

**3. Start all podcasts:**
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # Auto-start on boot
```

**4. Set up nginx reverse proxy:**

**/etc/nginx/sites-available/podcasts:**
```nginx
# Podcast A
server {
    listen 80;
    server_name podcast-a.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Podcast B
server {
    listen 80;
    server_name podcast-b.example.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Podcast C
server {
    listen 80;
    server_name podcast-c.example.com;

    location / {
        proxy_pass http://localhost:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**5. Enable and restart nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/podcasts /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**6. Monitor all podcasts:**
```bash
pm2 status
pm2 logs
pm2 monit
```

---

### Quick Comparison Table

| Feature | Separate Instances | Shared Collections | Multi-Tenant PM2 |
|---------|-------------------|-------------------|------------------|
| **Setup Complexity** | High | Low | Medium |
| **Resource Usage** | High (2-4GB per) | Low (2GB total) | Low (2GB total) |
| **Data Isolation** | Complete | Complete | Complete |
| **Failure Isolation** | Complete | Shared | Shared |
| **Scalability** | Excellent | Good | Good |
| **Cost** | High | Low | Medium |
| **Management** | Complex | Simple | Medium |
| **Best For** | Production/SaaS | Development/Small | Production/Medium |

---

### Recommendation by Use Case

**Local Development (1-3 podcasts):**
→ **Option 2** (Shared Milvus, different collections)
- Easiest to set up and manage
- Minimal resource usage
- Perfect for testing

**Small Production (2-5 podcasts):**
→ **Option 2 + PM2** (Shared Milvus + process manager)
- Resource efficient
- Professional deployment
- Easy monitoring

**Large Production (5+ podcasts or SaaS):**
→ **Option 1** (Separate Milvus instances)
- Better isolation and reliability
- Independent scaling
- Worth the resource overhead

**Enterprise/Multi-Region:**
→ **Option 1 + Kubernetes**
- Container orchestration
- Auto-scaling
- Geographic distribution

---

### Common Gotchas

**1. Collection Name Conflicts:**
```bash
# ❌ Bad - Both use same collection name
MyPodcast_A: collection_name: "podcast_segments"
MyPodcast_B: collection_name: "podcast_segments"  # CONFLICT!

# ✅ Good - Unique names
MyPodcast_A: collection_name: "podcast_a_segments"
MyPodcast_B: collection_name: "podcast_b_segments"
```

**2. Port Conflicts:**
```bash
# ❌ Bad - Both try to use port 8000
MyPodcast_A: web.port = 8000
MyPodcast_B: web.port = 8000  # ERROR: Port already in use!

# ✅ Good - Different ports
MyPodcast_A: web.port = 8000
MyPodcast_B: web.port = 8001
```

**3. Shared Conversations Directory:**
```bash
# ❌ Bad - Conversations get mixed
MyPodcast_A: conversations_dir = ".web_conversations"
MyPodcast_B: conversations_dir = ".web_conversations"  # Same directory!

# ✅ Good - Separate directories
MyPodcast_A: conversations_dir = ".conversations_podcast_a"
MyPodcast_B: conversations_dir = ".conversations_podcast_b"
```

---

## Advanced Usage

### Running in Production

1. **Update configuration:**
   ```yaml
   web:
     host: "0.0.0.0"
     port: 8000
     reload: false            # Disable auto-reload
     workers: 4               # Use multiple workers
   ```

2. **Use production ASGI server:**
   ```bash
   uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. **Set up reverse proxy** (nginx/Caddy) for SSL/TLS

### Docker Deployment

```dockerfile
FROM continuumio/miniconda3

WORKDIR /app
COPY environment.yml .
RUN conda env create -f environment.yml

COPY . .
CMD ["conda", "run", "-n", "podcast-rag", "python", "run_web.py"]
```

### Multiple Podcasts

**Option 1: Separate Collections**
- Create different `podcast_config.yaml` files
- Use different `milvus.collection_name` for each podcast
- Run separate instances

**Option 2: Shared Collection**
- Add `podcast_id` to episode metadata
- Filter by podcast in search queries

## Troubleshooting

### Milvus Connection Issues

```bash
# Check if Milvus is running
docker ps | grep milvus

# Check connection
python check_milvus.py
```

### CUDA Not Detected

```bash
# Verify PyTorch can see CUDA
python -c "import torch; print(torch.cuda.is_available())"

# If False, reinstall with CUDA support
conda install pytorch pytorch-cuda=12.1 -c pytorch -c nvidia
```

### Import Errors

```bash
# Ensure environment is activated
conda activate podcast-rag

# Reinstall dependencies
conda env update -f environment.yml
```

### Transcription Too Slow

```yaml
transcription:
  whisper_model: tiny.en      # Use smallest model
  beam_size: 1                # Fastest decoding
  vad_filter: true            # Skip silence
```

Or use GPU:
```bash
# Check GPU usage during transcription
nvidia-smi -l 1
```

## Development

### Running Tests

```bash
conda activate podcast-rag
pytest src/tests/
```

### Code Formatting

```bash
black src/
flake8 src/
```

### Adding New Features

1. **New API endpoint**: Add route in `src/web/routes/`
2. **New CLI command**: Add to `src/cli/main.py`
3. **New configuration**: Update `podcast_config.yaml` schema

## API Documentation

Full API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

- `POST /api/query/search` - Semantic search
- `GET /api/query/answer` - AI Q&A (streaming)
- `POST /api/ingest/episode` - Ingest transcript
- `GET /api/episodes/list` - List all episodes
- `POST /api/transcribe/start` - Start transcription job

## Performance Optimization

### Speed vs Quality Trade-offs

**Fastest (lower quality):**
```yaml
embeddings:
  model: all-MiniLM-L6-v2
transcription:
  whisper_model: tiny.en
  beam_size: 1
search:
  use_reranker: false
```

**Best Quality (slower):**
```yaml
embeddings:
  model: all-mpnet-base-v2
transcription:
  whisper_model: large-v3
  beam_size: 5
search:
  use_reranker: true
  reranker_model: large
```

## Contributing

This is a template repository. For your customized version:

1. Fork/clone this template
2. Customize for your podcast
3. Push to your own repository

## License

MIT License - feel free to use this template for any podcast project!

## Credits

- **FastAPI**: Web framework
- **Milvus**: Vector database
- **OpenAI**: LLM and Whisper models
- **sentence-transformers**: Embedding models
- **faster-whisper**: Optimized Whisper implementation

## Support

- **Issues**: [GitHub Issues](<your-repo-url>/issues)
- **Documentation**: This README + inline code comments
- **Configuration Help**: See [podcast_config.yaml](podcast_config.yaml)

## Changelog

### v1.0.0 (Initial Template)
- Complete RAG system for podcasts
- Conda environment with CUDA support
- YAML-based configuration
- Web UI for all operations
- CLI tools for automation
- Comprehensive documentation
