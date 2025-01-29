from flask import Flask, request, jsonify, send_file, render_template, url_for, send_from_directory
from flask_cors import CORS
import os
import time
import logging
import yt_dlp
import requests
from functools import partial
import threading
import random
import tempfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Allow all origins for /api routes
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Constants
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'downloads'))
TEMP_FOLDER = os.getenv('TEMP_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp'))
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Clean up old downloads and temp files periodically
def cleanup_files():
    try:
        # Delete files older than 1 hour
        max_age = 3600  # 1 hour in seconds
        current_time = time.time()
        
        # Clean downloads
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age:
                    try:
                        os.remove(file_path)
                        logger.info(f"Cleaned up old file: {filename}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {filename}: {e}")
        
        # Clean temp files
        for filename in os.listdir(TEMP_FOLDER):
            if filename.startswith('user_cookies_'):
                file_path = os.path.join(TEMP_FOLDER, filename)
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age:
                    try:
                        os.remove(file_path)
                        logger.info(f"Cleaned up temp file: {filename}")
                    except Exception as e:
                        logger.error(f"Error cleaning up temp file {filename}: {e}")
                        
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

# Run cleanup every hour
def schedule_cleanup():
    while True:
        cleanup_files()
        time.sleep(3600)  # Sleep for 1 hour

# Start cleanup thread
cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
cleanup_thread.start()

def save_user_cookies(cookies_str: str) -> str:
    """Save user cookies to a temporary file and return the file path"""
    try:
        # Create a temporary file with random name
        cookie_file = os.path.join(TEMP_FOLDER, f'user_cookies_{random.randint(1000, 9999)}.txt')
        
        # Clean up the cookie string
        cookies_str = cookies_str.strip()
        if not cookies_str.startswith('# Netscape HTTP Cookie File'):
            cookies_str = '# Netscape HTTP Cookie File\n' + cookies_str
        
        with open(cookie_file, 'w') as f:
            f.write(cookies_str)
            
        logger.info(f"Saved cookies to file: {cookie_file}")
        return cookie_file
    except Exception as e:
        logger.error(f"Error saving cookies: {e}")
        return None

# Global dictionaries for tracking downloads
download_progress = {}
download_cache = {}

# List of User-Agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Mozilla/5.0 (Linux; Android 10; SM-A505FN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
]

