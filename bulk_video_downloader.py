import os
import sys
from tqdm import tqdm
import pytube
import instaloader
from urllib.parse import urlparse, parse_qs

def create_download_folder():
    download_dir = os.path.join(os.getcwd(), 'downloads')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    return download_dir

def on_progress(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = (bytes_downloaded / total_size) * 100
    sys.stdout.write(f'\rDownloading... {percentage:.1f}%')
    sys.stdout.flush()

def convert_youtube_url(url):
    """Convert YouTube Shorts URL to standard YouTube URL"""
    if 'youtube.com/shorts/' in url:
        video_id = url.split('/shorts/')[1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    return url

def download_youtube_video(link, index, download_dir):
    try:
        # Convert shorts URL to standard URL if needed
        link = convert_youtube_url(link)
        yt = pytube.YouTube(link, on_progress_callback=on_progress)
        print(f'\nTitle: {yt.title}')
        
        # Get available streams
        streams = yt.streams.filter(progressive=True, file_extension='mp4')
        print("\nAvailable qualities:")
        for i, stream in enumerate(streams, 1):
            print(f"{i}. {stream.resolution}")
        
        choice = input("\nSelect quality (enter number): ")
        try:
            stream = streams[int(choice)-1]
        except:
            stream = streams.get_highest_resolution()
            print("Invalid choice, using highest quality")
        
        output_path = os.path.join(download_dir, f'{index}.mp4')
        stream.download(filename=output_path)
        print(f'\nDownloaded YouTube video: {index}.mp4')
        return True
    except Exception as e:
        print(f'\nError downloading YouTube video: {e}')
        return False

def download_youtube_playlist(playlist_url, start_index, download_dir):
    try:
        playlist = pytube.Playlist(playlist_url)
        print(f'\nPlaylist: {playlist.title}')
        print(f'Total videos: {len(playlist.video_urls)}')
        
        success_count = 0
        for i, video_url in enumerate(playlist.video_urls, start=start_index):
            print(f'\nDownloading video {i}...')
            if download_youtube_video(video_url, i, download_dir):
                success_count += 1
        
        print(f'\nSuccessfully downloaded {success_count} videos from playlist')
        return start_index + len(playlist.video_urls)
    except Exception as e:
        print(f'\nError processing playlist: {e}')
        return start_index

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
    
    links = input('\nEnter links: ').split(',')
    index = 1
    
    for link in links:
        link = link.strip()
        if not validate_url(link):
            print(f'\nInvalid URL format: {link}')
            continue
            
        if 'youtube.com' in link or 'youtu.be' in link:
            if 'playlist' in link:
                index = download_youtube_playlist(link, index, download_dir)
            else:
                if download_youtube_video(link, index, download_dir):
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
