import os
import re
import random
import requests
import time
from typing import Dict, List
from flask import Blueprint, request, jsonify

# Create Blueprint
summary_bp = Blueprint('summary', __name__)

# ======================================================
# GEMINI API CONFIGURATION
# ======================================================
def get_random_gemini_key():
    """Get random Gemini API key from pool"""
    api_keys = [
        os.getenv('GEMINI_KEY_1', 'AIzaSyAV1E3d1JIv3hhpe1dJwG06qVl7OSZz4GE'),
        os.getenv('GEMINI_KEY_2', 'AIzaSyBBttGpLmaR1Vq3gM8z46G6jsNsttV_GyU'),
    ]
    return random.choice(api_keys)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
TRANSCRIPT_API_URL = "https://vid-smart-sum.vercel.app/api/transcript/fetch"

# ======================================================
# FETCH TRANSCRIPT FROM API
# ======================================================
def fetch_transcript(video_id: str) -> Dict:
    """
    Fetch transcript from your external API
    """
    try:
        response = requests.post(
            TRANSCRIPT_API_URL,
            headers={'Content-Type': 'application/json'},
            json={'video_id': video_id},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return {
                    'success': True,
                    'data': data.get('data', {}),
                    'cached': data.get('cached', False)
                }
        
        return {
            'success': False,
            'error': f'API returned status {response.status_code}'
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to fetch transcript: {str(e)}'
        }

# ======================================================
# CLEAN & COMPRESS TRANSCRIPT
# ======================================================
def clean_segments(segments: List[Dict]) -> List[Dict]:
    """
    Clean segment timestamps and text
    """
    cleaned = []
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        cleaned.append({
            'text': text,
            'start': round(seg.get('start', 0), 2),
            'duration': round(seg.get('duration', 0), 2)
        })
    
    return cleaned

def compress_transcript(segments: List[Dict], reduction_target: float = 0.28) -> Dict:
    """
    Compress transcript by 25-30% by removing less important parts
    Strategy: Keep beginning, middle highlights, and end; remove redundant middle
    """
    if not segments:
        return {'segments': [], 'full_text': ''}
    
    total_segments = len(segments)
    
    # Calculate sections
    keep_start = int(total_segments * 0.15)  # Keep first 15%
    keep_end = int(total_segments * 0.15)    # Keep last 15%
    
    # Middle section: keep ~40% of important segments
    middle_start = keep_start
    middle_end = total_segments - keep_end
    middle_segments = segments[middle_start:middle_end]
    
    # Filter middle: keep segments with more words (likely more important)
    middle_important = sorted(
        middle_segments,
        key=lambda s: len(s['text'].split()),
        reverse=True
    )[:int(len(middle_segments) * 0.4)]
    
    # Sort by timestamp to maintain order
    middle_important = sorted(middle_important, key=lambda s: s['start'])
    
    # Combine: start + important middle + end
    compressed = (
        segments[:keep_start] +
        middle_important +
        segments[-keep_end:] if keep_end > 0 else []
    )
    
    # Sort by start time
    compressed = sorted(compressed, key=lambda s: s['start'])
    
    # Calculate compression stats
    original_text = ' '.join(s['text'] for s in segments)
    compressed_text = ' '.join(s['text'] for s in compressed)
    
    reduction = 1 - (len(compressed) / total_segments)
    
    print(f"📊 Compression: {total_segments} → {len(compressed)} segments ({reduction*100:.1f}% reduction)")
    
    return {
        'segments': compressed,
        'full_text': compressed_text,
        'original_length': len(original_text),
        'compressed_length': len(compressed_text),
        'reduction_percent': round(reduction * 100, 1)
    }

# ======================================================
# GEMINI API CALL
# ======================================================
def call_gemini(prompt: str, temperature: float = 0.7) -> Dict:
    """
    Call Gemini API with retry logic
    """
    api_key = get_random_gemini_key()
    url = f"{GEMINI_API_URL}?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": temperature,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 2048,
        }
    }
    
    for attempt in range(3):
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0].get('content', {})
                    parts = content.get('parts', [])
                    if parts and 'text' in parts[0]:
                        return {
                            'success': True,
                            'text': parts[0]['text'].strip()
                        }
            
            elif response.status_code == 429:
                if attempt < 2:
                    api_key = get_random_gemini_key()
                    url = f"{GEMINI_API_URL}?key={api_key}"
                    time.sleep(2)
                    continue
            
            return {'success': False, 'error': f'API error: {response.status_code}'}
        
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return {'success': False, 'error': str(e)}
    
    return {'success': False, 'error': 'Max retries exceeded'}

