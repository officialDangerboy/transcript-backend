import re
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import VideoUnavailable

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
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        try:
            transcript = transcript_list.find_transcript([language])
        except:
            transcript = transcript_list.find_generated_transcript(['en'])
        
        transcript_data = transcript.fetch()
        
        return {
            'success': True,
            'transcript': transcript_data,
            'language': transcript.language_code
        }
    
    except TranscriptsDisabled:
        return {
            'success': False,
            'error': 'Transcripts are disabled for this video'
        }
    except NoTranscriptFound:
        return {
            'success': False,
            'error': 'No transcript found for this video'
        }
    except VideoUnavailable:
        return {
            'success': False,
            'error': 'Video is unavailable or private'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error fetching transcript: {str(e)}'
        }

def get_available_languages(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
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
