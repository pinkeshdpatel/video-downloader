document.addEventListener('DOMContentLoaded', () => {
    const urlsTextarea = document.getElementById('urls');
    const checkUrlsBtn = document.getElementById('checkUrls');
    const quickDownloadBtn = document.getElementById('quickDownload');
    const qualitySelect = document.getElementById('quality');
    const downloadSection = document.getElementById('downloadSection');
    const videoList = document.getElementById('videoList');
    const downloadSelectedBtn = document.getElementById('downloadSelected');
    const selectedCountSpan = document.getElementById('selectedCount');
    const messagesDiv = document.getElementById('messages');

    let activeDownloads = new Set();

    function showMessage(message, type = 'info') {
        const div = document.createElement('div');
        div.className = `p-4 rounded-lg ${type === 'error' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`;
        div.textContent = message;
        messagesDiv.appendChild(div);
        setTimeout(() => div.remove(), 5000);
    }

    async function checkUrls() {
        const urls = urlsTextarea.value.split('\n').filter(url => url.trim());
        if (urls.length === 0) {
            showMessage('Please enter at least one URL', 'error');
            return;
        }

        checkUrlsBtn.disabled = true;
        try {
            const response = await fetch('/api/video-info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls })
            });
            const data = await response.json();
            
            if (data.error) {
                showMessage(data.error, 'error');
                return;
            }

            displayVideos(data.videos);
            if (data.errors.length > 0) {
                data.errors.forEach(error => showMessage(error, 'error'));
            }
        } catch (error) {
            showMessage('Failed to fetch video information', 'error');
        } finally {
            checkUrlsBtn.disabled = false;
        }
    }

    function displayVideos(videos) {
        videoList.innerHTML = '';
        if (videos.length > 0) {
            downloadSection.classList.remove('hidden');
        }

        videos.forEach(video => {
            const template = document.getElementById('videoCardTemplate');
            const clone = template.content.cloneNode(true);
            
            const img = clone.querySelector('img');
            img.src = video.thumbnail || 'placeholder.jpg';
            img.alt = video.title;

            const title = clone.querySelector('h3');
            title.textContent = video.title;

            const duration = clone.querySelector('p');
            duration.textContent = formatDuration(video.duration);

            const quality = clone.querySelector('.quality-badge');
            quality.textContent = video.quality || 'Auto';

            const checkbox = clone.querySelector('input[type="checkbox"]');
            checkbox.dataset.url = video.url;
            checkbox.addEventListener('change', updateSelectedCount);

            const card = clone.querySelector('.video-card');
            card.dataset.url = video.url;

            videoList.appendChild(clone);
        });
    }

    function formatDuration(seconds) {
        if (!seconds) return 'Unknown duration';
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    function updateSelectedCount() {
        const selectedCount = document.querySelectorAll('.video-select:checked').length;
        selectedCountSpan.textContent = `${selectedCount} videos selected`;
        downloadSelectedBtn.disabled = selectedCount === 0;
    }

    async function downloadVideo(url) {
        if (activeDownloads.has(url)) return;
        activeDownloads.add(url);

        const card = document.querySelector(`.video-card[data-url="${url}"]`);
        const progressBar = card.querySelector('.download-progress');
        const progressBarInner = card.querySelector('.download-progress-bar');
        progressBar.classList.remove('hidden');

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    quality: qualitySelect.value
                })
            });
            const data = await response.json();
            
            if (data.error) {
                showMessage(`Failed to download: ${data.error}`, 'error');
                activeDownloads.delete(url);
                return;
            }

            // Poll for progress
            const progressInterval = setInterval(async () => {
                try {
                    const progressResponse = await fetch(`/api/progress/${data.filename}`);
                    const progressData = await progressResponse.json();
                    
                    if (progressData.error) {
                        clearInterval(progressInterval);
                        showMessage(progressData.error, 'error');
                        activeDownloads.delete(url);
                        return;
                    }

                    progressBarInner.style.width = `${progressData.progress}%`;

                    if (progressData.status === 'completed') {
                        clearInterval(progressInterval);
                        showMessage(`Download completed: ${data.filename}`);
                        activeDownloads.delete(url);
                    } else if (progressData.status === 'error') {
                        clearInterval(progressInterval);
                        showMessage(progressData.error || 'Download failed', 'error');
                        activeDownloads.delete(url);
                    }
                } catch (error) {
                    clearInterval(progressInterval);
                    showMessage('Failed to fetch download progress', 'error');
                    activeDownloads.delete(url);
                }
            }, 1000);

        } catch (error) {
            showMessage('Failed to start download', 'error');
            activeDownloads.delete(url);
        }
    }

    // Event Listeners
    checkUrlsBtn.addEventListener('click', checkUrls);
    
    quickDownloadBtn.addEventListener('click', async () => {
        const urls = urlsTextarea.value.split('\n').filter(url => url.trim());
        for (const url of urls) {
            await downloadVideo(url);
        }
    });

    downloadSelectedBtn.addEventListener('click', async () => {
        const selectedUrls = Array.from(document.querySelectorAll('.video-select:checked'))
            .map(checkbox => checkbox.dataset.url);
        for (const url of selectedUrls) {
            await downloadVideo(url);
        }
    });
});
