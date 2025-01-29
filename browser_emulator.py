import random
import json
import os
from typing import Dict, Any, Optional
from http.cookiejar import MozillaCookieJar

class BrowserEmulator:
    def __init__(self, user_cookies: Optional[str] = None):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
        self.browser_profiles = {
            'chrome': {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br',
                'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec_ch_ua_mobile': '?0',
                'sec_ch_ua_platform': '"Windows"',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport_width': '1920',
                'viewport_height': '1080',
                'dpr': '1.25',
                'device_memory': '8',
                'hardware_concurrency': '8',
                'platform': 'Win32'
            },
            'firefox': {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.5',
                'accept_encoding': 'gzip, deflate, br',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport_width': '1920',
                'viewport_height': '1080',
                'dpr': '1',
                'device_memory': '8',
                'hardware_concurrency': '8',
                'platform': 'Win32'
            }
        }
        
        self.cookie_file = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if user_cookies:
            self._save_user_cookies(user_cookies)
        self._load_cookies()

    def _save_user_cookies(self, cookies_str: str) -> None:
        """Save user provided cookies to file"""
        try:
            # Create a temporary file with user cookies
            temp_cookie_file = os.path.join(os.path.dirname(__file__), f'user_cookies_{random.randint(1000, 9999)}.txt')
            with open(temp_cookie_file, 'w') as f:
                f.write(cookies_str)
            
            # Update cookie file path
            self.cookie_file = temp_cookie_file
        except Exception as e:
            print(f"Error saving user cookies: {e}")

    def _load_cookies(self):
        """Load cookies from file if it exists"""
        self.cookies = MozillaCookieJar(self.cookie_file)
        if os.path.exists(self.cookie_file):
            try:
                self.cookies.load(ignore_discard=True, ignore_expires=True)
            except Exception as e:
                print(f"Error loading cookies: {e}")

    def cleanup(self):
        """Clean up temporary cookie files"""
        try:
            if os.path.exists(self.cookie_file) and 'user_cookies_' in self.cookie_file:
                os.remove(self.cookie_file)
        except Exception as e:
            print(f"Error cleaning up cookies: {e}")

    def get_headers(self) -> Dict[str, str]:
        """Get random browser headers with enhanced fingerprinting"""
        user_agent = random.choice(self.user_agents)
        profile = random.choice(list(self.browser_profiles.values()))
        
        headers = {
            'User-Agent': user_agent,
            'Accept': profile['accept'],
            'Accept-Language': profile['accept_language'],
            'Accept-Encoding': profile['accept_encoding'],
            'Sec-Fetch-Dest': profile['sec_fetch_dest'],
            'Sec-Fetch-Mode': profile['sec_fetch_mode'],
            'Sec-Fetch-Site': profile['sec_fetch_site'],
            'Sec-Fetch-User': profile['sec_fetch_user'],
            'Upgrade-Insecure-Requests': profile['upgrade_insecure_requests'],
            'DNT': '1',
            'Connection': 'keep-alive'
        }
        
        return headers

    def get_yt_dlp_options(self, quality: str = 'best') -> Dict[str, Any]:
        """Get yt-dlp options with enhanced browser emulation"""
        headers = self.get_headers()
        
        options = {
            'format': quality,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'user_agent': headers['User-Agent'],
            'referer': 'https://www.youtube.com/',
            'http_headers': headers,
            'socket_timeout': 30,
            'retries': 5,
            'nocheckcertificate': True,
            'cookiefile': self.cookie_file if os.path.exists(self.cookie_file) else None,
            'sleep_interval': random.randint(1, 3),  # Random delay between requests
            'max_sleep_interval': 5,
            'geo_bypass': True,
            'geo_bypass_country': 'US'
        }
        
        return options
