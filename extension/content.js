// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'getVideoInfo') {
        // Extract video information from the page
        const videoInfo = extractVideoInfo();
        sendResponse(videoInfo);
    }
    return true;
});

// Extract video information from the page
function extractVideoInfo() {
    if (window.location.hostname.includes('youtube.com')) {
        return extractYouTubeInfo();
    } else if (window.location.hostname.includes('instagram.com')) {
        return extractInstagramInfo();
    }
    return null;
}

// Extract YouTube video information
function extractYouTubeInfo() {
    try {
        const videoData = document.querySelector('ytd-watch-flexy');
        if (!videoData) return null;

        return {
            title: document.title.replace(' - YouTube', ''),
            url: window.location.href,
            type: 'youtube',
            isShorts: window.location.pathname.includes('/shorts/'),
            thumbnail: document.querySelector('link[rel="image_src"]')?.href
        };
    } catch (error) {
        console.error('Error extracting YouTube info:', error);
        return null;
    }
}

// Extract Instagram video information
function extractInstagramInfo() {
    try {
        const videoElement = document.querySelector('video');
        if (!videoElement) return null;

        return {
            title: document.title,
            url: window.location.href,
            type: 'instagram',
            thumbnail: document.querySelector('meta[property="og:image"]')?.content
        };
    } catch (error) {
        console.error('Error extracting Instagram info:', error);
        return null;
    }
}

// Add a context menu item when right-clicking on videos
document.addEventListener('contextmenu', function(event) {
    const target = event.target;
    if (target.tagName === 'VIDEO' || 
        (target.closest('ytd-watch-flexy') || target.closest('ytd-shorts'))) {
        chrome.runtime.sendMessage({
            action: 'showContextMenu',
            info: extractVideoInfo()
        });
    }
}); 