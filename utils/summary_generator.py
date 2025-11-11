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
        os.getenv('GEMINI_KEY_1', 'AIzaSyCW3jBTKqFQvOUAD6D1nXvbDC4kqJ5QrqM'),
        os.getenv('GEMINI_KEY_2', 'AIzaSyCa2F_ZEyZ-j3u0BgU12vm9NRhR7ZHXUBI'),
        os.getenv('GEMINI_KEY_3', 'AIzaSyAj53qP6T87uJPKNHJ6X57m8uN0ytrGfVo'),
    ]
    return random.choice(api_keys)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
TRANSCRIPT_API_URL = "https://vid-smart-sum.vercel.app/api/transcript/fetch"

# ======================================================
# CLEAN & COMPRESS TRANSCRIPT
# ======================================================
def fetch_transcript(video_id: str) -> Dict:
    """
    Fetch transcript from your external API
    """
    try:
        print(f"📡 Calling transcript API for video: {video_id}")
        
        response = requests.post(
            TRANSCRIPT_API_URL,
            headers={'Content-Type': 'application/json'},
            json={'video_id': video_id},
            timeout=30
        )
        
        print(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ Transcript fetched successfully (cached: {data.get('cached')})")
                return {
                    'success': True,
                    'data': data.get('data', {}),
                    'cached': data.get('cached', False)
                }
            else:
                # API returned 200 but success=false
                return {
                    'success': False,
                    'error': data.get('error', 'Unknown error from transcript API')
                }
        
        # Handle non-200 responses
        try:
            error_data = response.json()
            error_msg = error_data.get('error', response.text)
        except:
            error_msg = response.text
        
        print(f"❌ API Error: {response.status_code} - {error_msg}")
        
        return {
            'success': False,
            'error': f'Transcript API returned {response.status_code}: {error_msg}',
            'status_code': response.status_code
        }
    
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout while fetching transcript")
        return {
            'success': False,
            'error': 'Transcript API request timed out (30s)'
        }
    
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection error to transcript API")
        return {
            'success': False,
            'error': 'Could not connect to transcript API'
        }
    
    except Exception as e:
        print(f"💥 Unexpected error: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to fetch transcript: {str(e)}'
        }

# ======================================================
# CLEAN & COMPRESS TRANSCRIPT
# ============================================= =========
# ======================================================
# CLEAN & COMPRESS TRANSCRIPT (IMPROVED)
# ======================================================
def clean_segments(segments: List[Dict]) -> List[Dict]:
    """Clean and normalize segment data"""
    cleaned = []
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text or len(text) < 3:  # Skip empty or too short
            continue
        
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        cleaned.append({
            'text': text,
            'start': round(seg.get('start', 0), 2),
            'end': round(seg.get('start', 0) + seg.get('duration', 0), 2),
            'duration': round(seg.get('duration', 0), 2)
        })
    
    return cleaned


def get_time_based_chunks(segments: List[Dict], start_seconds: float, end_seconds: float) -> List[Dict]:
    """Extract segments within a time range"""
    return [s for s in segments if start_seconds <= s['start'] <= end_seconds]


def compress_transcript_smart(segments: List[Dict]) -> Dict:
    """
    Smart compression: Extract key sections for coherent summary
    - First 30 seconds (introduction)
    - Middle 30 seconds (core content)
    - Last 30 seconds (conclusion)
    - Top segments from each section
    Total: ~25% of original content (keeping 25%, removing 75%)
    """
    if not segments or len(segments) == 0:
        return {'segments': [], 'full_text': '', 'reduction_percent': 0}
    
    total_segments = len(segments)
    video_duration = segments[-1]['end'] if segments else 0
    
    print(f"📹 Video duration: {video_duration:.1f}s, Total segments: {total_segments}")
    
    # === SECTION 1: First 30 seconds (Introduction) ===
    intro_segments = get_time_based_chunks(segments, 0, 30)
    # Keep 30% of intro segments
    intro_keep = max(1, int(len(intro_segments) * 0.30)) if intro_segments else 0
    intro_top = sorted(intro_segments, key=lambda s: len(s['text'].split()), reverse=True)[:intro_keep]
    
    # === SECTION 2: Middle 30 seconds (Core content) ===
    middle_start = (video_duration / 2) - 15  # 15s before middle
    middle_end = (video_duration / 2) + 15    # 15s after middle
    middle_segments = get_time_based_chunks(segments, middle_start, middle_end)
    # Keep 30% of middle segments
    middle_keep = max(1, int(len(middle_segments) * 0.30)) if middle_segments else 0
    middle_top = sorted(middle_segments, key=lambda s: len(s['text'].split()), reverse=True)[:middle_keep]
    
    # === SECTION 3: Last 30 seconds (Conclusion) ===
    outro_start = max(0, video_duration - 30)
    outro_segments = get_time_based_chunks(segments, outro_start, video_duration)
    # Keep 30% of outro segments
    outro_keep = max(1, int(len(outro_segments) * 0.30)) if outro_segments else 0
    outro_top = sorted(outro_segments, key=lambda s: len(s['text'].split()), reverse=True)[:outro_keep]
    
    # === SECTION 4: Additional key segments from entire video ===
    # Get top 20% most information-dense segments from everywhere
    all_dense = sorted(segments, key=lambda s: len(s['text'].split()), reverse=True)
    additional_keep = int(total_segments * 0.20)  # 20% additional
    additional_segments = all_dense[:additional_keep]
    
    # === COMBINE & DEDUPLICATE ===
    combined = intro_top + middle_top + outro_top + additional_segments
    # Remove duplicates by segment start time
    seen_times = set()
    unique_segments = []
    for seg in combined:
        if seg['start'] not in seen_times:
            seen_times.add(seg['start'])
            unique_segments.append(seg)
    
    # Sort by timestamp to maintain flow
    compressed = sorted(unique_segments, key=lambda s: s['start'])
    
    # Build full text with smooth transitions
    text_parts = []
    for i, seg in enumerate(compressed):
        text_parts.append(seg['text'])
        # Add transition marker if there's a big time gap (>10s)
        if i < len(compressed) - 1:
            time_gap = compressed[i + 1]['start'] - seg['end']
            if time_gap > 10:
                text_parts.append('[...]')  # Indicate skipped content
    
    compressed_text = ' '.join(text_parts)
    original_text = ' '.join(s['text'] for s in segments)
    
    reduction = 1 - (len(compressed) / total_segments)
    
    print(f"📊 Compression: {total_segments} → {len(compressed)} segments ({reduction*100:.1f}% reduction)")
    print(f"📝 Text: {len(original_text)} → {len(compressed_text)} chars")
    
    return {
        'segments': compressed,
        'full_text': compressed_text,
        'original_length': len(original_text),
        'compressed_length': len(compressed_text),
        'reduction_percent': round(reduction * 100, 1),
        'sections': {
            'intro': len(intro_top),
            'middle': len(middle_top),
            'outro': len(outro_top),
            'additional': len(additional_segments)
        }
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
            "maxOutputTokens": 2500,
        }
    }
    
    for attempt in range(3):
        try:
            print(f"🤖 Calling Gemini API (attempt {attempt + 1}/3)...")
            
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60  # Increased timeout
            )
            
            print(f"📥 Gemini Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle response structure
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    content = candidate.get('content', {})
                    parts = content.get('parts', [])
                    
                    if parts and 'text' in parts[0]:
                        response_text = parts[0]['text'].strip()
                        print(f"✅ Got response: {len(response_text)} characters")
                        return {
                            'success': True,
                            'text': response_text
                        }
                
                # If we reach here, response format was unexpected
                print(f"⚠️ Unexpected response format: {result}")
                return {
                    'success': False,
                    'error': 'Unexpected response format from Gemini',
                    'details': str(result)
                }
            
            elif response.status_code == 429:
                print(f"⏳ Rate limited, trying another key...")
                if attempt < 2:
                    api_key = get_random_gemini_key()
                    url = f"{GEMINI_API_URL}?key={api_key}"
                    time.sleep(2)
                    continue
                return {
                    'success': False,
                    'error': 'Rate limit exceeded on all API keys'
                }
            
            elif response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Bad request')
                print(f"❌ Bad request: {error_msg}")
                return {
                    'success': False,
                    'error': f'Gemini API error: {error_msg}'
                }
            
            else:
                print(f"❌ API error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f'Gemini API error: {response.status_code}'
                }
        
        except requests.exceptions.Timeout:
            print(f"⏱️ Request timeout (attempt {attempt + 1})")
            if attempt < 2:
                time.sleep(2)
                continue
            return {
                'success': False,
                'error': 'Gemini API request timed out'
            }
        
        except Exception as e:
            print(f"💥 Error: {str(e)}")
            if attempt < 2:
                time.sleep(2)
                continue
            return {
                'success': False,
                'error': f'Gemini API call failed: {str(e)}'
            }
    
    return {
        'success': False,
        'error': 'Max retries exceeded'
    }

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
        
        # 3. Compress transcript (smart 25% extraction)
        print(f"🗜️ Compressing transcript...")
        compressed = compress_transcript_smart(cleaned_segments)
        
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