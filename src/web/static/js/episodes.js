// DOM elements
const refreshBtn = document.getElementById('refreshBtn');
const episodesList = document.getElementById('episodesList');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadEpisodes();
    refreshBtn.addEventListener('click', loadEpisodes);
});

// Load and display episodes
async function loadEpisodes() {
    episodesList.innerHTML = '<p class="loading">Loading episodes...</p>';
    
    try {
        const response = await fetch('/api/episodes/list');
        const episodes = await response.json();
        
        if (!response.ok) {
            throw new Error('Failed to load episodes');
        }
        
        if (episodes.length === 0) {
            episodesList.innerHTML = '<p class="loading">No episodes found. Use the Ingest page to add episodes.</p>';
            return;
        }
        
        episodesList.innerHTML = '';
        
        episodes.forEach(episode => {
            const card = document.createElement('div');
            card.className = 'episode-card';
            
            card.innerHTML = `
                <div class="episode-info">
                    <h3>${episode.title}</h3>
                    <p class="episode-meta">ID: ${episode.episode_id}</p>
                </div>
                <div class="episode-actions">
                    <button class="btn btn-primary" onclick="viewEpisode('${episode.episode_id}')">
                        👁️ View
                    </button>
                    <button class="btn btn-danger" onclick="deleteEpisode('${episode.episode_id}', '${episode.title.replace(/'/g, "\\'")}')">
                        🗑️ Delete
                    </button>
                </div>
            `;
            
            episodesList.appendChild(card);
        });
        
    } catch (error) {
        episodesList.innerHTML = `<p class="loading" style="color: var(--danger-color);">Error: ${error.message}</p>`;
        console.error('Load episodes error:', error);
    }
}

// View episode details
async function viewEpisode(episodeId) {
    try {
        const response = await fetch(`/api/episodes/${episodeId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load episode');
        }
        
        alert(
            `Episode: ${data.title}\n\n` +
            `Episode ID: ${data.episode_id}\n` +
            `Segments: ${data.segment_count}\n` +
            `Total Words: ${data.total_words.toLocaleString()}`
        );
        
    } catch (error) {
        alert(`Error: ${error.message}`);
        console.error('View episode error:', error);
    }
}

// Delete episode
async function deleteEpisode(episodeId, title) {
    if (!confirm(`Are you sure you want to delete:\n\n"${title}"\n\nThis action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/episodes/${episodeId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to delete episode');
        }
        
        alert(`Successfully deleted "${title}"`);
        loadEpisodes(); // Refresh list
        
    } catch (error) {
        alert(`Error: ${error.message}`);
        console.error('Delete episode error:', error);
    }
}