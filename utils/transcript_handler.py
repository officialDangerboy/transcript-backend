import re
import time
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
from xml.etree.ElementTree import ParseError

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

def get_transcript(video_id, language='en'):
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            api = YouTubeTranscriptApi()
            
            try:
                result = api.fetch(video_id, languages=[language])
            except (NoTranscriptFound, Exception):
                try:
                    result = api.fetch(video_id, languages=['en'])
                except:
                    result = api.fetch(video_id)
            
            transcript_data = [
                {'text': snippet.text, 'start': snippet.start, 'duration': snippet.duration}
                for snippet in result.snippets
            ]
            
            return {
                'success': True,
                'transcript': transcript_data,
                'language': result.language_code
            }
        
        except TranscriptsDisabled:
            return {
                'success': False,
                'error': 'Transcripts are disabled for this video'
            }
        except NoTranscriptFound:
            return {
                'success': False,
                'error': 'No transcript found for this video in the selected language'
            }
        except VideoUnavailable:
            return {
                'success': False,
                'error': 'Video is unavailable or private'
            }
        except ParseError as e:
            if attempt < max_retries - 1:
                print(f"Transcript fetch failed (attempt {attempt + 1}/{max_retries}), retrying...")
                time.sleep(retry_delay)
                continue
            else:
                return {
                    'success': False,
                    'error': 'Unable to fetch transcript. This video may have restrictions or YouTube is temporarily blocking requests. Please try again in a few moments.'
                }
        except Exception as e:
            if "no element found" in str(e).lower() or "parseerror" in str(e).lower():
                if attempt < max_retries - 1:
                    print(f"Transcript fetch failed (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(retry_delay)
                    continue
                else:
                    return {
                        'success': False,
                        'error': 'Unable to fetch transcript. This video may have restrictions or YouTube is temporarily blocking requests. Please try again in a few moments.'
                    }
            import traceback
            error_details = traceback.format_exc()
            print(f"Transcript error for video {video_id}: {error_details}")
            return {
                'success': False,
                'error': f'Error fetching transcript: {str(e)}'
            }
    
    return {
        'success': False,
        'error': 'Failed to fetch transcript after multiple attempts. Please try again later.'
    }

def get_available_languages(video_id):
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        languages = []
        for transcript in transcript_list:
            languages.append({
                'code': transcript.language_code,
                'name': transcript.language,
                'is_generated': transcript.is_generated,
                'is_translatable': getattr(transcript, 'is_translatable', False)
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
