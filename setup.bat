@echo off
REM ============================================================================
REM Podcast RAG Template - Windows Setup Script
REM ============================================================================

echo ============================================================================
echo  Podcast RAG Template - Setup Script
echo ============================================================================
echo.

REM ============================================================================
REM Check Prerequisites
REM ============================================================================

echo Checking prerequisites...

where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Conda not found!
    echo Please install Miniconda or Anaconda:
    echo   https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)
echo [OK] Conda found

where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Docker not found
    echo Docker is recommended for running Milvus.
    echo You can install it from: https://docs.docker.com/get-docker/
    echo.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "%CONTINUE%"=="y" exit /b 1
) else (
    echo [OK] Docker found
)

echo.

REM ============================================================================
REM Create Conda Environment
REM ============================================================================

echo Setting up Conda environment...
echo.

set /p ENV_NAME="Environment name [podcast-rag]: "
if "%ENV_NAME%"=="" set ENV_NAME=podcast-rag

REM Check if environment exists
conda env list | findstr /C:"%ENV_NAME%" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Environment '%ENV_NAME%' already exists
    set /p RECREATE="Remove and recreate? (y/n): "
    if /i "%RECREATE%"=="y" (
        echo Removing existing environment...
        call conda env remove -n %ENV_NAME% -y
    ) else (
        echo Updating existing environment...
        call conda env update -n %ENV_NAME% -f environment.yml
        echo [OK] Environment updated
        goto :skip_create
    )
)

echo Creating conda environment from environment.yml...
call conda env create -f environment.yml -n %ENV_NAME%
echo [OK] Conda environment created: %ENV_NAME%

:skip_create
echo.

REM ============================================================================
REM Configure Environment Variables
REM ============================================================================

echo Setting up environment variables...
echo.

if not exist .env (
    copy .env.example .env
    echo [OK] Created .env file from template
    echo.
    echo [IMPORTANT] Edit .env and add your OpenAI API key
    echo.
    set /p OPENAI_KEY="Enter your OpenAI API key (or press Enter to skip): "

    if not "!OPENAI_KEY!"=="" (
        powershell -Command "(gc .env) -replace 'your_openai_api_key_here', '!OPENAI_KEY!' | Out-File -encoding ASCII .env"
        echo [OK] OpenAI API key configured
    ) else (
        echo [WARNING] Remember to edit .env and add your OpenAI API key later
    )
) else (
    echo [WARNING] .env file already exists, skipping...
)

echo.

REM ============================================================================
REM Create Directory Structure
REM ============================================================================

echo Creating directory structure...

if not exist data mkdir data
if not exist transcripts mkdir transcripts
if not exist logs mkdir logs
if not exist .web_conversations mkdir .web_conversations
if not exist src\web\static\images mkdir src\web\static\images

REM Create .gitkeep files
type nul > transcripts\.gitkeep
type nul > data\.gitkeep
type nul > logs\.gitkeep

echo [OK] Directories created
echo.

REM ============================================================================
REM Configure Podcast
REM ============================================================================

echo Configuring your podcast...
echo.
echo Let's customize podcast_config.yaml for your podcast
echo.

set /p ITUNES_ID="Podcast iTunes ID: "
set /p POD_NAME="Podcast Name: "
set /p POD_DESC="Podcast Description: "

if not "%ITUNES_ID%"=="" (
    powershell -Command "(gc podcast_config.yaml) -replace 'itunes_id: \"1681418502\"', 'itunes_id: \"%ITUNES_ID%\"' | Out-File -encoding UTF8 podcast_config.yaml"
)

if not "%POD_NAME%"=="" (
    powershell -Command "(gc podcast_config.yaml) -replace 'name: \"Your Podcast Name\"', 'name: \"%POD_NAME%\"' | Out-File -encoding UTF8 podcast_config.yaml"
    powershell -Command "(gc podcast_config.yaml) -replace 'app_title: \"Podcast Search\"', 'app_title: \"%POD_NAME% Search\"' | Out-File -encoding UTF8 podcast_config.yaml"
)

if not "%POD_DESC%"=="" (
    powershell -Command "(gc podcast_config.yaml) -replace 'description: \"A brief description of your podcast\"', 'description: \"%POD_DESC%\"' | Out-File -encoding UTF8 podcast_config.yaml"
)

echo [OK] Podcast configuration updated
echo.

REM ============================================================================
REM Start Milvus
REM ============================================================================

echo Setting up Milvus vector database...
echo.

where docker >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    docker ps | findstr milvus-standalone >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Milvus is already running
    ) else (
        echo Milvus is not running.
        set /p START_MILVUS="Start Milvus with Docker? (y/n): "
        if /i "%START_MILVUS%"=="y" (
            echo Starting Milvus...
            docker run -d --name milvus-standalone -p 19530:19530 -p 9091:9091 -v milvus_data:/var/lib/milvus milvusdb/milvus:latest
            echo Waiting for Milvus to start...
            timeout /t 5 /nobreak >nul
            echo [OK] Milvus started
        )
    )
) else (
    echo [WARNING] Docker not available. Please install Milvus manually:
    echo   https://milvus.io/docs/install_standalone-docker.md
)

echo.

REM ============================================================================
REM Setup Complete
REM ============================================================================

echo ============================================================================
echo  Setup Complete!
echo ============================================================================
echo.
echo Next steps:
echo.
echo 1. Activate the environment:
echo    conda activate %ENV_NAME%
echo.
echo 2. Start the web application:
echo    python run_web.py
echo.
echo 3. Open in your browser:
echo    http://localhost:8000
echo.
echo 4. Transcribe episodes:
echo    - Via Web UI: http://localhost:8000/transcribe
echo    - Via CLI: python -m src.cli.main transcribe --podcast-id %ITUNES_ID%
echo.
echo 5. Customize further:
echo    - Edit podcast_config.yaml for advanced settings
echo    - Replace src\web\static\images\podcast_logo.png with your logo
echo    - See README.md for complete documentation
echo.
echo ============================================================================
echo.

set /p START_APP="Start the application now? (y/n): "
if /i "%START_APP%"=="y" (
    echo Starting application...
    call conda activate %ENV_NAME%
    python run_web.py
)

pause