# ======================================================
# SUMMARY PROMPTS
# ======================================================
def get_summary_prompt(transcript_text: str, video_title: str, summary_type: str) -> str:
    """
    Generate appropriate prompt based on summary type
    """
    
    if summary_type == 'short':
        return f"""Analyze this video transcript and provide a SHORT summary in clean JSON format.

Video Title: {video_title}

Transcript:
{transcript_text}

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "summary": "2-3 sentence overview of the main topic",
  "key_points": [
    "First main point",
    "Second main point",
    "Third main point"
  ],
  "main_topic": "Single sentence describing the core subject",
  "duration_estimate": "X minutes"
}}

Keep it concise and focused on the essentials."""

    elif summary_type == 'medium':
        return f"""Analyze this video transcript and provide a MEDIUM-LENGTH summary in clean JSON format.

Video Title: {video_title}

Transcript:
{transcript_text}

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "summary": "4-6 sentence comprehensive overview",
  "key_points": [
    "First major point with brief explanation",
    "Second major point with brief explanation",
    "Third major point with brief explanation",
    "Fourth major point with brief explanation",
    "Fifth major point with brief explanation"
  ],
  "main_topics": [
    "Topic 1",
    "Topic 2",
    "Topic 3"
  ],
  "key_takeaways": [
    "Important takeaway 1",
    "Important takeaway 2",
    "Important takeaway 3"
  ],
  "target_audience": "Who would benefit from this video",
  "content_type": "Tutorial/Educational/Entertainment/Review/etc"
}}

Provide balanced detail with actionable insights."""

    else:  # detailed
        return f"""Analyze this video transcript and provide a DETAILED summary in clean JSON format.

Video Title: {video_title}

Transcript:
{transcript_text}

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "executive_summary": "2-3 sentence high-level overview",
  "detailed_summary": "8-10 sentence comprehensive explanation covering all major points",
  "key_points": [
    "Detailed explanation of first major point",
    "Detailed explanation of second major point",
    "Detailed explanation of third major point",
    "Detailed explanation of fourth major point",
    "Detailed explanation of fifth major point",
    "Detailed explanation of sixth major point"
  ],
  "main_topics": [
    {{
      "topic": "Topic name",
      "description": "What this topic covers"
    }},
    {{
      "topic": "Topic name",
      "description": "What this topic covers"
    }}
  ],
  "key_takeaways": [
    "Important insight 1",
    "Important insight 2",
    "Important insight 3",
    "Important insight 4"
  ],
  "timestamps": [
    {{
      "time": "0:00-2:30",
      "description": "Introduction and overview"
    }},
    {{
      "time": "2:30-5:00",
      "description": "Main concept explanation"
    }}
  ],
  "target_audience": "Detailed description of who should watch this",
  "prerequisites": "What knowledge is needed to understand this",
  "difficulty_level": "Beginner/Intermediate/Advanced",
  "content_type": "Tutorial/Educational/Entertainment/Review/etc",
  "practical_applications": [
    "How to apply learning 1",
    "How to apply learning 2"
  ]
}}

Provide comprehensive analysis with actionable insights and clear structure."""

# ======================================================
# PARSE JSON FROM GEMINI RESPONSE
# ======================================================
def parse_json_response(text: str) -> Dict:
    """
    Extract and parse JSON from Gemini response
    """
    try:
        # Remove markdown code blocks if present
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Try to find JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            import json
            return json.loads(json_match.group())
        
        return None
    except Exception as e:
        print(f"JSON parse error: {e}")
        return None

# ======================================================
# GENERATE SUMMARY
# ======================================================
def generate_summary(video_id: str, summary_type: str = 'medium') -> Dict:
    """
    Main function to generate summary
    """
    try:
        # 1. Fetch transcript
        print(f"🔍 Fetching transcript for: {video_id}")
        transcript_result = fetch_transcript(video_id)
        
        if not transcript_result['success']:
            return transcript_result
        
        data = transcript_result['data']
        video_title = data.get('video_title', 'Unknown Title')
        segments = data.get('segments', [])
        
        if not segments or len(segments) == 0:
            return {
                'success': False,
                'error': 'No segments found in transcript'
            }
        
        # 2. Clean segments
        print(f"🧹 Cleaning {len(segments)} segments...")
        cleaned_segments = clean_segments(segments)
        
        # 3. Compress transcript (25-30%)
        print(f"🗜️ Compressing transcript...")
        compressed = compress_transcript(cleaned_segments)
        
        # 4. Generate prompt
        prompt = get_summary_prompt(
            compressed['full_text'],
            video_title,
            summary_type
        )
        
        # 5. Call Gemini
        print(f"🤖 Generating {summary_type} summary with Gemini...")
        gemini_result = call_gemini(prompt, temperature=0.7)
        
        if not gemini_result['success']:
            return gemini_result
        
        # 6. Parse JSON response
        parsed_json = parse_json_response(gemini_result['text'])
        
        if not parsed_json:
            return {
                'success': False,
                'error': 'Failed to parse AI response into JSON',
                'raw_response': gemini_result['text']
            }
        
        # 7. Return structured response
        return {
            'success': True,
            'video_id': video_id,
            'video_title': video_title,
            'summary_type': summary_type,
            'cached_transcript': transcript_result.get('cached', False),
            'compression_stats': {
                'original_segments': len(segments),
                'compressed_segments': len(compressed['segments']),
                'reduction_percent': compressed['reduction_percent']
            },
            'summary_data': parsed_json,
            'metadata': {
                'language': data.get('language', 'unknown'),
                'word_count': data.get('word_count', 0),
                'channel_name': data.get('channel_name', 'Unknown')
            }
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Summary generation failed: {str(e)}'
        }