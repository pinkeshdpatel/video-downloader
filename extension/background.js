// Service Worker setup
const DEBUG = true;
function debugLog(...args) {
    if (DEBUG) {
        console.log('[Debug]', ...args);
    }
}

// Extract video ID from various YouTube URL formats
function extractYouTubeVideoId(url) {
    debugLog('Extracting video ID from URL:', url);
    
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname;
        const pathname = urlObj.pathname;
        
        // Handle different YouTube URL formats
        if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) {
            // youtube.com/watch?v=VIDEO_ID
            if (urlObj.searchParams.has('v')) {
                return urlObj.searchParams.get('v');
            }
            
            // youtu.be/VIDEO_ID
            if (hostname === 'youtu.be') {
                return pathname.slice(1);
            }
            
            // youtube.com/shorts/VIDEO_ID
            if (pathname.includes('/shorts/')) {
                return pathname.split('/shorts/')[1].split('/')[0];
            }
            
            // youtube.com/embed/VIDEO_ID
            if (pathname.includes('/embed/')) {
                return pathname.split('/embed/')[1].split('/')[0];
            }
            
            // youtube.com/v/VIDEO_ID
            if (pathname.includes('/v/')) {
                return pathname.split('/v/')[1].split('/')[0];
            }
        } else if (hostname.includes('instagram.com')) {
            // Handle Instagram URLs
            const matches = pathname.match(/\/(p|reel|tv)\/([^\/]+)/);
            if (matches && matches[2]) {
                return matches[2];
            }
        }
        
        throw new Error('Unsupported URL format');
    } catch (error) {
        debugLog('Error extracting video ID:', error);
        throw new Error(`Could not extract video ID: ${error.message}`);
    }
}

// Function to retry failed requests
async function fetchWithRetry(url, options, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(url, options);
            if (response.ok) return response;
            if (response.status === 429) { // Too Many Requests
                const waitTime = Math.pow(2, i) * 1000; // Exponential backoff
                await new Promise(resolve => setTimeout(resolve, waitTime));
                continue;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        } catch (error) {
            if (i === maxRetries - 1) throw error;
            await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
        }
    }
    throw new Error('Max retries reached');
}

// Handle video download
async function downloadVideo(url, quality) {
    debugLog('Starting download process for URL:', url, 'Quality:', quality);
    try {
        // Validate URL format
        if (!url.match(/^https?:\/\//i)) {
            throw new Error('Invalid URL format. URL must start with http:// or https://');
        }

        // Extract video ID and validate
        const videoId = extractYouTubeVideoId(url);
        debugLog('Extracted video ID:', videoId);

        if (!videoId) {
            throw new Error('Could not extract video ID from URL. Please check the URL format.');
        }

        // Use RapidAPI YouTube API
        const options = {
            method: 'GET',
            headers: {
                'X-RapidAPI-Key': 'YOUR_RAPIDAPI_KEY',  // You'll need to get a key from RapidAPI
                'X-RapidAPI-Host': 'youtube-video-download-info.p.rapidapi.com'
            }
        };

        debugLog('Fetching video info...');
        const infoResponse = await fetchWithRetry(
            `https://youtube-video-download-info.p.rapidapi.com/dl?id=${videoId}`,
            options
        );

        const videoInfo = await infoResponse.json();
        debugLog('Video info received:', videoInfo);

        if (!videoInfo.link || videoInfo.link.length === 0) {
            throw new Error('No download links available for this video');
        }

        // Select format based on quality
        let selectedFormat = null;
        const formats = videoInfo.link.filter(f => f.type === 'mp4');

        if (quality === 'highest') {
            selectedFormat = formats.sort((a, b) => (b.quality || 0) - (a.quality || 0))[0];
        } else {
            const targetQuality = parseInt(quality);
            selectedFormat = formats
                .filter(f => (f.quality || 0) <= targetQuality)
                .sort((a, b) => (b.quality || 0) - (a.quality || 0))[0];
        }

        if (!selectedFormat) {
            selectedFormat = formats[0]; // Fallback to best available
        }

        debugLog('Selected format:', selectedFormat);

        // Download the video
        debugLog('Starting download from:', selectedFormat.url);
        const downloadResponse = await fetchWithRetry(selectedFormat.url, {
            method: 'GET',
            headers: {
                'Accept': 'video/mp4,video/*'
            }
        });

        const blob = await downloadResponse.blob();
        if (blob.size < 1000) { // Less than 1KB
            throw new Error('Downloaded file is too small, likely an error response');
        }

        const filename = `${videoInfo.title || `video_${videoId}`}.mp4`
            .replace(/[<>:"/\\|?*]/g, '_'); // Remove invalid filename characters
        debugLog('Download successful, blob size:', blob.size);

        // Create download URL and trigger download
        const blobUrl = URL.createObjectURL(blob);
        const result = await chrome.downloads.download({
            url: blobUrl,
            filename: filename,
            saveAs: false
        });

        // Clean up the blob URL
        URL.revokeObjectURL(blobUrl);

        return {
            success: true,
            message: 'Download completed successfully',
            fileSize: blob.size,
            fileName: filename,
            downloadId: result,
            videoId: videoId,
            format: selectedFormat.quality + 'p'
        };

    } catch (error) {
        console.error('Download error:', error);
        debugLog('Full error details:', {
            message: error.message,
            stack: error.stack,
            url: url
        });
        return {
            success: false,
            message: error.message,
            details: error.stack
        };
    }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    debugLog('Received message:', message);
    if (message.action === 'downloadVideo') {
        // Handle the download request
        downloadVideo(message.url, message.quality)
            .then(result => {
                debugLog('Download completed with result:', result);
                sendResponse(result);
            })
            .catch(error => {
                debugLog('Download failed with error:', error);
                sendResponse({
                    success: false,
                    message: error.message,
                    details: error.stack
                });
            });
        return true; // Will respond asynchronously
    }
});

// Service worker activation
self.addEventListener('activate', event => {
    debugLog('Service Worker activated');
});

// Service worker installation
self.addEventListener('install', event => {
    debugLog('Service Worker installed');
    self.skipWaiting();
}); 