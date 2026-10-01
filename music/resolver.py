import yt_dlp
import asyncio
from ytmusicapi import YTMusic
from .track import Track

class Resolver:
    def __init__(self):
        self.ytdl_format_options = {
            'format': 'bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }
        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_format_options)
        self.ytmusic = YTMusic()

    async def search(self, query: str, requester_id: int) -> list[Track]:
        loop = asyncio.get_event_loop()
        
        # Spotify playlist/track extractor
        if "spotify.com" in query:
            import urllib.request, re, json
            try:
                embed_url = query.replace("open.spotify.com/", "open.spotify.com/embed/")
                req = urllib.request.Request(embed_url, headers={'User-Agent': 'Mozilla/5.0'})
                html = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req).read().decode('utf-8', errors='ignore'))
                match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
                if match:
                    data = json.loads(match.group(1))
                    entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                    
                    if 'trackList' in entity:
                        tracks = []
                        for t in entity['trackList']:
                            title = t.get('title', '')
                            artist = t.get('subtitle', '')
                            tracks.append(Track(
                                title=title,
                                url=f"{title} {artist}".strip(),
                                source_url="",
                                duration=0,
                                requester=requester_id,
                                thumbnail="",
                                artist=artist,
                                video_id=""
                            ))
                        if tracks:
                            return tracks
                            
                    elif entity.get('type') == 'track':
                        title = entity.get('name', entity.get('title', ''))
                        artist = entity.get('subtitle', '')
                        query = f"{title} {artist}".strip()
            except Exception as e:
                print(f"Spotify extraction error: {e}")
                
        # Apple Music converter (fallback to title)
        elif "apple.com" in query:
            import urllib.request, re
            try:
                req = urllib.request.Request(query, headers={'User-Agent': 'Mozilla/5.0'})
                html = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req).read().decode('utf-8', errors='ignore'))
                match = re.search(r'<title>(.*?)</title>', html)
                if match:
                    title = match.group(1).replace(' - song and lyrics by', '').replace(' | Apple Music', '').strip()
                    if title:
                        query = title
            except Exception as e:
                print(f"Apple Music extraction error: {e}")

        # If it's not a URL, search YT Music first
        if not query.startswith('http'):
            search_results = await loop.run_in_executor(None, lambda: self.ytmusic.search(query))
            for res in search_results:
                if 'videoId' in res and res['videoId']:
                    query = f"https://music.youtube.com/watch?v={res['videoId']}"
                    break

        # Temporary options for playlist flattening
        opts = dict(self.ytdl_format_options)
        opts['noplaylist'] = False
        opts['extract_flat'] = 'in_playlist'
        temp_ytdl = yt_dlp.YoutubeDL(opts)
        
        data = await loop.run_in_executor(None, lambda: temp_ytdl.extract_info(query, download=False))
        
        tracks = []
        if 'entries' in data:
            for entry in data['entries']:
                if not entry:
                    continue
                tracks.append(Track(
                    title=entry.get('title', 'Unknown'),
                    url=entry.get('webpage_url', entry.get('url', query)),
                    source_url="", # Will be resolved when playing
                    duration=entry.get('duration', 0) or 0,
                    requester=requester_id,
                    thumbnail=entry.get('thumbnail', ''),
                    artist=entry.get('uploader', 'Unknown'),
                    video_id=entry.get('id', '')
                ))
        else:
            tracks.append(Track(
                title=data.get('title', 'Unknown'),
                url=data.get('webpage_url', query),
                source_url=data.get('url', ''),
                duration=data.get('duration', 0) or 0,
                requester=requester_id,
                thumbnail=data.get('thumbnail', ''),
                artist=data.get('uploader', 'Unknown'),
                video_id=data.get('id', '')
            ))

        return tracks

    async def get_autoplay_tracks(self, video_id: str, requester_id: int, history_ids: list, count: int = 5) -> list[Track]:
        loop = asyncio.get_event_loop()
        try:
            watch_playlist = await loop.run_in_executor(None, lambda: self.ytmusic.get_watch_playlist(videoId=video_id, radio=True, limit=25))
            tracks = []
            if 'tracks' in watch_playlist:
                for track_data in watch_playlist['tracks']:
                    if track_data['videoId'] not in history_ids and track_data['videoId'] != video_id:
                        title = track_data.get('title', 'Unknown')
                        artist = ", ".join([a['name'] for a in track_data.get('artists', [])])
                        thumbnails = track_data.get('thumbnails', [])
                        thumb = thumbnails[-1]['url'] if thumbnails else ''
                        duration_str = track_data.get('length', '0:00')
                        
                        parts = duration_str.split(':')
                        try:
                            if len(parts) == 2:
                                dur = int(parts[0])*60 + int(parts[1])
                            elif len(parts) == 3:
                                dur = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
                            else:
                                dur = 0
                        except:
                            dur = 0
                            
                        track = Track(
                            title=title,
                            url=f"https://music.youtube.com/watch?v={track_data['videoId']}",
                            source_url="",
                            duration=dur,
                            requester=requester_id,
                            thumbnail=thumb,
                            artist=artist,
                            video_id=track_data['videoId']
                        )
                        tracks.append(track)
                        history_ids.append(track_data['videoId'])
                    if len(tracks) >= count:
                        break
            return tracks
        except Exception as e:
            print(f"Autoplay fetch error: {e}")
        return []
