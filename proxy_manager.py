import requests
import random
import time
import os
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

class ProxyManager:
    def __init__(self):
        self.proxies: List[Dict[str, str]] = []
        self.last_update = 0
        self.update_interval = 1800  # Update proxy list every 30 minutes
        self.proxy_file = os.path.join(os.path.dirname(__file__), 'proxyscrape_premium_http_proxies.txt')
        self._load_proxies()

    def _load_proxies(self) -> None:
        """Load proxies from file"""
        if os.path.exists(self.proxy_file):
            try:
                with open(self.proxy_file, 'r') as f:
                    proxy_list = f.read().strip().split('\n')
                self.proxies = [
                    {
                        'http': f'http://{proxy}',
                        'https': f'http://{proxy}'
                    }
                    for proxy in proxy_list
                    if proxy.strip()
                ]
            except Exception as e:
                print(f"Error loading proxies from file: {e}")
                self._fetch_proxies()
        else:
            self._fetch_proxies()

    def _fetch_proxies(self) -> None:
        """Fetch free proxies from multiple sources"""
        try:
            # Try multiple free proxy sources
            sources = [
                'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
                'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
                'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt'
            ]
            
            proxy_list = set()
            for source in sources:
                try:
                    response = requests.get(source, timeout=10)
                    if response.status_code == 200:
                        proxies = response.text.strip().split('\n')
                        proxy_list.update(proxies)
                except:
                    continue
            
            self.proxies = [
                {
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                }
                for proxy in proxy_list
                if proxy.strip()
            ]

            # Save working proxies to file
            if self.proxies:
                with open(self.proxy_file, 'w') as f:
                    f.write('\n'.join(proxy.strip() for proxy in proxy_list))

        except Exception as e:
            print(f"Error fetching proxies: {e}")
            # Fallback to some reliable free proxies
            self.proxies = [
                {'http': 'http://localhost:8080', 'https': 'http://localhost:8080'},
            ]

    def _test_proxy(self, proxy: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Test a single proxy"""
        try:
            test_urls = [
                'https://www.youtube.com',
                'https://www.google.com'
            ]
            
            for url in test_urls:
                response = requests.get(
                    url,
                    proxies=proxy,
                    timeout=5,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
                )
                if response.status_code != 200:
                    return None
            return proxy
        except:
            return None

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random working proxy with parallel testing"""
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            self._load_proxies()
            self.last_update = current_time

        if not self.proxies:
            return None

        # Test multiple proxies in parallel
        test_proxies = random.sample(self.proxies, min(5, len(self.proxies)))
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_proxy = {
                executor.submit(self._test_proxy, proxy): proxy 
                for proxy in test_proxies
            }
            
            for future in as_completed(future_to_proxy):
                result = future.result()
                if result:
                    return result

        return None

    def remove_proxy(self, proxy: Dict[str, str]) -> None:
        """Remove a non-working proxy from the list"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            # Update proxy file
            if os.path.exists(self.proxy_file):
                with open(self.proxy_file, 'w') as f:
                    proxy_list = [
                        p['http'].replace('http://', '')
                        for p in self.proxies
                    ]
                    f.write('\n'.join(proxy_list))
