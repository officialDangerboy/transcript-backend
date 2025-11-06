import re
import random
import logging
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
# LOGGING SETUP
# ======================================================
def setup_logger(name='yt_transcript', level=logging.DEBUG, log_file=None):
    """
    Setup logger with console and optional file output
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    return logger

# Initialize default logger
logger = setup_logger()

# ======================================================
# COOKIE MANAGEMENT WITH ENVIRONMENT VARIABLE SUPPORT
# ======================================================
def ensure_cookies_from_env(cookie_file='utils/cookies.txt'):
    """
    Create cookies.txt from environment variable if it doesn't exist
    This is useful for Railway deployment where files aren't committed to git
    """
    cookie_path = Path(cookie_file)
    
    # If file already exists, use it
    if cookie_path.exists():
        logger.info(f"Cookie file found at: {cookie_path}")
        return True
    
    # Try to create from environment variable
    cookie_content = os.environ.get('YOUTUBE_COOKIES_CONTENT')
    if cookie_content:
        logger.info("Creating cookies.txt from environment variable")
        try:
            # Create directory if it doesn't exist
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write cookie content
            with open(cookie_path, 'w', encoding='utf-8') as f:
                f.write(cookie_content)
            
            logger.info(f"✓ Successfully created cookies.txt at: {cookie_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create cookies.txt: {str(e)}")
            return False
    
    logger.warning("No cookie file found and no YOUTUBE_COOKIES_CONTENT environment variable set")
    return False

class CookieManager:
    """Manages cookies from Netscape format cookie file"""
    
    def __init__(self, cookie_file='utils/cookies.txt'):
        self.cookie_file = Path(cookie_file)
        self.cookie_jar = None
        self.session = None
        logger.info(f"Initializing CookieManager with file: {self.cookie_file}")
        
    def load_cookies(self):
        """Load cookies from Netscape format file"""
        try:
            # First ensure cookies exist (from file or env var)
            ensure_cookies_from_env(str(self.cookie_file))
            
            if not self.cookie_file.exists():
                logger.warning(f"Cookie file not found: {self.cookie_file}")
                return False
            
            self.cookie_jar = MozillaCookieJar(str(self.cookie_file))
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
            
            cookie_count = len(self.cookie_jar)
            logger.info(f"Successfully loaded {cookie_count} cookies from {self.cookie_file}")
            
            # Log cookie details in debug mode
            for cookie in self.cookie_jar:
                logger.debug(f"Cookie: {cookie.name} | Domain: {cookie.domain} | Expires: {cookie.expires}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}", exc_info=True)
            return False
    
    def create_session(self):
        """Create a requests session with loaded cookies"""
        self.session = requests.Session()
        if self.cookie_jar:
            self.session.cookies = self.cookie_jar
            logger.info("Created session with cookies")
        else:
            logger.warning("Creating session without cookies (no cookies loaded)")
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
    logger.debug(f"Extracting video ID from: {url}")
    
    if not url:
        logger.warning("Empty URL provided")
        return None
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            logger.info(f"Extracted video ID: {video_id}")
            return video_id
    
    logger.error(f"Could not extract video ID from: {url}")
    return None

# ======================================================
# PROXY MANAGEMENT
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
    logger.debug(f"Formatting proxy: {proxy_string}")
    
    parts = proxy_string.split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        proxy_url = f"http://{username}:{password}@{ip}:{port}"
        proxy_dict = {
            'http': proxy_url,
            'https': proxy_url
        }
        logger.debug(f"Formatted proxy: {ip}:{port}")
        return proxy_dict
    
    logger.warning(f"Invalid proxy format: {proxy_string}")
    return None

def get_random_proxy():
    """Get a random proxy from the list"""
    proxy_string = random.choice(PROXY_LIST)
    logger.debug(f"Selected random proxy from list")
    return format_proxy(proxy_string)

# ======================================================
# FETCH TRANSCRIPT WITH COOKIES
# ======================================================
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
    logger.info(f"Starting transcript fetch for video: {video_id}")
    logger.info(f"Settings - Language: {language}, Proxy: {use_proxy}, Cookies: {use_cookies}")
    
    # Initialize cookie manager if needed
    cookie_manager = None
    if use_cookies:
        cookie_manager = CookieManager(cookie_file)
        cookies_loaded = cookie_manager.load_cookies()
        if not cookies_loaded:
            logger.warning("Proceeding without cookies")
    
    last_error = None
    
    for attempt in range(max_retries):
        logger.info(f"=== Attempt {attempt + 1}/{max_retries} ===")
        
        try:
            # Setup proxy configuration
            proxies = None
            if use_proxy:
                if proxy_string and attempt == 0:
                    proxies = format_proxy(proxy_string)
                    logger.info(f"Using specified proxy")
                else:
                    proxies = get_random_proxy()
                    logger.info(f"Using random proxy")
                
                if proxies:
                    proxy_display = list(proxies.values())[0].split('@')[1] if '@' in list(proxies.values())[0] else 'configured'
                    logger.info(f"Proxy configured: {proxy_display}")
            
            # Patch requests.get to use proxy and cookies
            original_get = requests.get
            
            def proxied_get(url, **kwargs):
                logger.debug(f"Making request to: {url}")
                
                if proxies:
                    kwargs['proxies'] = proxies
                    kwargs['timeout'] = 10
                    logger.debug("Applied proxy to request")
                
                # Add cookies if available
                if use_cookies and cookie_manager and cookie_manager.cookie_jar:
                    session = cookie_manager.get_session()
                    logger.debug(f"Applied {len(cookie_manager.cookie_jar)} cookies to request")
                    return session.get(url, **kwargs)
                
                return original_get(url, **kwargs)
            
            # Monkey patch requests.get
            with patch('requests.get', side_effect=proxied_get):
                api = YouTubeTranscriptApi()
                
                # If language is specified, try that first
                if language and language != 'auto':
                    logger.info(f"Attempting to fetch transcript in language: {language}")
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
                        
                        logger.info(f"Successfully fetched transcript: {len(transcript_data)} segments")
                        logger.info(f"Language: {result.language_code} ({result.language})")
                        
                        return {
                            'success': True,
                            'transcript': transcript_data,
                            'language': result.language_code,
                            'language_name': result.language,
                            'proxy_used': proxies is not None,
                            'cookies_used': use_cookies and cookie_manager is not None,
                            'attempt': attempt + 1
                        }
                    except NoTranscriptFound as e:
                        logger.warning(f"No transcript found for language: {language}")
                        if attempt < max_retries - 1 and use_proxy:
                            continue
                        pass  # Fall through to auto-detection
                
                # Auto-detect: Try English first, then any available language
                logger.info("Auto-detecting transcript language")
                transcript_list = api.list(video_id)
                
                # Try English first
                try:
                    logger.debug("Trying English transcript")
                    transcript = transcript_list.find_transcript(['en'])
                    logger.info("Found English transcript")
                except NoTranscriptFound:
                    logger.debug("English transcript not found, trying any available language")
                    # Get first available transcript
                    available_transcripts = list(transcript_list)
                    if available_transcripts:
                        transcript = available_transcripts[0]
                        logger.info(f"Found transcript in: {transcript.language}")
                    else:
                        logger.error("No transcripts available")
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
                
                logger.info(f"Successfully fetched transcript: {len(transcript_data)} segments")
                logger.info(f"Language: {result.language_code} ({result.language})")
                
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
            logger.error(f"Non-retryable error: {type(e).__name__} - {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        except Exception as e:
            last_error = e
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}", exc_info=True)
            
            if attempt < max_retries - 1 and use_proxy:
                logger.info("Retrying with different proxy...")
                continue
            
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'UnexpectedError'
            }
    
    # If all retries failed
    logger.error(f"All {max_retries} attempts failed")
    return {
        'success': False,
        'error': f'All {max_retries} attempts failed. Last error: {str(last_error)}',
        'error_type': 'MaxRetriesExceeded'
    }

# ======================================================
# LANGUAGE LIST
# ======================================================
def get_available_languages(video_id, use_proxy=True, cookie_file='utils/cookies.txt', use_cookies=True):
    """Get available transcript languages with cookie support"""
    logger.info(f"Fetching available languages for video: {video_id}")
    
    try:
        # Initialize cookie manager if needed
        cookie_manager = None
        if use_cookies:
            cookie_manager = CookieManager(cookie_file)
            cookie_manager.load_cookies()
        
        proxies = None
        if use_proxy:
            proxies = get_random_proxy()
            if proxies:
                proxy_display = list(proxies.values())[0].split('@')[1] if '@' in list(proxies.values())[0] else 'configured'
                logger.info(f"Using proxy: {proxy_display}")
        
        # Patch requests.get to use proxy and cookies
        original_get = requests.get
        
        def proxied_get(url, **kwargs):
            if proxies:
                kwargs['proxies'] = proxies
                kwargs['timeout'] = 10
            
            # Add cookies if available
            if use_cookies and cookie_manager and cookie_manager.cookie_jar:
                session = cookie_manager.get_session()
                logger.debug(f"Using cookies for language list request")
                return session.get(url, **kwargs)
            
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
            
            logger.info(f"Found {len(languages)} available languages")
            for lang in languages:
                logger.debug(f"  - {lang['code']}: {lang['name']} (Generated: {lang['is_generated']})")
            
            return {
                'success': True,
                'languages': languages
            }
    
    except Exception as e:
        logger.error(f"Error fetching languages: {str(e)}", exc_info=True)
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
    logger.debug(f"Formatting {len(transcript_data)} transcript segments with timestamps")
    formatted_lines = []
    for entry in transcript_data:
        timestamp = format_timestamp(entry['start'])
        text = entry['text'].strip()
        formatted_lines.append(f"{timestamp} {text}")
    return '\n'.join(formatted_lines)

def format_transcript_plain(transcript_data):
    """Format transcript as plain text"""
    logger.debug(f"Formatting {len(transcript_data)} transcript segments as plain text")
    return ' '.join([entry['text'].strip() for entry in transcript_data])