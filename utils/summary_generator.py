"""
Railway-Optimized AI Summary Generator
Uses Hugging Face Inference API (FREE) - No local models needed!
Get your free token at: https://huggingface.co/settings/tokens
"""

import os
import re
import requests
import time
from typing import Dict

# ======================================================
# HELPER FUNCTIONS
# ======================================================
def clean_text(text: str) -> str:
    """Clean transcript text"""
    text = re.sub(r'\[.*?\]', '', text)  # Remove timestamps
    text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
    text = text.strip()
    return text

# ======================================================
# MAIN SUMMARIZATION FUNCTION
# ======================================================
def generate_summary(transcript_text: str, length='medium') -> Dict:
    
    # Get API token from environment
    api_token = os.environ.get('HF_API_TOKEN')
    
    if not api_token:
        return {
            'success': False,
            'error': 'HF_API_TOKEN not set. Get free token from https://huggingface.co/settings/tokens'
        }
    
    try:
        # Clean the input text
        cleaned_text = clean_text(transcript_text)
        
        if not cleaned_text or len(cleaned_text) < 50:
            return {
                'success': False,
                'error': 'Text too short to summarize'
            }
        
        # Use BART model - it's free on HF Inference API
        model_id = "facebook/bart-large-cnn"
        api_url = f"https://router.huggingface.co/hf-inference/models/${model_id}"
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        # Configure length parameters based on user preference
        length_configs = {
            'short': {
                'max_length': 130,
                'min_length': 30,
                'chunk_size': 800
            },
            'medium': {
                'max_length': 250,
                'min_length': 100,
                'chunk_size': 1000
            },
            'detailed': {
                'max_length': 400,
                'min_length': 200,
                'chunk_size': 1200
            }
        }
        
        config = length_configs.get(length, length_configs['medium'])
        
        # Split text into chunks (BART has ~1024 token limit)
        words = cleaned_text.split()
        chunk_size = config['chunk_size']
        chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        
        summaries = []
        
        for chunk_idx, chunk in enumerate(chunks):
            if len(chunk.split()) < 40:  # Skip tiny chunks
                continue
            
            # Prepare payload
            payload = {
                "inputs": chunk,
                "parameters": {
                    "max_length": config['max_length'],
                    "min_length": config['min_length'],
                    "do_sample": False,
                    "early_stopping": True
                }
            }
            
            # Try up to 3 times (for model loading)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        api_url,
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Extract summary text
                        if isinstance(result, list) and len(result) > 0:
                            summary_text = result[0].get('summary_text', '')
                            if summary_text:
                                summaries.append(summary_text)
                        break
                        
                    elif response.status_code == 503:
                        # Model is loading, wait and retry
                        if attempt < max_retries - 1:
                            time.sleep(3)
                            continue
                        else:
                            raise Exception("Model loading timeout. Please try again in a moment.")
                    
                    elif response.status_code == 429:
                        # Rate limited
                        raise Exception("Rate limit reached. Please try again in a minute.")
                    
                    else:
                        error_msg = response.json().get('error', response.text)
                        raise Exception(f"API error: {error_msg}")
                
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        raise Exception("Request timeout. Please try again.")
                
                except requests.exceptions.RequestException as e:
                    raise Exception(f"Network error: {str(e)}")
        
        # Combine all chunk summaries
        if not summaries:
            return {
                'success': False,
                'error': 'Failed to generate summary. Please try again.'
            }
        
        final_summary = ' '.join(summaries)
        
        # Calculate metadata
        word_count = len(final_summary.split())
        reading_time = max(1, word_count // 200)  # Assuming 200 words per minute
        
        return {
            'success': True,
            'summary': final_summary,
            'word_count': word_count,
            'reading_time': reading_time,
            'length': length,
            'method': 'huggingface_api'
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error generating summary: {str(e)}'
        }