import requests
import random
import time
from typing import List, Dict, Optional

class ProxyManager:
    def __init__(self):
        self.proxies: List[Dict[str, str]] = []
        self.last_update = 0
        self.update_interval = 3600  # Update proxy list every hour

    def _fetch_proxies(self) -> None:
        """Fetch free proxies from multiple sources"""
        try:
            # Free proxy list API (you can replace with paid service for better reliability)
            response = requests.get('https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt')
            if response.status_code == 200:
                proxy_list = response.text.split('\n')
                self.proxies = [
                    {
                        'http': f'http://{proxy}',
                        'https': f'http://{proxy}'
                    }
                    for proxy in proxy_list
                    if proxy.strip()
                ]

        except Exception as e:
            print(f"Error fetching proxies: {e}")
            # Fallback to some reliable free proxies
            self.proxies = [
                {'http': 'http://localhost:8080', 'https': 'http://localhost:8080'},
                # Add more fallback proxies here
            ]

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random working proxy"""
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            self._fetch_proxies()
            self.last_update = current_time

        if not self.proxies:
            return None

        # Test proxy before returning
        for _ in range(min(5, len(self.proxies))):
            proxy = random.choice(self.proxies)
            try:
                test_response = requests.get(
                    'https://www.google.com',
                    proxies=proxy,
                    timeout=5
                )
                if test_response.status_code == 200:
                    return proxy
            except:
                continue

        return None

    def remove_proxy(self, proxy: Dict[str, str]) -> None:
        """Remove a non-working proxy from the list"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
