import os
from flask import Flask, request, jsonify, send_file
import time
import logging
import yt_dlp
import requests
from functools import partial
import threading
from proxy_manager import ProxyManager
from browser_emulator import BrowserEmulator
from fallback_downloader import FallbackDownloader

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Constants
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Initialize components
proxy_manager = ProxyManager()
browser_emulator = BrowserEmulator()
fallback_downloader = FallbackDownloader(proxy_manager, browser_emulator)

# Global download progress cache
download_progress = {}
download_cache = {}

def get_yt_dlp_opts(quality='best'):
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    return {
        'format': quality,
        'quiet': False,  # Set to False to see detailed output
        'no_warnings': False,  # Set to False to see warnings
        'extract_flat': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'force_generic_extractor': False,
        'cookiefile': cookies_file,
        'cookiesfrombrowser': ('chrome',),
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_color': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
        'extractor_retries': 5,
        'file_access_retries': 5,
        'hls_prefer_native': True,
        'external_downloader_args': ['--max-connection-per-server', '16'],
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'DNT': '1',
            'Referer': 'https://www.youtube.com/'
        }
    }

def get_video_info(url):
    """Get video information without downloading"""
    try:
        ydl_opts = get_yt_dlp_opts()
        proxy = proxy_manager.get_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy.get('http')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formats': info.get('formats', [])
            }
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def download_progress_hook(d, progress_key):
    """Track download progress"""
    if d['status'] == 'downloading':
        try:
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = (downloaded / total) * 100
                download_progress[progress_key] = {
                    'progress': progress,
                    'speed': d.get('speed', 0),
                    'eta': d.get('eta', 0),
                    'status': 'downloading'
                }
        except Exception as e:
            logger.error(f"Error in progress hook: {e}")
    elif d['status'] == 'finished':
        download_progress[progress_key] = {
            'progress': 100,
            'status': 'finished'
        }

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_videos_info():
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        videos_info = []
        errors = []

        for url in urls:
            try:
                ydl_opts = get_yt_dlp_opts()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Extracting info for URL: {url}")
                    info = ydl.extract_info(url, download=False)
                    if info:
                        videos_info.append({
                            'url': url,
                            'title': info.get('title', 'Unknown Title'),
                            'thumbnail': info.get('thumbnail', ''),
                            'duration': info.get('duration', 0),
                            'format': info.get('format', ''),
                            'quality': info.get('quality', 0)
                        })
                        logger.info(f"Successfully extracted info for: {info.get('title', 'Unknown Title')}")
                    else:
                        raise Exception("No video information found")
            except Exception as e:
                error_msg = f"Error with URL {url}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        return jsonify({
            'videos': videos_info,
            'errors': errors
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in video info endpoint: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', 'highest')
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Create a unique filename
        filename = f"video{int(time.time())}.mp4"
        output_path = os.path.join(DOWNLOAD_FOLDER, filename)

        # Set format string based on quality
        if quality == 'highest':
            format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            format_string = f'bestvideo[height<={quality[:-1]}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality[:-1]}][ext=mp4]/best'

        ydl_opts = {
            **get_yt_dlp_opts(format_string),
            'outtmpl': output_path,
            'progress_hooks': [lambda d: download_progress_hook(d, filename)],
        }

        def download_task():
            try:
                logger.info(f"Starting download for URL: {url}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    error_code = ydl.download([url])
                    if error_code != 0:
                        raise Exception(f"yt-dlp returned error code: {error_code}")
                logger.info(f"Download completed for: {filename}")
            except Exception as e:
                error_msg = f"Download error: {str(e)}"
                logger.error(error_msg)
                if os.path.exists(output_path):
                    os.remove(output_path)

        thread = threading.Thread(target=download_task)
        thread.start()
            
        return jsonify({
            'filename': filename,
            'status': 'success',
            'message': 'Download started'
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in download endpoint: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/progress/<filename>')
def get_progress(filename):
    progress_key = next((k for k in download_progress.keys() if filename in k), None)
    if progress_key:
        return jsonify(download_progress[progress_key])
    return jsonify({'status': 'not_found'})

@app.route('/downloads/<filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join(DOWNLOAD_FOLDER, filename),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    # Create download folder if it doesn't exist
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
    
    # In production, the host and port will be set by the environment
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
