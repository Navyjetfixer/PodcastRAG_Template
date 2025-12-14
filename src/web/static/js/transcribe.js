// Transcription state
let transcriptionJob = null;
let pollingInterval = null;
let currentEpisodes = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('Transcription page loaded');
});

// Fetch podcast info preview
async function fetchPodcastInfo() {
    const podcastId = document.getElementById('podcastId').value;
    
    if (!podcastId) {
        alert('Please enter a podcast ID');
        return;
    }
    
    try {
        const response = await fetch(`/api/transcribe/info/${podcastId}`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch podcast info');
        }
        
        const data = await response.json();

        // Display podcast info
        document.getElementById('podcastInfoSection').style.display = 'block';
        document.getElementById('podcastName').textContent = data.name;

        // Build detailed stats
        const stats = [
            `👨‍🎤 ${data.artist || 'Unknown Artist'}`,
            `📚 Total Episodes: ${data.total_episodes}`,
            `🆕 New Episodes: ${data.new_episodes}`,
            `✅ Processed: ${data.processed_episodes}`
        ];

        if (data.genres && data.genres.length > 0) {
            stats.push(`🏷️ Genres: ${data.genres.join(', ')}`);
        }

        document.getElementById('podcastStats').innerHTML = stats.join('<br>');

        // Add artwork if available
        if (data.artwork) {
            const artworkHTML = `<img src="${data.artwork}" alt="${data.name}" style="max-width: 200px; border-radius: 8px; margin-top: 10px;">`;
            document.getElementById('podcastStats').innerHTML += '<br>' + artworkHTML;
        }

        console.log('Podcast info:', data);
    } catch (error) {
        console.error('Failed to fetch podcast info:', error);
        alert('Failed to fetch podcast info');
    }
}

// Start transcription
async function startTranscription() {
    const config = {
        podcast_id: document.getElementById('podcastId').value,
        max_episodes: parseInt(document.getElementById('maxEpisodes').value),
        whisper_model: document.getElementById('whisperModel').value,
        beam_size: parseInt(document.getElementById('beamSize').value),
        use_timestamps: document.getElementById('useTimestamps').checked,
        reprocess: document.getElementById('reprocess').checked,
        use_openai_whisper: document.getElementById('useOpenAI').checked,
        vad_filter: !document.getElementById('disableVAD').checked
    };
    
    console.log('Starting transcription with config:', config);
    
    try {
        const response = await fetch('/api/transcribe/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start transcription');
        }
        
        const data = await response.json();
        transcriptionJob = data.job_id;
        
        console.log('Transcription started:', data);
        
        // Update UI
        document.getElementById('startBtn').disabled = true;
        document.getElementById('stopBtn').disabled = false;
        document.getElementById('progressContainer').style.display = 'block';
        document.getElementById('overallStatus').textContent = 'Starting...';
        
        // Start polling for status
        startPolling();
        
    } catch (error) {
        console.error('Failed to start transcription:', error);
        alert(`Failed to start: ${error.message}`);
    }
}

// Stop transcription
async function stopTranscription() {
    if (!transcriptionJob) return;
    
    if (!confirm('Stop the current transcription job?')) return;
    
    try {
        const response = await fetch(`/api/transcribe/stop/${transcriptionJob}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to stop transcription');
        }
        
        stopPolling();
        resetUI();
        
        alert('✅ Transcription stopped');
        
    } catch (error) {
        console.error('Failed to stop transcription:', error);
        alert('Failed to stop transcription');
    }
}

// Start polling for status updates
function startPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    // Poll every 2 seconds
    pollingInterval = setInterval(async () => {
        if (!transcriptionJob) {
            stopPolling();
            return;
        }
        
        try {
            const response = await fetch(`/api/transcribe/status/${transcriptionJob}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch status');
            }
            
            const status = await response.json();
            updateUI(status);
            
            // Stop polling if job is complete
            if (status.is_complete) {
                stopPolling();
                handleComplete(status);
            }
            
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000);
}

// Stop polling
function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// Update UI with status
function updateUI(status) {
    // Update progress bar
    const progress = status.progress || 0;
    document.getElementById('progressBar').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${Math.round(progress)}%`;
    
    // Update status text
    document.getElementById('overallStatus').textContent = status.status || 'Processing...';
    document.getElementById('episodeCounter').textContent = 
        `${status.completed || 0}/${status.total || 0}`;
    document.getElementById('currentEpisode').textContent = 
        status.current_episode || '-';
    
    // Update episodes list
    if (status.episodes && status.episodes.length > 0) {
        renderEpisodes(status.episodes);
    }
}

// Render episodes list
function renderEpisodes(episodes) {
    const list = document.getElementById('episodesList');
    
    list.innerHTML = episodes.map(ep => `
        <div class="episode-card ${ep.status}">
            <div class="episode-header">
                <div>
                    <h3 class="episode-title">${ep.title}</h3>
                    <div class="episode-meta">
                        <span>📅 ${ep.published || 'Unknown'}</span>
                        <span>⏱️ ${formatDuration(ep.duration)}</span>
                        <span>🆔 ${ep.episode_number || 'N/A'}</span>
                    </div>
                </div>
                <span class="status-badge ${ep.status}">${ep.status}</span>
            </div>
            
            ${ep.description ? `
                <div class="episode-description">
                    ${truncateText(ep.description, 200)}
                </div>
            ` : ''}
            
            ${ep.progress_detail ? `
                <div class="episode-progress">
                    ${ep.progress_detail}
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Handle completion
function handleComplete(status) {
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('overallStatus').textContent = 
        status.status === 'failed' ? '❌ Failed' : '✅ Completed';
    
    // Show completion message
    const message = status.status === 'failed' 
        ? `Transcription failed: ${status.error || 'Unknown error'}`
        : `✅ Successfully transcribed ${status.completed} episodes!`;
    
    alert(message);
    
    transcriptionJob = null;
}

// Reset UI
function resetUI() {
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('progressContainer').style.display = 'none';
    document.getElementById('episodesList').innerHTML =
        '<p class="loading">No episodes being processed</p>';
    transcriptionJob = null;
}

// Utility: Format duration
function formatDuration(seconds) {
    if (!seconds) return 'Unknown';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

// Utility: Truncate text
function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}