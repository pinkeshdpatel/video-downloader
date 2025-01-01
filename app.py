import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import instaloader
from urllib.parse import urlparse
import json
import time
import logging
import requests
from functools import partial
import threading

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Create downloads directory if it doesn't exist
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Global download cache to prevent duplicate downloads
download_cache = {}

def get_video_info(url):
    """Get video information without downloading"""
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            ydl_opts = {
                'format': 'best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'socket_timeout': 30,
                'retries': 3
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('format_note')]
                qualities = sorted(list(set(f['format_note'] for f in formats if f.get('format_note'))))
                
                video_info = {
                    'title': info.get('title', 'Unknown Title'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration'),
                    'author': info.get('uploader', 'Unknown Author'),
                    'qualities': qualities or ['best'],  # Fallback to 'best' if no qualities found
                    'url': url,
                    'type': 'youtube'
                }
                logger.debug(f"YouTube video info: {video_info}")
                return video_info
            
        elif 'instagram.com' in url:
            L = instaloader.Instaloader()
            parsed_url = urlparse(url)
            shortcode = parsed_url.path.split('/')[-2]
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            
            info = {
                'title': f'Instagram Video by {post.owner_username}',
                'thumbnail': post.url,
                'author': post.owner_username,
                'qualities': ['default'],
                'url': url,
                'type': 'instagram'
            }
            logger.debug(f"Instagram video info: {info}")
            return info
            
        else:
            logger.error(f"Unsupported URL: {url}")
            return {
                'error': 'Unsupported platform',
                'url': url
            }
            
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return {
            'error': str(e),
            'url': url
        }

def download_progress_hook(d, progress_key):
    """Progress hook for yt-dlp"""
    if d['status'] == 'downloading':
        progress = d.get('_percent_str', 'unknown progress')
        speed = d.get('_speed_str', 'unknown speed')
        logger.debug(f"Download progress for {progress_key}: {progress} at {speed}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished for {progress_key}")

def download_youtube_video(url, quality, filename):
    """Download YouTube video"""
    try:
        logger.info(f"Starting YouTube download: {url} with quality: {quality} to file: {filename}")
        output_path = os.path.join(DOWNLOAD_FOLDER, filename)
        
        # Check if already downloading
        progress_key = f"{url}_{quality}"
        if progress_key in download_cache:
            logger.info(f"Download already in progress for {url}")
            return False
            
        download_cache[progress_key] = True
        
        try:
            ydl_opts = {
                'format': f'bestvideo[ext=mp4][height<={quality[:-1]}]+bestaudio[ext=m4a]/best[ext=mp4]/best' if quality != 'highest' else 'best[ext=mp4]/best',
                'outtmpl': output_path,
                'quiet': False,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 3,
                'verbose': True,
                'progress_hooks': [partial(download_progress_hook, progress_key=progress_key)],
            }
            
            logger.debug(f"YouTube-DL options: {ydl_opts}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    logger.info(f"Starting download with yt-dlp for {url}")
                    ydl.download([url])
                    logger.info(f"yt-dlp download completed for {url}")
                except Exception as e:
                    logger.error(f"Error in yt-dlp download: {str(e)}")
                    raise
                
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    logger.info(f"Successfully downloaded: {filename} (size: {file_size} bytes)")
                    if file_size > 0:
                        return True
                    else:
                        logger.error(f"Downloaded file is empty: {output_path}")
                        os.remove(output_path)
                        return False
                else:
                    logger.error(f"File not found after download: {output_path}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error during YouTube download: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
        finally:
            download_cache.pop(progress_key, None)
            
    except Exception as e:
        logger.error(f"Error in download_youtube_video: {str(e)}")
        return False

def download_instagram_video(url, filename):
    """Download Instagram video"""
    try:
        logger.info(f"Downloading Instagram video: {url}")
        L = instaloader.Instaloader()
        parsed_url = urlparse(url)
        shortcode = parsed_url.path.split('/')[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        if not post.is_video:
            logger.error(f"Instagram post is not a video: {url}")
            return False
            
        output_path = os.path.join(DOWNLOAD_FOLDER, filename)
        temp_dir = os.path.join(DOWNLOAD_FOLDER, 'temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        logger.debug(f"Downloading to temp directory: {temp_dir}")
        L.download_post(post, target=temp_dir)
        
        # Find and rename the downloaded video file
        video_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp4')]
        if video_files:
            source_path = os.path.join(temp_dir, video_files[0])
            logger.debug(f"Moving {source_path} to {output_path}")
            os.rename(source_path, output_path)
            
            # Clean up temp directory
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
            
            logger.info(f"Successfully downloaded: {filename}")
            return True
        else:
            logger.error("No video file found after download")
            return False
            
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def video_info():
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        logger.info(f"Received video info request for {len(urls)} URLs")
        
        results = []
        for url in urls:
            url = url.strip()
            info = get_video_info(url)
            if info is None:
                info = {'error': 'Failed to get video info', 'url': url}
            results.append(info)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in video_info endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        quality = data.get('quality', 'highest')
        logger.info(f"Received download request for {len(urls)} URLs with quality: {quality}")
        
        # Clear old files from download folder
        try:
            for file in os.listdir(DOWNLOAD_FOLDER):
                file_path = os.path.join(DOWNLOAD_FOLDER, file)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing file {file_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error cleaning download folder: {str(e)}")
        
        results = []
        download_index = 1  # Counter for filenames
        
        for url in urls:
            try:
                url = url.strip()
                logger.info(f"Processing URL {download_index}: {url}")
                
                # Get video info to get title
                info = get_video_info(url)
                if info.get('error'):
                    error_msg = f"Error getting video info: {info['error']}"
                    logger.error(error_msg)
                    results.append({
                        'url': url,
                        'success': False,
                        'error': error_msg,
                        'title': info.get('title', 'Unknown')
                    })
                    continue
                
                # Use simple numbered filename
                filename = f'video{download_index}.mp4'
                output_path = os.path.join(DOWNLOAD_FOLDER, filename)
                logger.info(f"Using filename: {filename} for {url}")
                
                success = False
                if 'youtube.com' in url or 'youtu.be' in url:
                    success = download_youtube_video(url, quality, filename)
                elif 'instagram.com' in url:
                    success = download_instagram_video(url, filename)
                
                # Verify file exists and has size
                file_exists = os.path.exists(output_path)
                file_size = os.path.getsize(output_path) if file_exists else 0
                logger.info(f"File status - exists: {file_exists}, size: {file_size} bytes")
                
                if success and file_exists and file_size > 0:
                    logger.info(f"Download successful: {filename}")
                    result = {
                        'url': url,
                        'success': True,
                        'filename': filename,
                        'title': info.get('title', 'Unknown Title')
                    }
                    download_index += 1  # Only increment counter for successful downloads
                else:
                    error_msg = "Download failed - file not found or empty"
                    logger.error(error_msg)
                    result = {
                        'url': url,
                        'success': False,
                        'error': error_msg,
                        'title': info.get('title', 'Unknown Title')
                    }
                
                results.append(result)
                logger.info(f"Download result for {url}: {result}")
                
            except Exception as e:
                error_msg = f"Error processing URL {url}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'url': url,
                    'success': False,
                    'error': error_msg,
                    'title': 'Unknown'
                })
        
        return jsonify(results)
        
    except Exception as e:
        error_msg = f"Error in download endpoint: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        logger.info(f"Request to download file: {file_path}")
        
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 404
            
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            error_msg = f"Empty file: {file_path}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 404
            
        logger.info(f"Sending file: {file_path} (size: {file_size} bytes)")
        try:
            response = send_file(
                file_path,
                as_attachment=True,
                download_name=filename,
                max_age=0
            )
            response.headers['Content-Length'] = file_size
            return response
        except Exception as e:
            error_msg = f"Error sending file: {str(e)}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
            
    except Exception as e:
        error_msg = f"Error in download_file endpoint: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    # Create download folder if it doesn't exist
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
    
    # In production, the host and port will be set by the environment
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
