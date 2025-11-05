from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import re

def clean_text(text):
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def generate_summary(transcript_text, length='medium'):
    try:
        cleaned_text = clean_text(transcript_text)
        
        if not cleaned_text:
            return {
                'success': False,
                'error': 'No text available to summarize'
            }
        
        sentence_counts = {
            'short': 5,
            'medium': 10,
            'detailed': 20
        }
        
        sentence_count = sentence_counts.get(length, 10)
        
        parser = PlaintextParser.from_string(cleaned_text, Tokenizer("english"))
        stemmer = Stemmer("english")
        summarizer = LexRankSummarizer(stemmer)
        summarizer.stop_words = get_stop_words("english")
        
        summary_sentences = summarizer(parser.document, sentence_count)
        
        summary_text = ' '.join([str(sentence) for sentence in summary_sentences])
        
        word_count = len(summary_text.split())
        
        reading_time = max(1, word_count // 200)
        
        return {
            'success': True,
            'summary': summary_text,
            'word_count': word_count,
            'reading_time': reading_time,
            'length': length
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error generating summary: {str(e)}'
        }
