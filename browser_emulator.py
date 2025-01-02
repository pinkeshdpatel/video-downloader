import random
import json
import os
from typing import Dict, Any

class BrowserEmulator:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.browser_profiles = {
            'chrome': {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.9',
                'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec_ch_ua_mobile': '?0',
                'sec_ch_ua_platform': '"Windows"',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1'
            },
            'firefox': {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.5',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1'
            }
        }

    def get_headers(self) -> Dict[str, str]:
        """Get random browser headers"""
        user_agent = random.choice(self.user_agents)
        profile = random.choice(list(self.browser_profiles.values()))
        
        headers = {
            'User-Agent': user_agent,
            'Accept': profile['accept'],
            'Accept-Language': profile['accept_language'],
            'Sec-Fetch-Dest': profile['sec_fetch_dest'],
            'Sec-Fetch-Mode': profile['sec_fetch_mode'],
            'Sec-Fetch-Site': profile['sec_fetch_site'],
            'Sec-Fetch-User': profile['sec_fetch_user'],
            'Upgrade-Insecure-Requests': profile['upgrade_insecure_requests']
        }
        
        return headers

    def get_yt_dlp_options(self, quality: str = 'best') -> Dict[str, Any]:
        """Get yt-dlp options with browser emulation"""
        headers = self.get_headers()
        
        return {
            'format': quality,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'user_agent': headers['User-Agent'],
            'referer': 'https://www.youtube.com/',
            'http_headers': headers,
            'cookiesfrombrowser': ('chrome',),
            'socket_timeout': 30,
            'retries': 5,
            'nocheckcertificate': True
        }
