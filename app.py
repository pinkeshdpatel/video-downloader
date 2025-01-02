from flask import Flask, request, jsonify, send_file, render_template, url_for
from flask_cors import CORS
import os
import time
import logging
import yt_dlp
import requests
from functools import partial
import threading

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
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Constants
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'downloads'))
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Clean up old downloads periodically
def cleanup_downloads():
    try:
        # Delete files older than 1 hour
        max_age = 3600  # 1 hour in seconds
        current_time = time.time()
        
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
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

# Run cleanup every hour
def schedule_cleanup():
    while True:
        cleanup_downloads()
        time.sleep(3600)  # Sleep for 1 hour

# Start cleanup thread
cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
cleanup_thread.start()

# Global dictionaries for tracking downloads
download_progress = {}
download_cache = {}

def get_yt_dlp_opts(quality='best'):
    return {
        'format': quality,
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'force_generic_extractor': False,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_color': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'extractor_args': {'youtube': {
            'skip': ['dash', 'hls'],
            'player_skip': ['js', 'configs', 'webpage']
        }},
        'extractor_retries': 5,
        'file_access_retries': 5,
        'hls_prefer_native': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    }

def get_video_info(url):
    try:
        logger.info(f"Getting info for URL: {url}")
        
        # Try different user agents if the first one fails
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        last_error = None
        for user_agent in user_agents:
            try:
                ydl_opts = get_yt_dlp_opts()
                ydl_opts['http_headers']['User-Agent'] = user_agent
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue
                    
                    # For playlists or channels, get the first video
                    if 'entries' in info:
                        if not info['entries']:
                            continue
                        info = info['entries'][0]
                    
                    return {
                        'url': url,
                        'title': info.get('title', 'Unknown Title'),
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', None),
                        'webpage_url': info.get('webpage_url', url)
                    }
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Failed with user agent {user_agent}: {e}")
                continue
        
        # If all user agents failed, raise the last error
        if last_error:
            raise Exception(f"Failed to get video info: {last_error}")
        else:
            raise Exception("No video information found")
            
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
        videos_info = []
        errors = []

        logger.info(f"Received video info request for URLs: {urls}")

        for url in urls:
            try:
                ydl_opts = get_yt_dlp_opts()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Extracting info for URL: {url}")
                    info = ydl.extract_info(url, download=False)
                    if info:
                        video_data = {
                            'url': url,
                            'title': info.get('title', 'Unknown Title'),
                            'thumbnail': info.get('thumbnail', ''),
                            'duration': info.get('duration', 0),
                            'format': info.get('format', ''),
                            'quality': info.get('quality', 0)
                        }
                        videos_info.append(video_data)
                        logger.info(f"Successfully extracted info: {video_data}")
                    else:
                        raise Exception("No video information found")
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
        
        if not urls:
            logger.error("No URLs provided")
            return jsonify({'error': 'No URLs provided'}), 400

        # Create downloads directory in the static folder
        download_dir = os.path.join(app.static_folder, 'downloads')
        os.makedirs(download_dir, exist_ok=True)
        logger.info(f"Using download directory: {download_dir}")

        # Convert quality setting to yt-dlp format string
        if quality == 'highest':
            format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            height = quality.replace('p', '')  # Convert '1080p' to '1080'
            format_string = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'

        logger.info(f"Using format string: {format_string}")

        results = []
        for index, url in enumerate(urls, 1):
            try:
                logger.info(f"Processing URL {index}: {url}")
                
                # First get video info to get the title
                info_result = get_video_info(url)
                if 'error' in info_result:
                    raise Exception(info_result['error'])
                
                # Create filename from video title
                video_title = info_result.get('title', f'video{index}')
                safe_title = "".join(x for x in video_title if x.isalnum() or x in (' ', '-', '_'))[:50]  # Limit length
                filename = f"video{index}_{safe_title}.mp4"
                filename = filename.replace(' ', '_')  # Replace spaces with underscores
                
                output_path = os.path.join(download_dir, filename)
                logger.info(f"Will download to: {output_path}")

                # Download the video
                ydl_opts = {
                    **get_yt_dlp_opts(format_string),
                    'outtmpl': output_path,
                    'progress_hooks': [lambda d: handle_progress(d, filename)]
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    error_code = ydl.download([url])
                    if error_code != 0:
                        raise Exception(f"yt-dlp returned error code: {error_code}")
                
                if not os.path.exists(output_path):
                    raise Exception("Download completed but file not found")

                file_size = os.path.getsize(output_path)
                logger.info(f"Download completed: {filename}, size: {file_size} bytes")
                
                # Generate download URL
                download_url = url_for('static', filename=f'downloads/{filename}', _external=True)
                logger.info(f"Download URL: {download_url}")

                results.append({
                    'url': url,
                    'filename': filename,
                    'status': 'completed',
                    'message': 'Download completed successfully',
                    'download_url': download_url,
                    'file_size': file_size,
                    'title': video_title
                })

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Download error for {url}: {error_msg}")
                results.append({
                    'url': url,
                    'error': error_msg,
                    'status': 'error'
                })
            
        logger.info(f"Returning results: {results}")
        return jsonify(results)

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
