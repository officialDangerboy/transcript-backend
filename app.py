from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils.transcript_handler import (
    extract_video_id, get_transcript, get_available_languages,
    format_transcript_with_timestamps, format_transcript_plain
)
from utils.summary_generator import generate_summary
from utils.video_info import get_video_info
import time
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        
        logger.info(f"Fetching transcript for video: {video_id}")
        
        # Get transcript with cookie support
        transcript_result = get_transcript(
            video_id, 
            language,
            use_cookies=True,
            cookie_file=os.getenv('COOKIE_FILE', 'utils/cookies.txt')
        )
        
        if not transcript_result['success']:
            logger.error(f"Transcript fetch failed: {transcript_result.get('error')}")
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
        
        logger.info(f"Transcript fetched successfully: {word_count} words")
        
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
        logger.error(f"Error in transcript endpoint: {str(e)}", exc_info=True)
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
        
        logger.info(f"Generating summary for video: {video_id}")
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
        
        logger.info(f"Summary generated in {processing_time}s")
        
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
        logger.error(f"Error in summary endpoint: {str(e)}", exc_info=True)
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
        
        languages_result = get_available_languages(
            video_id,
            use_cookies=True,
            cookie_file=os.getenv('COOKIE_FILE', 'utils/cookies.txt')
        )
        
        if not languages_result['success']:
            return jsonify(languages_result), 400
        
        return jsonify(languages_result)
    
    except Exception as e:
        logger.error(f"Error in languages endpoint: {str(e)}", exc_info=True)
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
    logger.error(f"Internal server error: {str(e)}", exc_info=True)
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)