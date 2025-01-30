document.addEventListener('DOMContentLoaded', function() {
    const urlsTextarea = document.getElementById('urls');
    const qualitySelect = document.getElementById('quality');
    const downloadBtn = document.getElementById('downloadBtn');
    const progressContainer = document.querySelector('.progress-container');
    const progressBar = document.querySelector('.progress');
    const statusText = document.querySelector('.status');
    const downloadList = document.getElementById('downloadList');
    const debugPanel = document.getElementById('debugPanel');
    const debugLog = document.getElementById('debugLog');
    const toggleDebug = document.getElementById('toggleDebug');

    let isDownloading = false;
    let debugMessages = [];

    // Debug logging
    function addDebugMessage(message) {
        const timestamp = new Date().toISOString();
        debugMessages.push(`[${timestamp}] ${message}`);
        debugLog.textContent = debugMessages.join('\n');
        debugLog.scrollTop = debugLog.scrollHeight;
    }

    // Toggle debug panel
    toggleDebug.addEventListener('click', () => {
        if (debugPanel.style.display === 'none') {
            debugPanel.style.display = 'block';
            toggleDebug.textContent = 'Hide Debug Information';
        } else {
            debugPanel.style.display = 'none';
            toggleDebug.textContent = 'Show Debug Information';
        }
    });

    downloadBtn.addEventListener('click', async function() {
        if (isDownloading) return;

        const urls = urlsTextarea.value.split('\n').filter(url => url.trim());
        if (urls.length === 0) {
            showStatus('Please enter at least one URL', 'error');
            return;
        }

        addDebugMessage(`Starting download process for ${urls.length} URLs`);
        isDownloading = true;
        downloadBtn.disabled = true;
        progressContainer.style.display = 'block';
        downloadList.innerHTML = '';
        debugMessages = [];

        try {
            for (let i = 0; i < urls.length; i++) {
                const url = urls[i].trim();
                if (!url) continue;

                updateProgress((i / urls.length) * 100);
                showStatus(`Processing video ${i + 1} of ${urls.length}`);
                addDebugMessage(`Processing URL: ${url}`);

                try {
                    const result = await chrome.runtime.sendMessage({
                        action: 'downloadVideo',
                        url: url,
                        quality: qualitySelect.value
                    });

                    addDebugMessage(`Download result for ${url}: ${JSON.stringify(result, null, 2)}`);
                    addDownloadItem(url, result);
                } catch (error) {
                    addDebugMessage(`Error downloading ${url}: ${error.message}`);
                    addDownloadItem(url, {
                        success: false,
                        message: error.message,
                        details: error.stack
                    });
                }
            }

            updateProgress(100);
            showStatus('All downloads completed!');
            addDebugMessage('All downloads completed');
        } catch (error) {
            showStatus('Error: ' + error.message, 'error');
            addDebugMessage(`Fatal error: ${error.message}\n${error.stack}`);
        } finally {
            isDownloading = false;
            downloadBtn.disabled = false;
        }
    });

    function updateProgress(percent) {
        progressBar.style.width = `${percent}%`;
    }

    function showStatus(message, type = 'info') {
        statusText.textContent = message;
        statusText.className = 'status ' + type;
        addDebugMessage(`Status: ${message} (${type})`);
    }

    function formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
    }

    function addDownloadItem(url, result) {
        const item = document.createElement('div');
        item.className = `download-item ${result.success ? 'success' : 'error'}`;
        
        let detailsHtml = '';
        if (result.success) {
            detailsHtml = `
                <div class="details">
                    File: ${result.fileName || 'Unknown'}<br>
                    Size: ${formatFileSize(result.fileSize)}<br>
                    Status: Download completed
                </div>
            `;
        } else {
            detailsHtml = `
                <div class="details">Status: Failed</div>
                <div class="error-details">
                    Error: ${result.message}
                    ${result.details ? `\nDetails: ${result.details}` : ''}
                </div>
            `;
        }

        item.innerHTML = `
            <div class="url">${url}</div>
            ${detailsHtml}
        `;
        downloadList.appendChild(item);
        downloadList.scrollTop = downloadList.scrollHeight;
    }

    // Listen for progress updates from background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'downloadProgress') {
            const { url, progress, status, speed, eta, totalSize, downloadedSize } = message;
            addDebugMessage(`Progress for ${url}: ${progress}% - ${status}`);
            
            // Update progress for specific URL
            const items = downloadList.getElementsByClassName('download-item');
            for (let item of items) {
                if (item.querySelector('.url').textContent === url) {
                    const details = item.querySelector('.details') || document.createElement('div');
                    details.className = 'details';
                    details.innerHTML = `
                        Status: ${status}<br>
                        Progress: ${Math.round(progress)}%<br>
                        Speed: ${formatFileSize(speed)}/s<br>
                        ETA: ${eta} seconds<br>
                        Size: ${formatFileSize(downloadedSize)} / ${formatFileSize(totalSize)}
                    `;
                    if (!item.querySelector('.details')) {
                        item.appendChild(details);
                    }
                    break;
                }
            }
        }
    });
}); 