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
import random
import requests

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

def get_random_api_key():
    api_keys = [
        "690472d06a281e43da326a2f",
        "690e00ab070ee63dc66f801e",
        "690e010dbdc762cdc1d1e02c",
        "690e019aa35112c309e743cb",
        "690361176ee0e3ee9607f664",
        "690e253bdc96d99ec19b7790",
        "690e01dfa480fd59b68659ac"  # etc...
    ]
    return random.choice(api_keys)

YOUTUBE_TRANSCRIPT_API = "https://www.youtube-transcript.io/api/transcripts"

@app.route("/api/transcript/byapi", methods=["POST"])
def get_transcript_byapi():
    """
    Fetch transcript & video details using youtube-transcript.io API.
    """
    try:
        data = request.json or {}
        video_id = data.get("video_id")
        language = data.get("language")  # optional
        if not video_id:
            return jsonify({"success": False, "error": "Missing video_id"}), 400

        # Prepare request
        API_KEY = get_random_api_key()
        headers = {
            "Authorization": f"Basic {API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {"ids": [video_id]}

        # Call external API
        response = requests.post(YOUTUBE_TRANSCRIPT_API, headers=headers, json=payload)
        if response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Upstream API returned {response.status_code}",
                "details": response.text
            }), response.status_code

        data_list = response.json()
        if not isinstance(data_list, list) or len(data_list) == 0:
            return jsonify({"success": False, "error": "Unexpected API response"}), 500

        video_data = data_list[0]
        microformat = video_data.get("microformat", {}).get("playerMicroformatRenderer", {})
        tracks = video_data.get("tracks", [])
        selected_track = None

        # Select preferred language
        if language:
            for t in tracks:
                if t.get("language", "").lower() == language.lower():
                    selected_track = t
                    break
        if not selected_track and tracks:
            selected_track = tracks[0]

        transcript_segments = selected_track.get("transcript", []) if selected_track else []
        transcript_text = " ".join(seg.get("text", "") for seg in transcript_segments)

        # Build clean response
        result = {
            "success": True,
            "video_id": video_id,
            "title": microformat.get("title", {}).get("simpleText"),
            "author": video_data.get("author"),
            "channel_id": video_data.get("channelId"),
            "thumbnail": microformat.get("thumbnail", {}).get("thumbnails", [{}])[0].get("url"),
            "description": microformat.get("description", {}).get("simpleText"),
            "language": selected_track.get("language") if selected_track else None,
            "transcript_segments": transcript_segments,
            "plain_text": transcript_text,
            "word_count": len(transcript_text.split()),
            "char_count": len(transcript_text),
            "view_count": microformat.get("viewCount"),
            "publish_date": microformat.get("publishDate"),
            "like_count": microformat.get("likeCount"),
            "source": "youtube-transcript.io"
        }

        return jsonify(result)

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


@app.route('/api/summary/detailed', methods=['POST'])
def get_detailed_summary():
    """Generate DETAILED summary (comprehensive analysis)"""
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'video_id is required'
            }), 400
        
        result = generate_summary(video_id, 'detailed')
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.route('/api/summary/medium', methods=['POST'])
def get_medium_summary():
    """Generate MEDIUM summary (4-6 sentences, detailed points)"""
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'video_id is required'
            }), 400
        
        result = generate_summary(video_id, 'medium')
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    

@app.route('/api/summary/short', methods=['POST'])
def get_short_summary():
    """Generate SHORT summary (2-3 sentences, key points)"""
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'video_id is required'
            }), 400
        
        result = generate_summary(video_id, 'short')
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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