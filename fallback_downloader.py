import yt_dlp
import requests
import time
import logging
from typing import Optional, Dict, Any, Callable

class FallbackDownloader:
    def __init__(self, proxy_manager=None, browser_emulator=None):
        self.proxy_manager = proxy_manager
        self.browser_emulator = browser_emulator
        self.logger = logging.getLogger(__name__)

    def _try_download_with_yt_dlp(self, url: str, output_path: str, ydl_opts: Dict[str, Any]) -> bool:
        """Try downloading with yt-dlp"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            self.logger.error(f"yt-dlp download failed: {e}")
            return False

    def _try_download_with_requests(self, url: str, output_path: str, headers: Dict[str, str]) -> bool:
        """Try downloading directly with requests"""
        try:
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Requests download failed: {e}")
            return False

    def download(self, url: str, output_path: str, quality: str = 'best',
                progress_callback: Optional[Callable] = None) -> bool:
        """
        Try different methods to download the video
        Returns True if any method succeeds
        """
        methods_tried = 0
        max_attempts = 3

        while methods_tried < max_attempts:
            # Get fresh headers and proxy for each attempt
            headers = self.browser_emulator.get_headers() if self.browser_emulator else {}
            proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None

            # Basic yt-dlp options
            ydl_opts = {
                'format': quality,
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
            }

            # Add browser emulation if available
            if self.browser_emulator:
                ydl_opts.update(self.browser_emulator.get_yt_dlp_options(quality))

            # Add proxy if available
            if proxy:
                ydl_opts['proxy'] = proxy.get('http')

            # Method 1: Try yt-dlp with current settings
            if self._try_download_with_yt_dlp(url, output_path, ydl_opts):
                return True

            # Method 2: Try with different format options
            ydl_opts['format'] = 'best/bestvideo+bestaudio'
            if self._try_download_with_yt_dlp(url, output_path, ydl_opts):
                return True

            # Method 3: Try direct download if we have a direct video URL
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    direct_url = info.get('url')
                    if direct_url and self._try_download_with_requests(direct_url, output_path, headers):
                        return True
            except:
                pass

            methods_tried += 1
            if methods_tried < max_attempts:
                time.sleep(2)  # Wait before next attempt

        return False
