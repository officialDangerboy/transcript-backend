import re
import random
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
import requests
from unittest.mock import patch

# ======================================================
# VIDEO ID EXTRACTION
# ======================================================
def extract_video_id(url):
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
# FETCH TRANSCRIPT WITH AUTO LANGUAGE DETECTION
# ======================================================
PROXY_LIST = [
    "142.111.48.253:7030:demsanuy:5aek3a4qn27i",
    "31.59.20.176:6754:demsanuy:5aek3a4qn27i",
    "23.95.150.145:6114:demsanuy:5aek3a4qn27i",
    "198.23.239.134:6540:demsanuy:5aek3a4qn27i",
    "45.38.107.97:6014:demsanuy:5aek3a4qn27i",
    "107.172.163.27:6543:demsanuy:5aek3a4qn27i",
    "64.137.96.74:6641:demsanuy:5aek3a4qn27i",
    "216.10.27.159:6837:demsanuy:5aek3a4qn27i",
    "142.111.67.146:5611:demsanuy:5aek3a4qn27i",
    "142.147.128.93:6593:demsanuy:5aek3a4qn27i",
]

def format_proxy(proxy_string):
    """
    Convert proxy string from 'ip:port:username:password' format
    to dictionary format required by requests library
    """
    parts = proxy_string.split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        proxy_url = f"http://{username}:{password}@{ip}:{port}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    return None

def get_random_proxy():
    """Get a random proxy from the list"""
    proxy_string = random.choice(PROXY_LIST)
    return format_proxy(proxy_string)

def get_transcript(video_id, language=None, use_proxy=True, proxy_string=None, max_retries=3):
    """
    Fetches transcript with auto language detection and proxy support
    
    Args:
        video_id: YouTube video ID
        language: Language code (e.g., 'en', 'es'). If None, auto-detects
        use_proxy: Whether to use proxy (default: True)
        proxy_string: Specific proxy to use (format: ip:port:username:password)
                     If None, randomly selects from PROXY_LIST
        max_retries: Maximum number of retries with different proxies
    
    Returns:
        Dictionary with transcript data or error information
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Setup proxy configuration
            proxies = None
            if use_proxy:
                if proxy_string and attempt == 0:  # Use specific proxy only on first attempt
                    proxies = format_proxy(proxy_string)
                else:
                    proxies = get_random_proxy()
                
                if proxies:
                    proxy_display = list(proxies.values())[0].split('@')[1] if '@' in list(proxies.values())[0] else 'configured'
                    print(f"Attempt {attempt + 1}: Using proxy: {proxy_display}")
            
            # Patch requests.get to use proxy
            original_get = requests.get
            
            def proxied_get(url, **kwargs):
                if proxies:
                    kwargs['proxies'] = proxies
                    kwargs['timeout'] = 10  # Add timeout
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
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying with different proxy...")
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
# LANGUAGE LIST
# ======================================================
def get_available_languages(video_id, use_proxy=True):
    try:
        proxies = None
        if use_proxy:
            proxies = get_random_proxy()
            if proxies:
                proxy_display = list(proxies.values())[0].split('@')[1] if '@' in list(proxies.values())[0] else 'configured'
                print(f"Fetching languages using proxy: {proxy_display}")
        
        # Patch requests.get to use proxy
        original_get = requests.get
        
        def proxied_get(url, **kwargs):
            if proxies:
                kwargs['proxies'] = proxies
                kwargs['timeout'] = 10
            return original_get(url, **kwargs)
        
        # Monkey patch requests.get
        with patch('requests.get', side_effect=proxied_get):
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
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"

def format_transcript_with_timestamps(transcript_data):
    formatted_lines = []
    for entry in transcript_data:
        timestamp = format_timestamp(entry['start'])
        text = entry['text'].strip()
        formatted_lines.append(f"{timestamp} {text}")
    return '\n'.join(formatted_lines)

def format_transcript_plain(transcript_data):
    return ' '.join([entry['text'].strip() for entry in transcript_data])