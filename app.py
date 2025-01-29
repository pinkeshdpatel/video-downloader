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

def get_yt_dlp_opts(quality='best', cookies_str=None, is_shorts=False):
    # Randomly select a User-Agent
    selected_user_agent = random.choice(USER_AGENTS)
    
    # Special format string for shorts
    if is_shorts:
        format_string = 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b'
    else:
        # Regular format strings for normal videos
        if quality == 'highest':
            format_string = 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b'
        elif quality == '1080p':
            format_string = 'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4] / bv*[height<=1080]+ba/b[height<=1080]'
        elif quality == '720p':
            format_string = 'bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4] / bv*[height<=720]+ba/b[height<=720]'
        elif quality == '480p':
            format_string = 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4] / bv*[height<=480]+ba/b[height<=480]'
        elif quality == '360p':
            format_string = 'bv*[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360][ext=mp4] / bv*[height<=360]+ba/b[height<=360]'
        else:
            format_string = 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b'

    opts = {
        'format': format_string,
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': False,
        'verbose': True,
        'extract_flat': False,
        'socket_timeout': 30,
        'retries': 15,
        'fragment_retries': 15,
        'retry_sleep_functions': {'http': lambda n: 5 * (2 ** (n-1))},
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
                'player_client': ['android', 'web', 'tv_embedded', 'mobile'],
                'max_comments': [0],
                'player_params': ['all'],
                'embed_thumbnail': [True],
                'innertube_key': ['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'],
            }
        },
        'extractor_retries': 15,
        'file_access_retries': 15,
        'hls_prefer_native': True,
        'http_headers': {
            'User-Agent': selected_user_agent,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        },
        'youtube_include_dash_manifest': True,
        'youtube_include_hls_manifest': True,
        'prefer_insecure': True,
        'allow_unplayable_formats': True,  # Changed to True for shorts
        'check_formats': False,  # Changed to False for shorts
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    # Add random sleep between requests with longer delays
    opts['sleep_interval'] = random.randint(3, 6)
    opts['max_sleep_interval'] = 8

    # Add cookies if provided
    if cookies_str:
        cookie_file = save_user_cookies(cookies_str)
        if cookie_file:
            opts['cookiefile'] = cookie_file
            opts['cookiesfrombrowser'] = None
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
        
        # Check if it's a shorts URL
        is_shorts = '/shorts/' in url
        if is_shorts:
            video_id = url.split('/shorts/')[1].split('?')[0]
            url = f'https://www.youtube.com/watch?v={video_id}'
            logger.info(f"Converted shorts URL to: {url}")
        
        # Add random delay
        time.sleep(random.uniform(2, 4))
        
        if not cookies_str:
            logger.warning("No cookies provided. This may result in bot detection.")
            
        ydl_opts = get_yt_dlp_opts(cookies_str=cookies_str, is_shorts=is_shorts)
        ydl_opts.update({
            'extract_flat': True,
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
                
                # For shorts, prefer vertical video formats
                if is_shorts:
                    for f in formats:
                        if f.get('ext') == 'mp4' and f.get('height', 0) > f.get('width', 0):
                            best_format = f
                            break
                
                # If no vertical format found or not shorts, use regular format selection
                if not best_format:
                    for f in formats:
                        if f.get('ext') == 'mp4' and f.get('format_note') in ['720p', '1080p']:
                            best_format = f
                            break
                
                if not best_format and formats:
                    best_format = formats[-1]
                
                result = {
                    'url': url,
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'webpage_url': info.get('webpage_url', url),
                    'format': f"{best_format.get('format_id', '')} - {best_format.get('resolution', '')} ({best_format.get('format_note', '')})" if best_format else 'best',
                    'is_shorts': is_shorts
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

def handle_download_error(error_msg, cookies_str=None):
    """Handle different types of download errors and return appropriate messages"""
    if "HTTP Error 403" in error_msg:
        if not cookies_str:
            return "Access forbidden by YouTube. Please provide cookies from a logged-in account."
        else:
            return "Access forbidden even with cookies. Please try with fresh cookies from a different account or wait a few minutes."
    elif "Sign in to confirm you're not a bot" in error_msg:
        return "YouTube bot detection triggered. Please provide fresh cookies from a logged-in account."
    elif "Sign in to confirm your age" in error_msg:
        return "This video is age-restricted. Please provide cookies from a logged-in account."
    elif "This video is not available" in error_msg:
        return "This video is not available. It might be private or deleted."
    else:
        return f"Download error: {error_msg}"

def validate_video_file(file_path):
    """Validate that the downloaded file is a proper video file"""
    try:
        if not os.path.exists(file_path):
            return False, "File does not exist"
            
        file_size = os.path.getsize(file_path)
        if file_size < 1000000:  # Less than 1MB
            return False, f"File too small ({file_size} bytes)"
            
        # Check if file is a valid MP4
        with open(file_path, 'rb') as f:
            header = f.read(8)
            if not header.startswith(b'\x00\x00\x00') and not b'ftyp' in header:
                return False, "Not a valid MP4 file"
                
        return True, None
    except Exception as e:
        return False, str(e)

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
                })
                
                # Start download with retry mechanism
                max_retries = 3
                retry_count = 0
                last_error = None
                
                while retry_count < max_retries:
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            logger.info(f"Starting download for URL: {url} (Attempt {retry_count + 1}/{max_retries})")
                            logger.info(f"Using format: {ydl_opts['format']}")
                            ydl.download([url])
                            
                            # Validate the downloaded file
                            is_valid, error_msg = validate_video_file(output_path)
                            if not is_valid:
                                raise Exception(f"Invalid video file: {error_msg}")
                                
                            break  # If successful, break the retry loop
                            
                    except Exception as e:
                        last_error = str(e)
                        retry_count += 1
                        # Clean up invalid file if it exists
                        if os.path.exists(output_path):
                            os.remove(output_path)
                            
                        if retry_count < max_retries:
                            logger.warning(f"Attempt {retry_count} failed, retrying in {5 * retry_count} seconds...")
                            time.sleep(5 * retry_count)  # Exponential backoff
                        else:
                            raise Exception(handle_download_error(last_error, cookies))
                
                # Get file size
                file_size = os.path.getsize(output_path)
                
                # Generate download URL
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
                error_msg = handle_download_error(str(e), cookies)
                logger.error(f"Error downloading {url}: {error_msg}")
                results.append({
                    'url': url,
                    'status': 'error',
                    'error': error_msg
                })
                # Clean up any failed download
                if os.path.exists(output_path):
                    os.remove(output_path)
        
        return jsonify({'results': results})
        
    except Exception as e:
        error_msg = handle_download_error(str(e), cookies)
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