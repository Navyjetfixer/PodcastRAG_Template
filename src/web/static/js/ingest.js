// DOM elements
const episodeJson = document.getElementById('episodeJson');
const transcriptSrt = document.getElementById('transcriptSrt');
const forceOverwrite = document.getElementById('forceOverwrite');
const chunkSize = document.getElementById('chunkSize');
const uploadStatus = document.getElementById('uploadStatus');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');

const folderPath = document.getElementById('folderPath');
const maxEpisodes = document.getElementById('maxEpisodes');
const skipExisting = document.getElementById('skipExisting');
const folderChunkSize = document.getElementById('folderChunkSize');
const folderStatus = document.getElementById('folderStatus');
const folderProgress = document.getElementById('folderProgress');
const folderProgressFill = document.getElementById('folderProgressFill');
const folderProgressText = document.getElementById('folderProgressText');

const jobsList = document.getElementById('jobsList');

// Auto-refresh interval
let jobsRefreshInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Only load jobs if the element exists
    if (jobsList) {
        loadJobs();
        // Auto-refresh jobs every 5 seconds
        jobsRefreshInterval = setInterval(loadJobs, 5000);
    }
});

// Upload single episode
async function uploadEpisode() {
    const jsonFile = episodeJson.files[0];
    const srtFile = transcriptSrt.files[0];
    
    if (!jsonFile || !srtFile) {
        showUploadStatus('Please select both JSON and SRT files', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('episode_json', jsonFile);
    formData.append('transcript_srt', srtFile);
    formData.append('force', forceOverwrite.checked);
    formData.append('chunk_size', chunkSize.value);
    
    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Uploading files...';
    
    showUploadStatus('Uploading...', 'info');
    
    try {
        const response = await fetch('/api/ingest/episode', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Upload failed');
        }

        // Job started successfully - poll for status
        const jobId = data.job_id;
        progressFill.style.width = '30%';
        progressText.textContent = 'Processing...';
        showUploadStatus(`Job started: ${data.episode_title}`, 'info');

        // Poll for job status
        const pollInterval = setInterval(async () => {
            try {
                const statusResponse = await fetch(`/api/ingest/status/${jobId}`);
                const statusData = await statusResponse.json();

                progressText.textContent = statusData.status;

                if (statusData.is_complete) {
                    clearInterval(pollInterval);
                    progressFill.style.width = '100%';

                    if (statusData.status === 'completed') {
                        showUploadStatus(`✅ Successfully ingested: ${data.episode_title}`, 'success');
                    } else if (statusData.status.startsWith('failed')) {
                        showUploadStatus(`❌ ${statusData.status}`, 'error');
                    }

                    // Clear form
                    episodeJson.value = '';
                    transcriptSrt.value = '';

                    // Reload jobs
                    if (jobsList) {
                        setTimeout(() => loadJobs(), 1000);
                    }

                    // Hide progress bar
                    setTimeout(() => {
                        uploadProgress.style.display = 'none';
                    }, 3000);
                } else {
                    // Update progress
                    if (statusData.status === 'processing') {
                        progressFill.style.width = '60%';
                    }
                }
            } catch (pollError) {
                console.error('Polling error:', pollError);
                clearInterval(pollInterval);
            }
        }, 2000); // Poll every 2 seconds

    } catch (error) {
        showUploadStatus(`❌ Error: ${error.message}`, 'error');
        console.error('Upload error:', error);
        uploadProgress.style.display = 'none';
    }
}

// Ingest folder
async function ingestFolder() {
    const path = folderPath.value.trim();

    if (!path) {
        showFolderStatus('Please enter a folder path', 'error');
        return;
    }

    folderProgress.style.display = 'block';
    folderProgressFill.style.width = '0%';
    folderProgressText.textContent = 'Starting ingestion...';

    showFolderStatus('Starting ingestion...', 'info');

    try {
        const formData = new FormData();
        formData.append('folder_path', path);
        formData.append('skip_existing', skipExisting.checked);
        formData.append('force', !skipExisting.checked);
        formData.append('chunk_size', folderChunkSize.value);

        if (maxEpisodes.value) {
            formData.append('max_episodes', maxEpisodes.value);
        }

        const response = await fetch('/api/ingest/folder', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            console.error('Response status:', response.status);
            console.error('Response data:', data);
            throw new Error(data.detail || JSON.stringify(data) || 'Ingestion failed');
        }

        // Job started successfully - poll for status
        const jobId = data.job_id;
        showFolderStatus(`Job started: ${jobId}`, 'info');

        // Poll for job status
        const pollInterval = setInterval(async () => {
            try {
                const statusResponse = await fetch(`/api/ingest/status/${jobId}`);
                const statusData = await statusResponse.json();

                folderProgressText.textContent = statusData.status;

                if (statusData.is_complete) {
                    clearInterval(pollInterval);
                    folderProgressFill.style.width = '100%';

                    if (statusData.status.startsWith('completed')) {
                        showFolderStatus(`✅ ${statusData.status}`, 'success');
                    } else if (statusData.status.startsWith('failed')) {
                        showFolderStatus(`❌ ${statusData.status}`, 'error');
                    }

                    // Reload jobs
                    if (jobsList) {
                        setTimeout(() => loadJobs(), 1000);
                    }

                    // Hide progress bar after delay
                    setTimeout(() => {
                        folderProgress.style.display = 'none';
                    }, 3000);
                } else {
                    // Update progress based on status text
                    if (statusData.status.includes('processing')) {
                        folderProgressFill.style.width = '50%';
                    } else if (statusData.status.includes('queued')) {
                        folderProgressFill.style.width = '10%';
                    }
                }
            } catch (pollError) {
                console.error('Polling error:', pollError);
                clearInterval(pollInterval);
            }
        }, 2000); // Poll every 2 seconds

    } catch (error) {
        showFolderStatus(`❌ Error: ${error.message}`, 'error');
        console.error('Folder ingestion error:', error);
        folderProgress.style.display = 'none';
    }
}
// Load recent jobs
async function loadJobs() {
    if (!jobsList) return;
    
    jobsList.innerHTML = '<p class="loading">Loading jobs...</p>';
    
    try {
        // This endpoint might not exist yet - handle gracefully
        const response = await fetch('/api/ingest/jobs');
        
        if (!response.ok) {
            jobsList.innerHTML = '<p class="loading">Job history not available</p>';
            return;
        }
        
        const jobs = await response.json();

        if (jobs.length === 0) {
            jobsList.innerHTML = '<p class="loading">No recent jobs</p>';
            return;
        }

        jobsList.innerHTML = jobs.map(job => {
            // Determine status color
            let statusClass = 'info';
            if (job.status.startsWith('completed')) {
                statusClass = 'success';
            } else if (job.status.startsWith('failed')) {
                statusClass = 'error';
            } else if (job.status === 'processing') {
                statusClass = 'warning';
            }

            return `
                <div class="job-card" style="padding: 15px; margin-bottom: 10px; border-radius: 8px; background: #f5f5f5;">
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <div style="font-weight: 600; font-size: 14px;">📁 ${job.job_id}</div>
                        <div>
                            <span class="status ${statusClass}" style="padding: 4px 12px; border-radius: 4px; font-size: 13px;">
                                ${job.status}
                            </span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        jobsList.innerHTML = '<p class="loading">Job history not available</p>';
        console.error('Load jobs error:', error);
    }
}

// Show upload status
function showUploadStatus(message, type) {
    uploadStatus.textContent = message;
    uploadStatus.className = `status ${type}`;
    uploadStatus.style.display = 'block';
    
    if (type === 'success') {
        setTimeout(() => {
            uploadStatus.style.display = 'none';
        }, 5000);
    }
}

// Show folder status
function showFolderStatus(message, type) {
    folderStatus.textContent = message;
    folderStatus.className = `status ${type}`;
    folderStatus.style.display = 'block';
    
    if (type === 'success') {
        setTimeout(() => {
            folderStatus.style.display = 'none';
        }, 5000);
    }
}