def get_yt_dlp_opts(quality='best', cookies_str=None):
    # Randomly select a User-Agent
    selected_user_agent = random.choice(USER_AGENTS)
    
    # Convert quality setting to yt-dlp format string
    if quality == 'highest':
        format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == '1080p':
        format_string = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
    elif quality == '720p':
        format_string = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
    elif quality == '480p':
        format_string = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
    elif quality == '360p':
        format_string = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best'
    else:
        format_string = 'best[ext=mp4]/best'
    
    opts = {
        'format': format_string,
        'merge_output_format': 'mp4',  # Force MP4 output
        'quiet': False,
        'no_warnings': False,
        'verbose': True,
        'extract_flat': False,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'force_generic_extractor': False,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'extractor_args': {
            'youtube': {
                'skip': [],
                'player_skip': [],
                'player_client': ['android', 'web'],
                'max_comments': [0],
            }
        },
        'extractor_retries': 10,
        'file_access_retries': 10,
        'hls_prefer_native': True,
        'http_headers': {
            'User-Agent': selected_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Sec-GPC': '1'
        },
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
        'prefer_insecure': True,
        'allow_unplayable_formats': True,
        'check_formats': False,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    # Add random sleep between requests
    opts['sleep_interval'] = random.randint(2, 4)
    opts['max_sleep_interval'] = 5

    # Add cookies if provided
    if cookies_str:
        cookie_file = save_user_cookies(cookies_str)
        if cookie_file:
            opts['cookiefile'] = cookie_file
            opts['cookiesfrombrowser'] = None
            # Add additional YouTube-specific cookie handling
            if 'youtube.com' in cookies_str:
                opts['extractor_args']['youtube'].update({
                    'skip_webpage': [False],
                    'skip_initial_data': [False],
                    'embed_thumbnail': [True],
                    'player_skip': [],
                })
    
    return opts

def get_video_info(url, cookies_str=None):
    try:
        logger.info(f"Getting info for URL: {url}")
        
        # For YouTube shorts, convert to regular video URL
        if '/shorts/' in url:
            video_id = url.split('/shorts/')[1].split('?')[0]
            url = f'https://www.youtube.com/watch?v={video_id}'
            logger.info(f"Converted shorts URL to: {url}")
        
        # Add random delay
        time.sleep(random.uniform(2, 4))  # Random delay between 2-4 seconds
        
        if not cookies_str:
            logger.warning("No cookies provided. This may result in bot detection.")
            
        ydl_opts = get_yt_dlp_opts(cookies_str=cookies_str)
        ydl_opts.update({
            'extract_flat': True,  # Only extract metadata
            'quiet': True,
            'no_warnings': True
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                logger.info("Starting video extraction...")
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.error("No info returned from yt-dlp")
                    raise Exception("No video information found")
                
                # For playlists, get the first video
                if 'entries' in info:
                    if not info['entries']:
                        logger.error("No entries in playlist")
                        raise Exception("No videos found in playlist")
                    info = info['entries'][0]
                
                # Get best available format
                formats = info.get('formats', [])
                best_format = None
                for f in formats:
                    if f.get('ext') == 'mp4' and f.get('format_note') in ['720p', '1080p']:
                        best_format = f
                        break
                if not best_format and formats:
                    best_format = formats[-1]  # Get last format as it's usually the best quality
                
                result = {
                    'url': url,
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'webpage_url': info.get('webpage_url', url),
                    'format': f"{best_format.get('format_id', '')} - {best_format.get('resolution', '')} ({best_format.get('format_note', '')})" if best_format else 'best'
                }
                logger.info(f"Successfully extracted video info: {result}")
                return result
                
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if "Sign in to confirm your age" in error_msg:
                    logger.error("Age-restricted video detected")
                    raise Exception("This video is age-restricted. Please provide cookies from a logged-in account.")
                elif "Sign in to confirm you're not a bot" in error_msg:
                    logger.error("Bot detection triggered")
                    if not cookies_str:
                        raise Exception("YouTube thinks we're a bot. Please provide cookies from a logged-in account to bypass this.")
                    else:
                        raise Exception("Bot detection triggered even with cookies. Please try with fresh cookies from a recently logged-in account.")
                else:
                    logger.error(f"Download error: {error_msg}")
                    raise
                
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting video info: {error_msg}")
        return {'error': error_msg}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_videos_info():
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        cookies = data.get('cookies', '')  # Get cookies from request
        videos_info = []
        errors = []

        logger.info(f"Received video info request for URLs: {urls}")

        for url in urls:
            try:
                info = get_video_info(url, cookies)
                if 'error' in info:
                    error_msg = f"Error with URL {url}: {info['error']}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    videos_info.append(info)
                    logger.info(f"Successfully extracted info: {info}")
            except Exception as e:
                error_msg = f"Error with URL {url}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        response_data = {
            'videos': videos_info,
            'errors': errors
        }
        logger.info(f"Sending response: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in video info endpoint: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        logger.info(f"Received download request with data: {data}")
        
        urls = data.get('urls', [])
        quality = data.get('quality', 'highest')
        cookies = data.get('cookies', '')
        
        if not urls:
            logger.error("No URLs provided")
            return jsonify({'error': 'No URLs provided'}), 400

        # Process each URL
        results = []
        for url in urls:
            try:
                # Generate unique filename
                filename = f"video_{int(time.time())}_{random.randint(1000, 9999)}.mp4"
                output_path = os.path.join(DOWNLOAD_FOLDER, filename)
                
                # Configure yt-dlp options
                ydl_opts = get_yt_dlp_opts(quality, cookies)
                ydl_opts.update({
                    'outtmpl': output_path,
                    'progress_hooks': [partial(handle_progress, filename=filename)],
                    'merge_output_format': 'mp4',  # Ensure MP4 output
                })
                
                # Start download
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Starting download for URL: {url}")
                    logger.info(f"Using format: {ydl_opts['format']}")
                    ydl.download([url])
                    
                # Verify file exists and is accessible
                if not os.path.exists(output_path):
                    raise Exception("Download completed but file not found")
                
                # Get file size
                file_size = os.path.getsize(output_path)
                if file_size == 0:
                    raise Exception("Downloaded file is empty")
                
                # Generate download URL with static path
                download_url = url_for('static', filename=f'downloads/{filename}', _external=True)
                
                results.append({
                    'url': url,
                    'status': 'success',
                    'download_url': download_url,
                    'filename': filename,
                    'file_size': file_size
                })
                logger.info(f"Download completed for {url}, size: {file_size} bytes")
                
            except Exception as e:
                error_msg = f"Error downloading {url}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'url': url,
                    'status': 'error',
                    'error': error_msg
                })
        
        return jsonify({'results': results})
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in download endpoint: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/progress/<filename>')
def get_progress(filename):
    try:
        progress_data = download_progress.get(filename, {
            'status': 'unknown',
            'progress': 0
        })
        return jsonify(progress_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/static/downloads/<path:filename>')
def serve_download(filename):
    try:
        # Ensure the file exists
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found'}), 404
            
        # Get file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error(f"File is empty: {file_path}")
            return jsonify({'error': 'File is empty'}), 404
            
        # Set content disposition to force download
        response = send_from_directory(
            DOWNLOAD_FOLDER, 
            filename, 
            as_attachment=True,
            attachment_filename=filename
        )
        response.headers['Content-Length'] = file_size
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        logger.info(f"Serving file for download: {filename}, size: {file_size} bytes")
        return response
        
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return jsonify({'error': str(e)}), 404

def handle_progress(d, filename):
    if d['status'] == 'downloading':
        try:
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = (downloaded / total) * 100
            else:
                progress = 0
            
            download_progress[filename] = {
                'status': 'downloading',
                'progress': progress,
                'speed': d.get('speed', 0),
                'eta': d.get('eta', 0)
            }
        except Exception as e:
            logger.error(f"Error updating progress: {str(e)}")
    
    elif d['status'] == 'finished':
        download_progress[filename] = {
            'status': 'completed',
            'progress': 100
        }
    
    elif d['status'] == 'error':
        download_progress[filename] = {
            'status': 'error',
            'error': str(d.get('error', 'Unknown error'))
        }

if __name__ == '__main__':
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    
    # Determine if we're in development mode
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=debug)