import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from music.manager import GuildMusicManager
from music.resolver import Resolver

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.managers = {}
        self.resolver = Resolver()

    def get_manager(self, guild_id: int):
        if guild_id not in self.managers:
            self.managers[guild_id] = GuildMusicManager(self.bot, guild_id)
        return self.managers[guild_id]

    async def query_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        loop = asyncio.get_event_loop()
        
        # If the input is a URL, parse it for metadata to display in autocomplete
        if current.startswith("http"):
            try:
                display = "URL (Press Enter to load)"
                
                # Spotify Quick Parser
                if "spotify.com" in current:
                    import urllib.request, re, json
                    embed_url = current.replace("open.spotify.com/", "open.spotify.com/embed/")
                    req = urllib.request.Request(embed_url, headers={'User-Agent': 'Mozilla/5.0'})
                    html = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=2).read().decode('utf-8', errors='ignore'))
                    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
                    if match:
                        data = json.loads(match.group(1))
                        entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                        name = entity.get('name', entity.get('title', 'Unknown'))
                        if 'trackList' in entity:
                            display = f"Spotify Playlist: {name} ({len(entity['trackList'])} tracks)"
                        else:
                            display = f"Spotify Track: {name}"
                
                # Apple Music Quick Parser
                elif "apple.com" in current:
                    import urllib.request, re
                    req = urllib.request.Request(current, headers={'User-Agent': 'Mozilla/5.0'})
                    html = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=2).read().decode('utf-8', errors='ignore'))
                    match = re.search(r'<title>(.*?)</title>', html)
                    if match:
                        title = match.group(1).replace(' - song and lyrics by', '').replace(' | Apple Music', '').strip()
                        display = f"Apple Music: {title}"
                
                # YouTube / YT Music fallback
                elif "youtube.com" in current or "youtu.be" in current:
                    import yt_dlp
                    opts = {'quiet': True, 'extract_flat': 'in_playlist', 'noplaylist': False}
                    temp_ytdl = yt_dlp.YoutubeDL(opts)
                    data = await loop.run_in_executor(None, lambda: temp_ytdl.extract_info(current, download=False))
                    if data:
                        title = data.get('title', 'Unknown')
                        if 'entries' in data:
                            display = f"YouTube Playlist: {title} ({len(list(data['entries']))} tracks)"
                        else:
                            display = f"YouTube Video: {title}"

                if len(display) > 100:
                    display = display[:97] + "..."
                return [app_commands.Choice(name=display, value=current)]
            except Exception as e:
                # Fallback to raw url
                display = "URL (Press Enter to load)"
                if len(current) > 100:
                    display = current[:97] + "..."
                return [app_commands.Choice(name=display, value=current)]

        # Regular Text Search
        try:
            results = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: self.resolver.ytmusic.search(current, limit=10)
                ),
                timeout=2.0
            )
            choices = []
            for r in results:
                title = r.get('title', 'Unknown')
                artist = ", ".join([a['name'] for a in r.get('artists', [])])
                video_id = r.get('videoId')
                if video_id:
                    display = f"{title} - {artist}"
                    if len(display) > 100:
                        display = display[:97] + "..."
                    url = f"https://music.youtube.com/watch?v={video_id}"
                    choices.append(app_commands.Choice(name=display, value=url))
            return choices[:10]
        except Exception:
            return []

    @app_commands.command(name="play", description="Play a song from YouTube or elsewhere")
    @app_commands.autocomplete(query=query_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        if not interaction.user.voice:
            return await interaction.followup.send("You need to be in a voice channel to use this command.")
            
        channel = interaction.user.voice.channel
        manager = self.get_manager(interaction.guild_id)
        manager.text_channel = interaction.channel
        
        if not manager.voice_client:
            manager.voice_client = await channel.connect(self_deaf=True)
        elif manager.voice_client.channel != channel:
            await manager.voice_client.move_to(channel)

        try:
            tracks = await self.resolver.search(query, interaction.user.id)
            if not tracks:
                return await interaction.followup.send("Could not find any tracks.")
                
            manager.queue.extend(tracks)
            
            if not manager.voice_client.is_playing() and not manager.voice_client.is_paused():
                manager.play_next()
                if len(tracks) == 1:
                    await interaction.followup.send(f"Now playing: **{tracks[0].title}**")
                else:
                    await interaction.followup.send(f"Started playing a playlist with **{len(tracks)}** tracks!")
            else:
                if len(tracks) == 1:
                    await interaction.followup.send(f"Added to queue: **{tracks[0].title}**")
                else:
                    await interaction.followup.send(f"Added a playlist with **{len(tracks)}** tracks to the queue!")
        except Exception as e:
            await interaction.followup.send(f"An error occurred while trying to play: {str(e)}")

    @app_commands.command(name="stop", description="Stop music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if manager.voice_client:
            manager.reset_state()
            manager.voice_client.stop()
            await manager.voice_client.disconnect()
            manager.voice_client = None
            await interaction.response.send_message("Stopped the music and cleared the queue.")
        else:
            await interaction.response.send_message("I am not connected to a voice channel.")

    @app_commands.command(name="save", description="Save the currently playing song to your playlist")
    async def save(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if not manager.current_track:
            return await interaction.response.send_message("No song is currently playing to save.", ephemeral=True)
            
        from music.db import add_to_playlist
        add_to_playlist(str(interaction.guild_id), str(interaction.user.id), {
            "title": manager.current_track.title,
            "url": manager.current_track.url,
            "duration": manager.current_track.duration,
            "thumbnail": manager.current_track.thumbnail,
            "artist": manager.current_track.artist,
            "video_id": manager.current_track.video_id
        })
        await interaction.response.send_message(f"💾 Saved **{manager.current_track.title}** to your playlist! Use `/myplaylist` to play it.", ephemeral=True)

    @app_commands.command(name="myplaylist", description="Play or manage your saved playlist")
    @app_commands.describe(action="What do you want to do?", index="Track number to remove (if action is remove)")
    @app_commands.choices(action=[
        app_commands.Choice(name="Play", value="play"),
        app_commands.Choice(name="View", value="view"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="Clear All", value="clear")
    ])
    async def myplaylist(self, interaction: discord.Interaction, action: str, index: int = None):
        from music.db import get_playlist, remove_multiple_from_playlist, clear_playlist
        from music.track import Track
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        tracks_data = get_playlist(guild_id, user_id)
        
        if action == "view":
            if not tracks_data:
                return await interaction.response.send_message("Your playlist is empty.", ephemeral=True)
            text = "\n".join([f"{i+1}. {t['title']}" for i, t in enumerate(tracks_data)])
            if len(text) > 1900:
                text = text[:1900] + "\n...and more."
            await interaction.response.send_message(f"**Your Playlist:**\n{text}", ephemeral=True)
            
        elif action == "clear":
            clear_playlist(guild_id, user_id)
            await interaction.response.send_message("Your saved playlist has been completely cleared!", ephemeral=True)
            
        elif action == "play":
            if not tracks_data:
                return await interaction.response.send_message("Your playlist is empty.", ephemeral=True)
                
            if not interaction.user.voice:
                return await interaction.response.send_message("You must be in a voice channel to play music.", ephemeral=True)
                
            await interaction.response.defer()
            manager = self.get_manager(interaction.guild_id)
            channel = interaction.user.voice.channel
            manager.text_channel = interaction.channel
            
            if not manager.voice_client:
                manager.voice_client = await channel.connect(self_deaf=True)
            elif manager.voice_client.channel != channel:
                await manager.voice_client.move_to(channel)
                
            for t in tracks_data:
                track = Track(
                    title=t['title'],
                    url=t['url'],
                    source_url="",
                    duration=t['duration'],
                    requester=interaction.user.id,
                    thumbnail=t['thumbnail'],
                    artist=t['artist'],
                    video_id=t['video_id']
                )
                manager.queue.append(track)
                
            if not manager.voice_client.is_playing() and not manager.voice_client.is_paused():
                manager.play_next()
                
            await interaction.followup.send(f"Added **{len(tracks_data)}** tracks from your playlist to the queue!")
            
        elif action == "remove":
            if not index:
                return await interaction.response.send_message("Please provide the track number to remove using the `index` option.", ephemeral=True)
            if remove_multiple_from_playlist(guild_id, user_id, [index - 1]):
                await interaction.response.send_message(f"Removed track #{index} from your playlist.", ephemeral=True)
            else:
                await interaction.response.send_message("Invalid track number.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if manager.voice_client and manager.voice_client.is_playing():
            manager.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused the music.")
            await manager.update_panel(is_new=False)
        else:
            await interaction.response.send_message("Music is not playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the current song")
    async def resume(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if manager.voice_client and manager.voice_client.is_paused():
            manager.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed the music.")
            await manager.update_panel(is_new=False)
        else:
            await interaction.response.send_message("Music is not paused.", ephemeral=True)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if manager.voice_client and manager.voice_client.is_playing():
            manager.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped the song.")
            await manager.update_panel(is_new=False)
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)
            
    @app_commands.command(name="prev", description="Play the previous song")
    async def prev(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if manager.history:
            if manager.current_track:
                manager.queue.insert(0, manager.current_track)
            prev_track = manager.history.pop()
            manager.queue.insert(0, prev_track)
            if manager.voice_client and manager.voice_client.is_playing():
                manager.voice_client.stop()
            else:
                manager.play_next()
            await interaction.response.send_message("⏪ Playing previous song.")
            await manager.update_panel(is_new=False)
        else:
            await interaction.response.send_message("No previous song in history.", ephemeral=True)

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        import random
        random.shuffle(manager.queue)
        await interaction.response.send_message("🔀 Shuffled the queue.")
        await manager.update_panel(is_new=False)

    @app_commands.command(name="loop", description="Toggle loop mode")
    async def loop(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        manager.loop_mode = (manager.loop_mode + 1) % 3
        modes = ["Off", "Track", "Queue"]
        await interaction.response.send_message(f"🔁 Loop mode set to: **{modes[manager.loop_mode]}**")
        await manager.update_panel(is_new=False)

    @app_commands.command(name="autoplay", description="Toggle autoplay")
    async def autoplay(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        manager.autoplay = not manager.autoplay
        if manager.autoplay and len(manager.queue) < 1:
            manager.bot.loop.create_task(manager.fill_autoplay_queue())
        state = "On" if manager.autoplay else "Off"
        await interaction.response.send_message(f"📻 Autoplay is now **{state}**.")
        await manager.update_panel(is_new=False)

    @app_commands.command(name="volume", description="Set the volume (0-100)")
    async def volume(self, interaction: discord.Interaction, level: int):
        manager = self.get_manager(interaction.guild_id)
        manager.volume = max(0, min(100, level))
        if manager.voice_client and manager.voice_client.source:
            manager.voice_client.source.volume = manager.volume / 100.0
        await interaction.response.send_message(f"🔊 Volume set to **{manager.volume}%**.")
        await manager.update_panel(is_new=False)

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        if not manager.queue:
            return await interaction.response.send_message("The queue is empty.", ephemeral=True)
            
        q_list = "\n".join([f"{i+1}. {track.title}" for i, track in enumerate(manager.queue[:10])])
        if len(manager.queue) > 10:
            q_list += f"\n...and {len(manager.queue) - 10} more."
            
        await interaction.response.send_message(f"**Current Queue:**\n{q_list}")

    @app_commands.command(name="move", description="Move a song in the queue")
    async def move(self, interaction: discord.Interaction, from_index: int, to_index: int):
        manager = self.get_manager(interaction.guild_id)
        if from_index < 1 or from_index > len(manager.queue) or to_index < 1 or to_index > len(manager.queue):
            return await interaction.response.send_message("Invalid indices.", ephemeral=True)
            
        track = manager.queue.pop(from_index - 1)
        manager.queue.insert(to_index - 1, track)
        await interaction.response.send_message(f"Moved **{track.title}** to position {to_index}.")
        await manager.update_panel(is_new=False)

    @app_commands.command(name="remove", description="Remove a song from the queue")
    async def remove(self, interaction: discord.Interaction, index: int):
        manager = self.get_manager(interaction.guild_id)
        if index < 1 or index > len(manager.queue):
            return await interaction.response.send_message("Invalid index.", ephemeral=True)
            
        track = manager.queue.pop(index - 1)
        await interaction.response.send_message(f"Removed **{track.title}** from the queue.")
        await manager.update_panel(is_new=False)

    @app_commands.command(name="clearqueue", description="Clear the entire queue")
    async def clearqueue(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild_id)
        manager.queue.clear()
        await interaction.response.send_message("The queue has been completely cleared!")
        await manager.update_panel(is_new=False)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Handle bot being disconnected
        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            manager = self.get_manager(member.guild.id)
            if manager.panel_message:
                try:
                    await manager.panel_message.delete()
                except:
                    pass
                manager.panel_message = None
            manager.reset_state()
            manager.voice_client = None
            
        # Handle everyone else leaving the bot's channel
        if before.channel is not None and not member.bot:
            manager = self.get_manager(member.guild.id)
            if manager.voice_client and manager.voice_client.channel and manager.voice_client.channel.id == before.channel.id:
                channel = self.bot.get_channel(before.channel.id)
                non_bot_members = [m for m in channel.members if not m.bot]
                if len(non_bot_members) == 0:
                    self.bot.loop.create_task(self.check_alone(manager, channel.id))
                    
    async def check_alone(self, manager, channel_id):
        await asyncio.sleep(60) # Wait 1 minute
        if manager.voice_client and manager.voice_client.channel and manager.voice_client.channel.id == channel_id:
            channel = self.bot.get_channel(channel_id)
            non_bot_members = [m for m in channel.members if not m.bot]
            if len(non_bot_members) == 0:
                manager.reset_state()
                
                if manager.voice_client.is_playing() or manager.voice_client.is_paused():
                    manager.voice_client.stop()
                    
                if manager.voice_client:
                    await manager.voice_client.disconnect()
                manager.voice_client = None
                
                if manager.text_channel:
                    try:
                        await manager.text_channel.send("😴 I left the voice channel because I was left alone for 1 minute.")
                    except:
                        pass
                if manager.panel_message:
                    try:
                        await manager.panel_message.delete()
                    except:
                        pass
                    manager.panel_message = None

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
