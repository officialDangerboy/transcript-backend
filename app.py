from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils.transcript_handler import (
    extract_video_id, get_transcript, get_available_languages,
    format_transcript_with_timestamps, format_transcript_plain
)
from utils.summary_generator import generate_summary
from utils.video_info import get_video_info
import time

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcript', methods=['POST'])
def get_transcript_endpoint():
    try:
        data = request.json
        
        # Accept either 'video_id' or 'url'
        video_id = data.get('video_id')
        url = data.get('url', '')
        include_timestamps = data.get('include_timestamps', True)
        language = data.get('language', None)  # None = auto-detect
        
        # If video_id not provided, try extracting from URL
        if not video_id:
            video_id = extract_video_id(url)
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Please provide a valid video_id or YouTube URL'
            }), 400
        
        # Get transcript with auto language detection
        transcript_result = get_transcript(video_id, language)
        
        if not transcript_result['success']:
            return jsonify(transcript_result), 400
        
        # Get video info
        video_info_result = get_video_info(video_id)
        
        transcript_data = transcript_result['transcript']
        
        # Format transcript
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
        
        # Accept either 'video_id' or 'url'
        video_id = data.get('video_id')
        url = data.get('url', '')
        language = data.get('language', 'en')
        length = data.get('length', 'medium')
        
        # If video_id not provided, try extracting from URL
        if not video_id:
            video_id = extract_video_id(url)
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Please provide a valid video_id or YouTube URL'
            }), 400
        
        start_time = time.time()
        
        transcript_result = get_transcript(video_id, language)
        
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
        
        # Accept either 'video_id' or 'url'
        video_id = data.get('video_id')
        url = data.get('url', '')
        
        # If video_id not provided, try extracting from URL
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

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000, debug=False)