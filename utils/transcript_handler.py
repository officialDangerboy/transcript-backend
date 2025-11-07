import re
import random
import os
from pathlib import Path
from http.cookiejar import MozillaCookieJar
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
import requests
from unittest.mock import patch

# ======================================================
# COOKIE MANAGEMENT WITH ENVIRONMENT VARIABLE SUPPORT
# ======================================================
def get_cookies_from_env():
    """
    Get cookies content from environment variable
    Returns the cookie content as string or None
    """
    cookie_content = os.environ.get('YOUTUBE_COOKIES')
    return cookie_content if cookie_content else None

def create_cookie_file_from_env(cookie_file='utils/cookies.txt'):
    """
    Create cookies.txt from environment variable if it doesn't exist
    """
    cookie_path = Path(cookie_file)
    
    # If file already exists, use it
    if cookie_path.exists():
        return True
    
    # Try to create from environment variable
    cookie_content = get_cookies_from_env()
    if cookie_content:
        try:
            # Create directory if it doesn't exist
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write cookie content
            with open(cookie_path, 'w', encoding='utf-8') as f:
                f.write(cookie_content)
            
            return True
        except Exception as e:
            return False
    
    return False

class CookieManager:
    """Manages cookies from environment variable or file"""
    
    def __init__(self, cookie_file='utils/cookies.txt'):
        self.cookie_file = Path(cookie_file)
        self.cookie_jar = None
        self.session = None
        
    def load_cookies(self):
        """Load cookies from environment variable or file"""
        try:
            # First try to create from environment variable
            create_cookie_file_from_env(str(self.cookie_file))
            
            if not self.cookie_file.exists():
                return False
            
            self.cookie_jar = MozillaCookieJar(str(self.cookie_file))
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
            
            return True
            
        except Exception as e:
            return False
    
    def create_session(self):
        """Create a requests session with loaded cookies"""
        self.session = requests.Session()
        if self.cookie_jar:
            self.session.cookies = self.cookie_jar
        return self.session
    
    def get_session(self):
        """Get or create session with cookies"""
        if self.session is None:
            self.load_cookies()
            self.create_session()
        return self.session

# ======================================================
# VIDEO ID EXTRACTION
# ======================================================
def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if not url:
        return None
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

# ======================================================
# PROXY MANAGEMENT - USING ENVIRONMENT VARIABLES
# ======================================================
def load_proxies_from_env():
    """
    Load proxy list from environment variable
    Format: PROXY_LIST=ip:port:user:pass,ip:port:user:pass,ip:port:user:pass
    """
    proxy_env = os.environ.get('PROXY_LIST', '')
    
    if not proxy_env:
        return []
    
    # Split by comma and strip whitespace
    proxy_strings = [p.strip() for p in proxy_env.split(',') if p.strip()]
    return proxy_strings

def format_proxy(proxy_string):
    """
    Convert proxy string from 'ip:port:username:password' format
    to dictionary format required by requests library
    """
    parts = proxy_string.split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        proxy_url = f"http://{username}:{password}@{ip}:{port}"
        proxy_dict = {
            'http': proxy_url,
            'https': proxy_url
        }
        return proxy_dict
    
    return None

def get_random_proxy():
    """Get a random proxy from environment variable list"""
    proxy_list = load_proxies_from_env()
    
    if not proxy_list:
        return None
    
    proxy_string = random.choice(proxy_list)
    return format_proxy(proxy_string)

# ======================================================
# FETCH TRANSCRIPT WITH COOKIES
# ======================================================



