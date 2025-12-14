# 📋 Template Information

This is a **template repository** for creating podcast RAG (Retrieval-Augmented Generation) systems.

## What is this template?

This template provides a complete, production-ready RAG system specifically designed for podcasts. It includes:

- ✅ Automatic transcription with Whisper
- ✅ Vector-based semantic search with Milvus
- ✅ AI-powered Q&A with GPT-4
- ✅ Modern web interface
- ✅ CLI tools for automation
- ✅ Fully configurable via YAML

## Key Differences from Regular Repository

**This is a TEMPLATE, not a working application.** To use it:

1. **Clone/fork this repository** for your specific podcast
2. **Customize** `podcast_config.yaml` with your podcast details
3. **Add your logo** to `src/web/static/images/`
4. **Configure** your OpenAI API key in `.env`
5. **Run** the setup script and start building!

## Quick Start

### Linux/Mac:
```bash
chmod +x setup.sh
./setup.sh
```

### Windows:
```cmd
setup.bat
```

## Template vs Production

| Aspect | Template (This Repo) | Your Production Use |
|--------|---------------------|---------------------|
| Podcast Info | Generic placeholders | Your podcast details |
| Branding | Generic blue theme | Your custom colors/logo |
| Data | Empty databases | Your episodes & transcripts |
| Configuration | Default settings | Tuned for your content |

## What to Customize

### Required Changes:
1. `podcast_config.yaml` - Add your podcast information
2. `.env` - Add your OpenAI API key
3. `src/web/static/images/podcast_logo.png` - Replace with your logo

### Optional Changes:
- `src/web/templates/*.html` - Customize UI layout
- `src/web/static/style.css` - Adjust colors and styling
- `podcast_config.yaml` - Tune search/transcription parameters

## Template Features

### Designed for Easy Customization:
- **YAML Configuration**: All podcast-specific settings in one file
- **Environment Variables**: Secure API key management
- **Modular Structure**: Easy to extend and modify
- **Conda Environment**: Automated dependency management
- **Docker Support**: Optional containerization

### Built-in Tools:
- Web UI for all operations
- CLI for automation and scripting
- Health checks and monitoring
- Episode management
- Conversation history
- Export functionality

## Getting Help

1. **Read the README.md** - Comprehensive setup guide
2. **Check podcast_config.yaml** - Configuration reference with comments
3. **Review .env.example** - Environment variable documentation
4. **Explore examples** - See how components work together

## Repository Structure

```
Template Repository (Clean)          Your Production Repo
├── podcast_config.yaml (template)   ├── podcast_config.yaml (customized)
├── .env.example                     ├── .env (with your API key)
├── src/ (generic code)              ├── src/ (same, maybe customized)
├── transcripts/ (empty)             ├── transcripts/ (your episodes)
├── data/ (empty)                    ├── data/ (your database)
└── README.md (template docs)        └── README.md (your project docs)
```

## Versioning Your Customized Copy

After customizing this template for your podcast:

```bash
# Remove template origin
git remote remove origin

# Add your own repository
git remote add origin https://github.com/yourusername/yourpodcast-search.git

# Push your customized version
git push -u origin main
```

## Multiple Podcasts

To use this template for multiple podcasts:

### Option 1: Separate Repositories (Recommended)
- Clone this template once per podcast
- Each gets its own repository and configuration
- Completely isolated

### Option 2: Separate Branches
- Use different branches in one repository
- Each branch has different `podcast_config.yaml`
- Shared codebase

### Option 3: Separate Collections
- One repository, multiple config files
- Different Milvus collections per podcast
- Run multiple instances

## Updates and Maintenance

This template may receive updates. To update your customized version:

```bash
# Add template as upstream remote
git remote add template https://github.com/original/PodcastRAG_Template.git

# Fetch template updates
git fetch template

# Merge updates (resolve conflicts if needed)
git merge template/main
```

**Note:** Only update if you need new features. Your customizations won't be overwritten unless there are conflicts.

## Template Checklist

Before deploying your customized version:

- [ ] Updated `podcast_config.yaml` with your podcast info
- [ ] Created `.env` with your OpenAI API key
- [ ] Replaced logo image in `src/web/static/images/`
- [ ] Tested transcription with sample episode
- [ ] Tested search and Q&A functionality
- [ ] Customized branding colors (optional)
- [ ] Updated README.md with your project details (optional)
- [ ] Set up production Milvus instance (if deploying to prod)
- [ ] Configured web server for production (if deploying to prod)

## Support

This template is provided as-is for customization. For issues specific to:

- **Template bugs/improvements**: Open issue on template repository
- **Your customization**: Debug in your own repository
- **General usage questions**: See README.md and configuration files

---

**Happy building! 🚀**

Transform this template into your own powerful podcast search system.
