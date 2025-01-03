from flask import Flask, request, jsonify, send_file, render_template, url_for
from flask_cors import CORS
import os
import time
import logging
import yt_dlp
import requests
from functools import partial
import threading
import random

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
    opts = {
        'format': quality,
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
        'cookiefile': 'cookies.txt',
        'cookiesfrombrowser': ('chrome',),
        'extractor_args': {
            'youtube': {
                'skip': [],
                'player_skip': []
            }
        },
        'extractor_retries': 10,
        'file_access_retries': 10,
        'hls_prefer_native': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    }

    # Add random sleep between requests
    opts['sleep_interval'] = (1, 3)
    opts['max_sleep_interval'] = 5

    return opts

def get_video_info(url):
    try:
        logger.info(f"Getting info for URL: {url}")
        
        # For YouTube shorts, convert to regular video URL
        if '/shorts/' in url:
            video_id = url.split('/shorts/')[1].split('?')[0]
            url = f'https://www.youtube.com/watch?v={video_id}'
            logger.info(f"Converted shorts URL to: {url}")
        
        # Add random delay
        time.sleep(random.uniform(1, 3))
        
        ydl_opts = get_yt_dlp_opts()
        
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
                
                # Log available formats
                if 'formats' in info:
                    logger.info(f"Available formats: {[f\"{f.get('format_id')} - {f.get('ext')} - {f.get('resolution')}\" for f in info['formats']]}")
                else:
                    logger.warning("No formats available in video info")
                
                result = {
                    'url': url,
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'webpage_url': info.get('webpage_url', url),
                    'formats': info.get('formats', [])
                }
                logger.info(f"Successfully extracted video info: {result}")
                return result
                
            except Exception as e:
                logger.error(f"Error during extraction: {str(e)}")
                # Get detailed error info
                if hasattr(e, 'exc_info'):
                    logger.error(f"Exception info: {e.exc_info}")
                if hasattr(e, 'msg'):
                    logger.error(f"Error message: {e.msg}")
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
                
                # Convert shorts URL if needed
                if '/shorts/' in url:
                    video_id = url.split('/shorts/')[1].split('?')[0]
                    url = f'https://www.youtube.com/watch?v={video_id}'
                    logger.info(f"Converted shorts URL to: {url}")
                
                # Add random delay between videos
                if index > 1:
                    time.sleep(random.uniform(1, 3))
                
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
        
        if not any(result.get('status') == 'completed' for result in results):
            return jsonify({'error': 'No valid videos found', 'details': results}), 400
            
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
