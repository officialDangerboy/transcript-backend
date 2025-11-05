import requests

def get_video_info(video_id):
    try:
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        
        video_title = f"Video {video_id}"
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                video_title = data.get('title', f"Video {video_id}")
        except:
            pass
        
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
