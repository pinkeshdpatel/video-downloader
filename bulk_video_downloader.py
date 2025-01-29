import os
import sys
from tqdm import tqdm
import yt_dlp
import instaloader
from urllib.parse import urlparse, parse_qs
from browser_emulator import BrowserEmulator
from proxy_manager import ProxyManager

def create_download_folder():
    download_dir = os.path.join(os.getcwd(), 'downloads')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    return download_dir

class DownloadLogger:
    def debug(self, msg):
        if msg.startswith('[download]'):
            print(msg)
    
    def warning(self, msg):
        pass
    
    def error(self, msg):
        print(f"Error: {msg}")

def download_youtube_video(link, index, download_dir, user_cookies=None):
    browser = None
    try:
        # Initialize browser emulator and proxy manager
        browser = BrowserEmulator(user_cookies)
        proxy_manager = ProxyManager()
        
        # Get yt-dlp options with browser emulation
        ydl_opts = browser.get_yt_dlp_options()
        
        # Add download specific options
        ydl_opts.update({
            'outtmpl': os.path.join(download_dir, f'{index}.%(ext)s'),
            'format': 'best[ext=mp4]',
            'logger': DownloadLogger(),
            'progress_hooks': [lambda d: print(f'\rDownloading... {d["_percent_str"]}', end='') 
                             if d['status'] == 'downloading' else None],
        })
        
        # Try with different proxies until success
        max_retries = 3
        for attempt in range(max_retries):
            try:
                proxy = proxy_manager.get_proxy()
                if proxy:
                    ydl_opts['proxy'] = proxy['http']
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    print(f'\nDownloaded YouTube video: {index}.mp4')
                    return True
                    
            except Exception as e:
                if proxy:
                    proxy_manager.remove_proxy(proxy)
                if attempt == max_retries - 1:
                    raise e
                print(f'\nRetrying with different proxy... (Attempt {attempt + 2}/{max_retries})')
                continue
                
    except Exception as e:
        print(f'\nError downloading YouTube video: {e}')
        return False
    finally:
        if browser:
            browser.cleanup()

def download_youtube_playlist(playlist_url, start_index, download_dir, user_cookies=None):
    browser = None
    try:
        # Initialize browser emulator and proxy manager
        browser = BrowserEmulator(user_cookies)
        proxy_manager = ProxyManager()
        
        # Get yt-dlp options
        ydl_opts = browser.get_yt_dlp_options()
        ydl_opts.update({
            'outtmpl': os.path.join(download_dir, f'%(playlist_index)d.%(ext)s'),
            'format': 'best[ext=mp4]',
            'logger': DownloadLogger(),
            'playliststart': start_index,
        })
        
        proxy = proxy_manager.get_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy['http']
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=True)
            videos = info['entries']
            success_count = len([v for v in videos if v is not None])
            print(f'\nSuccessfully downloaded {success_count} videos from playlist')
            return start_index + len(videos)
            
    except Exception as e:
        print(f'\nError processing playlist: {e}')
        return start_index
    finally:
        if browser:
            browser.cleanup()

def download_instagram_video(link, index, download_dir):
    try:
        L = instaloader.Instaloader()
        # Extract post shortcode from URL
        parsed_url = urlparse(link)
        shortcode = parsed_url.path.split('/')[-2]
        
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        if not post.is_video:
            print(f'\nError: The Instagram post {index} is not a video')
            return False
            
        print(f'\nDownloading Instagram video {index}...')
        output_path = os.path.join(download_dir, f'{index}.mp4')
        L.download_post(post, target=os.path.dirname(output_path))
        
        # Rename the downloaded file to our index-based naming
        downloaded_files = [f for f in os.listdir(os.path.dirname(output_path)) if f.endswith('.mp4')]
        if downloaded_files:
            os.rename(
                os.path.join(os.path.dirname(output_path), downloaded_files[0]),
                output_path
            )
        print(f'Downloaded Instagram video: {index}.mp4')
        return True
    except Exception as e:
        print(f'\nError downloading Instagram video: {e}')
        return False

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def main():
    download_dir = create_download_folder()
    print("Welcome to Bulk Video Downloader!")
    print("Enter video links separated by commas")
    print("Supported formats:")
    print("- YouTube videos: https://youtube.com/watch?v=...")
    print("- YouTube shorts: https://youtube.com/shorts/...")
    print("- YouTube playlists: https://youtube.com/playlist?list=...")
    print("- Instagram posts: https://instagram.com/p/...")
    
    print("\nOptional: Paste your YouTube cookies to improve download success rate")
    print("(You can get cookies using browser extensions like 'Get cookies.txt')")
    user_cookies = input("Enter cookies (or press Enter to skip): ").strip()
    
    links = input('\nEnter links: ').split(',')
    index = 1
    
    for link in links:
        link = link.strip()
        if not validate_url(link):
            print(f'\nInvalid URL format: {link}')
            continue
            
        if 'youtube.com' in link or 'youtu.be' in link:
            if 'playlist' in link:
                index = download_youtube_playlist(link, index, download_dir, user_cookies)
            else:
                if download_youtube_video(link, index, download_dir, user_cookies):
                    index += 1
        elif 'instagram.com' in link:
            if download_instagram_video(link, index, download_dir):
                index += 1
        else:
            print(f'\nUnsupported platform: {link}')
    
    print('\nAll downloads completed!')
    print(f'Videos are saved in the "downloads" folder')

if __name__ == '__main__':
    main()