def api_transcript(video_id: str, api_token: str) -> dict:
    """
    Fetch transcript from YouTube Transcript API.
    
    Args:
        video_id (str): YouTube video ID (e.g., 'jNQXAC9IVRw')
        api_token (str): Your API token for authentication
    
    Returns:
        dict: {
            'success': True/False,
            'data': <transcript data if success>,
            'error': <error message if failed>
        }
    """
    url = "https://www.youtube-transcript.io/api/transcripts"
    headers = {
        "Authorization": f"Basic {api_token}",
        "Content-Type": "application/json"
    }
    payload = {"ids": [video_id]}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)

        # Handle common HTTP errors
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "data": data
            }

        elif response.status_code == 401:
            return {"success": False, "error": "Unauthorized – check your API token."}
        elif response.status_code == 404:
            return {"success": False, "error": "Transcript not found for this video ID."}
        else:
            return {
                "success": False,
                "error": f"API returned status {response.status_code}: {response.text}"
            }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out."}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def get_transcript(video_id, language=None, use_proxy=True, proxy_string=None, 
                   max_retries=3, cookie_file='utils/cookies.txt', use_cookies=True):
    """
    Fetches transcript with auto language detection, proxy support, and cookies
    
    Args:
        video_id: YouTube video ID
        language: Language code (e.g., 'en', 'es'). If None, auto-detects
        use_proxy: Whether to use proxy (default: True)
        proxy_string: Specific proxy to use (format: ip:port:username:password)
        max_retries: Maximum number of retries with different proxies
        cookie_file: Path to Netscape format cookie file (default: 'utils/cookies.txt')
        use_cookies: Whether to use cookies (default: True)
    
    Returns:
        Dictionary with transcript data or error information
    """
    # Initialize cookie manager if needed
    cookie_manager = None
    if use_cookies:
        cookie_manager = CookieManager(cookie_file)
        cookie_manager.load_cookies()
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Setup proxy configuration
            proxies = None
            if use_proxy:
                if proxy_string and attempt == 0:
                    proxies = format_proxy(proxy_string)
                else:
                    proxies = get_random_proxy()
            
            # Patch requests.get to use proxy and cookies
            original_get = requests.get
            
            def proxied_get(url, **kwargs):
                if proxies:
                    kwargs['proxies'] = proxies
                    kwargs['timeout'] = 10
                
                # Add cookies if available
                if use_cookies and cookie_manager and cookie_manager.cookie_jar:
                    session = cookie_manager.get_session()
                    return session.get(url, **kwargs)
                
                return original_get(url, **kwargs)
            
            # Monkey patch requests.get
            with patch('requests.get', side_effect=proxied_get):
                api = YouTubeTranscriptApi()
                
                # If language is specified, try that first
                if language and language != 'auto':
                    try:
                        transcript_list = api.list(video_id)
                        transcript = transcript_list.find_transcript([language])
                        result = transcript.fetch()
                        
                        # Extract data from FetchedTranscriptSnippet objects
                        transcript_data = [
                            {
                                'text': snippet.text,
                                'start': snippet.start,
                                'duration': snippet.duration
                            }
                            for snippet in result.snippets
                        ]
                        
                        return {
                            'success': True,
                            'transcript': transcript_data,
                            'language': result.language_code,
                            'language_name': result.language,
                            'proxy_used': proxies is not None,
                            'cookies_used': use_cookies and cookie_manager is not None,
                            'attempt': attempt + 1
                        }
                    except NoTranscriptFound:
                        if attempt < max_retries - 1 and use_proxy:
                            continue
                        pass  # Fall through to auto-detection
                
                # Auto-detect: Try English first, then any available language
                transcript_list = api.list(video_id)
                
                # Try English first
                try:
                    transcript = transcript_list.find_transcript(['en'])
                except NoTranscriptFound:
                    # Get first available transcript
                    available_transcripts = list(transcript_list)
                    if available_transcripts:
                        transcript = available_transcripts[0]
                    else:
                        raise NoTranscriptFound(video_id, [], transcript_list)
                
                result = transcript.fetch()
                
                # Extract data from FetchedTranscriptSnippet objects
                transcript_data = [
                    {
                        'text': snippet.text,
                        'start': snippet.start,
                        'duration': snippet.duration
                    }
                    for snippet in result.snippets
                ]
                
                return {
                    'success': True,
                    'transcript': transcript_data,
                    'language': result.language_code,
                    'language_name': result.language,
                    'auto_detected': True,
                    'proxy_used': proxies is not None,
                    'cookies_used': use_cookies and cookie_manager is not None,
                    'attempt': attempt + 1
                }
        
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            # These are non-retryable errors
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        except Exception as e:
            last_error = e
            
            if attempt < max_retries - 1 and use_proxy:
                continue
            
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'UnexpectedError'
            }
    
    # If all retries failed
    return {
        'success': False,
        'error': f'All {max_retries} attempts failed. Last error: {str(last_error)}',
        'error_type': 'MaxRetriesExceeded'
    }

# ======================================================
# LANGUAGE LIST - WITHOUT PROXY OR COOKIES
# ======================================================
def get_available_languages(video_id):
    """
    Get available transcript languages (no proxy or cookies needed)
    This is a simple API call that doesn't require authentication
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        languages = []
        for transcript in transcript_list:
            languages.append({
                'code': transcript.language_code,
                'name': transcript.language,
                'is_generated': transcript.is_generated,
                'is_translatable': transcript.is_translatable
            })
        
        return {
            'success': True,
            'languages': languages
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error fetching languages: {str(e)}'
        }

# ======================================================
# FORMATTING
# ======================================================
def format_timestamp(seconds):
    """Format seconds to [MM:SS] format"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"

def format_transcript_with_timestamps(transcript_data):
    """Format transcript with timestamps"""
    formatted_lines = []
    for entry in transcript_data:
        timestamp = format_timestamp(entry['start'])
        text = entry['text'].strip()
        formatted_lines.append(f"{timestamp} {text}")
    return '\n'.join(formatted_lines)

def format_transcript_plain(transcript_data):
    """Format transcript as plain text"""
    return ' '.join([entry['text'].strip() for entry in transcript_data])