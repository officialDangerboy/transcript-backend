from youtube_transcript_api import YouTubeTranscriptApi

def get_video_info(video_id):
    try:
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            first_transcript = list(transcript_list)[0]
            video_title = f"Video {video_id}"
        except:
            video_title = f"Video {video_id}"
        
        return {
            'success': True,
            'video_id': video_id,
            'title': video_title,
            'thumbnail': thumbnail_url
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error fetching video info: {str(e)}'
        }
