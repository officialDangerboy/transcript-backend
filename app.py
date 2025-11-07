from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils.transcript_handler import (
    extract_video_id, get_transcript, get_available_languages,
    format_transcript_with_timestamps, format_transcript_plain,api_transcript
)
from utils.summary_generator import generate_summary
from utils.video_info import get_video_info
import time
import os

app = Flask(__name__)

# CORS configuration
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint for Railway"""
    return jsonify({'status': 'healthy', 'service': 'youtube-transcript-api'}), 200




@app.route('/api/transcript/byapi', methods=['POST'])
def get_transcript_by_api():
    """
    Fetch transcript using the youtube-transcript.io API.
    """
    try:
        data = request.json or {}
        video_id = data.get("video_id")
        url = data.get("url", "")
        api_token = os.getenv("YT_TRANSCRIPT_API_TOKEN", "690472d06a281e43da326a2f")  # you can store in env

        # Extract video_id from URL if not provided
        if not video_id and url:
            import re
            match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
            video_id = match.group(1) if match else None

        if not video_id:
            return jsonify({
                "success": False,
                "error": "Please provide a valid video_id or YouTube URL"
            }), 400

        # Fetch transcript via API
        result = api_transcript(video_id, api_token)

        if not result["success"]:
            return jsonify(result), 400

        # ✅ Fix: handle proper data structure
        videos_data = result["data"].get("videos", {})
        transcript_data = videos_data.get(video_id, [])

        if not transcript_data:
            return jsonify({
                "success": False,
                "error": "Transcript not found or empty for this video."
            }), 404

        # Join all segments into plain text
        transcript_text = " ".join(seg.get("text", "") for seg in transcript_data)

        return jsonify({
            "success": True,
            "video_id": video_id,
            "transcript_segments": transcript_data,
            "plain_text": transcript_text,
            "word_count": len(transcript_text.split()),
            "char_count": len(transcript_text),
            "source": "youtube-transcript.io API"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

    

@app.route('/api/transcript', methods=['POST'])
def get_transcript_endpoint():
    try:
        data = request.json
        
        video_id = data.get('video_id')
        url = data.get('url', '')
        include_timestamps = data.get('include_timestamps', True)
        language = data.get('language', None)
        
        if not video_id:
            video_id = extract_video_id(url)
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Please provide a valid video_id or YouTube URL'
            }), 400
        
        transcript_result = get_transcript(
            video_id, 
            language,
            use_cookies=True,
            cookie_file=os.getenv('COOKIE_FILE', 'utils/cookies.txt')
        )
        
        if not transcript_result['success']:
            return jsonify(transcript_result), 400
        
        video_info_result = get_video_info(video_id)
        transcript_data = transcript_result['transcript']
        
        if include_timestamps:
            formatted_transcript = format_transcript_with_timestamps(transcript_data)
        else:
            formatted_transcript = format_transcript_plain(transcript_data)
        
        plain_text = format_transcript_plain(transcript_data)
        
        word_count = len(plain_text.split())
        char_count = len(plain_text)
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'transcript': formatted_transcript,
            'plain_text': plain_text,
            'video_info': video_info_result,
            'word_count': word_count,
            'char_count': char_count,
            'language': transcript_result['language'],
            'language_name': transcript_result.get('language_name', ''),
            'auto_detected': transcript_result.get('auto_detected', False)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500

@app.route('/api/summary', methods=['POST'])
def get_summary_endpoint():
    try:
        data = request.json
        
        video_id = data.get('video_id')
        url = data.get('url', '')
        language = data.get('language', 'en')
        length = data.get('length', 'medium')
        
        if not video_id:
            video_id = extract_video_id(url)
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Please provide a valid video_id or YouTube URL'
            }), 400
        
        start_time = time.time()
        
        transcript_result = get_transcript(
            video_id, 
            language,
            use_cookies=True,
            cookie_file=os.getenv('COOKIE_FILE', 'utils/cookies.txt')
        )
        
        if not transcript_result['success']:
            return jsonify(transcript_result), 400
        
        plain_text = format_transcript_plain(transcript_result['transcript'])
        summary_result = generate_summary(plain_text, length)
        
        if not summary_result['success']:
            return jsonify(summary_result), 400
        
        video_info_result = get_video_info(video_id)
        processing_time = round(time.time() - start_time, 2)
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'summary': summary_result['summary'],
            'word_count': summary_result['word_count'],
            'reading_time': summary_result['reading_time'],
            'processing_time': processing_time,
            'video_info': video_info_result,
            'length': summary_result['length']
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500

@app.route('/api/languages', methods=['POST'])
def get_languages_endpoint():
    try:
        data = request.json
        
        video_id = data.get('video_id')
        url = data.get('url', '')
        
        if not video_id:
            video_id = extract_video_id(url)
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Please provide a valid video_id or YouTube URL'
            }), 400
        
        languages_result = get_available_languages(video_id)
        
        if not languages_result['success']:
            return jsonify(languages_result), 400
        
        return jsonify(languages_result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500

@app.after_request
def add_header(response):
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.must_revalidate = True
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)