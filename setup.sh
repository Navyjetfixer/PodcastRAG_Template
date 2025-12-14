#!/bin/bash
# ============================================================================
# Podcast RAG Template - Setup Script
# ============================================================================
# This script helps you set up the Podcast RAG system for your podcast

set -e  # Exit on error

echo "============================================================================"
echo "🎙️  Podcast RAG Template - Setup Script"
echo "============================================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================================
# Check Prerequisites
# ============================================================================

echo "📋 Checking prerequisites..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda not found!${NC}"
    echo "Please install Miniconda or Anaconda:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi
echo -e "${GREEN}✅ Conda found${NC}"

# Check if Docker is installed (for Milvus)
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker not found${NC}"
    echo "Docker is recommended for running Milvus."
    echo "You can install it from: https://docs.docker.com/get-docker/"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ Docker found${NC}"
fi

echo ""

# ============================================================================
# Create Conda Environment
# ============================================================================

echo "🔧 Setting up Conda environment..."
echo ""

read -p "Environment name [podcast-rag]: " ENV_NAME
ENV_NAME=${ENV_NAME:-podcast-rag}

# Check if environment already exists
if conda env list | grep -q "^$ENV_NAME "; then
    echo -e "${YELLOW}⚠️  Environment '$ENV_NAME' already exists${NC}"
    read -p "Remove and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing environment..."
        conda env remove -n $ENV_NAME
    else
        echo "Updating existing environment..."
        conda env update -n $ENV_NAME -f environment.yml
        echo -e "${GREEN}✅ Environment updated${NC}"
        SKIP_CREATE=true
    fi
fi

if [ -z "$SKIP_CREATE" ]; then
    echo "Creating conda environment from environment.yml..."
    conda env create -f environment.yml -n $ENV_NAME
    echo -e "${GREEN}✅ Conda environment created: $ENV_NAME${NC}"
fi

echo ""

# ============================================================================
# Configure Environment Variables
# ============================================================================

echo "🔐 Setting up environment variables..."
echo ""

if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env file from template${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env and add your OpenAI API key${NC}"
    echo ""
    read -p "Enter your OpenAI API key (or press Enter to skip): " OPENAI_KEY

    if [ -n "$OPENAI_KEY" ]; then
        sed -i "s/your_openai_api_key_here/$OPENAI_KEY/" .env
        echo -e "${GREEN}✅ OpenAI API key configured${NC}"
    else
        echo -e "${YELLOW}⚠️  Remember to edit .env and add your OpenAI API key later${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env file already exists, skipping...${NC}"
fi

echo ""

# ============================================================================
# Create Directory Structure
# ============================================================================

echo "📁 Creating directory structure..."

mkdir -p data
mkdir -p transcripts
mkdir -p logs
mkdir -p .web_conversations
mkdir -p src/web/static/images

# Create .gitkeep files
touch transcripts/.gitkeep
touch data/.gitkeep
touch logs/.gitkeep

echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# ============================================================================
# Configure Podcast
# ============================================================================

echo "🎙️  Configuring your podcast..."
echo ""
echo "Let's customize podcast_config.yaml for your podcast"
echo ""

read -p "Podcast iTunes ID: " ITUNES_ID
read -p "Podcast Name: " POD_NAME
read -p "Podcast Description: " POD_DESC

if [ -n "$ITUNES_ID" ]; then
    sed -i "s/itunes_id: \"1681418502\"/itunes_id: \"$ITUNES_ID\"/" podcast_config.yaml
fi

if [ -n "$POD_NAME" ]; then
    sed -i "s/name: \"Your Podcast Name\"/name: \"$POD_NAME\"/" podcast_config.yaml
    sed -i "s/app_title: \"Podcast Search\"/app_title: \"$POD_NAME Search\"/" podcast_config.yaml
fi

if [ -n "$POD_DESC" ]; then
    sed -i "s/description: \"A brief description of your podcast\"/description: \"$POD_DESC\"/" podcast_config.yaml
fi

echo -e "${GREEN}✅ Podcast configuration updated${NC}"
echo ""

# ============================================================================
# Start Milvus
# ============================================================================

echo "🔌 Setting up Milvus vector database..."
echo ""

if command -v docker &> /dev/null; then
    # Check if Milvus is already running
    if docker ps | grep -q milvus-standalone; then
        echo -e "${GREEN}✅ Milvus is already running${NC}"
    else
        echo "Milvus is not running."
        read -p "Start Milvus with Docker? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Starting Milvus..."
            docker run -d --name milvus-standalone \
                -p 19530:19530 -p 9091:9091 \
                -v milvus_data:/var/lib/milvus \
                milvusdb/milvus:latest

            echo "Waiting for Milvus to start..."
            sleep 5
            echo -e "${GREEN}✅ Milvus started${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Docker not available. Please install Milvus manually:${NC}"
    echo "  https://milvus.io/docs/install_standalone-docker.md"
fi

echo ""

# ============================================================================
# Setup Complete
# ============================================================================

echo "============================================================================"
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo "============================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the environment:"
echo -e "   ${GREEN}conda activate $ENV_NAME${NC}"
echo ""
echo "2. Start the web application:"
echo -e "   ${GREEN}python run_web.py${NC}"
echo ""
echo "3. Open in your browser:"
echo -e "   ${GREEN}http://localhost:8000${NC}"
echo ""
echo "4. Transcribe episodes:"
echo "   - Via Web UI: http://localhost:8000/transcribe"
echo "   - Via CLI: python -m src.cli.main transcribe --podcast-id $ITUNES_ID"
echo ""
echo "5. Customize further:"
echo "   - Edit podcast_config.yaml for advanced settings"
echo "   - Replace src/web/static/images/podcast_logo.png with your logo"
echo "   - See README.md for complete documentation"
echo ""
echo "============================================================================"
echo ""

# Offer to activate environment and start app
read -p "Start the application now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting application..."
    eval "$(conda shell.bash hook)"
    conda activate $ENV_NAME
    python run_web.py
fi
