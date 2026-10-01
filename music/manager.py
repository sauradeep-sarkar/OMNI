import discord
import asyncio
import time
import random
from music.card import generate_music_card

class SimilarSongSelect(discord.ui.Select):
    def __init__(self, manager):
        self.manager = manager
        options = []
        if manager.similar_tracks:
            for i, t in enumerate(manager.similar_tracks[:25]):
                options.append(discord.SelectOption(label=t.title[:100], description=t.artist[:100], value=str(i), emoji="🎵"))
        else:
            options.append(discord.SelectOption(label="No similar songs found", value="-1"))
            
        super().__init__(placeholder="🎵 Pick a similar song", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        val = int(self.values[0])
        if val == -1:
            await interaction.response.send_message("No song selected.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        track_placeholder = self.manager.similar_tracks[val]
        cog = self.manager.bot.get_cog("MusicCog")
        tracks = await cog.resolver.search(track_placeholder.url, interaction.user.id)
        
        if tracks:
            self.manager.queue.append(tracks[0])
            await interaction.followup.send(f"Added **{tracks[0].title}** to the queue!", ephemeral=True)
        if not self.manager.voice_client or not self.manager.voice_client.is_playing():
            if self.manager.voice_client:
                self.manager.play_next()


class EditPlaylistSelect(discord.ui.Select):
    def __init__(self, manager):
        self.manager = manager
        options = []
        for i, track in enumerate(manager.queue[:25]):
            options.append(discord.SelectOption(
                label=track.title[:100],
                description=track.artist[:100],
                value=str(i),
                emoji="🎵"
            ))
        if not options:
            options.append(discord.SelectOption(label="Queue is empty", value="-1"))
            
        super().__init__(placeholder="🗑️ Select a song to remove...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "-1":
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
            
        index = int(self.values[0])
        if 0 <= index < len(self.manager.queue):
            removed = self.manager.queue.pop(index)
            await interaction.response.send_message(f"Removed **{removed.title}** from the queue.", ephemeral=True)
            await self.manager.update_panel(is_new=False)
        else:
            await interaction.response.send_message("Invalid selection.", ephemeral=True)

class MoveTrackModal(discord.ui.Modal, title="Move a Song"):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        
        self.old_pos = discord.ui.TextInput(
            label="Current Track Number (1, 2, 3...)",
            placeholder="e.g. 5",
            required=True,
            min_length=1,
            max_length=3
        )
        self.new_pos = discord.ui.TextInput(
            label="New Position (1, 2, 3...)",
            placeholder="e.g. 1",
            required=True,
            min_length=1,
            max_length=3
        )
        self.add_item(self.old_pos)
        self.add_item(self.new_pos)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            old_idx = int(self.old_pos.value) - 1
            new_idx = int(self.new_pos.value) - 1
            
            if 0 <= old_idx < len(self.manager.queue):
                new_idx = max(0, min(new_idx, len(self.manager.queue) - 1))
                track = self.manager.queue.pop(old_idx)
                self.manager.queue.insert(new_idx, track)
                await interaction.response.send_message(f"Moved **{track.title}** to position {new_idx + 1}!", ephemeral=True)
                await self.manager.update_panel(is_new=False)
            else:
                await interaction.response.send_message("Invalid track number. Please check the queue and try again.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers.", ephemeral=True)

class ManageSavedPlaylistSelect(discord.ui.Select):
    def __init__(self, guild_id, user_id, tracks):
        self.guild_id = guild_id
        self.user_id = user_id
        self.tracks = tracks
        options = []
        for i, track in enumerate(tracks[:25]):
            options.append(discord.SelectOption(
                label=track['title'][:100],
                description=track['artist'][:100],
                value=str(i),
                emoji="🗑️"
            ))
        if not options:
            options.append(discord.SelectOption(label="Playlist is empty", value="-1"))
            
        super().__init__(placeholder="🗑️ Select songs to remove...", min_values=1, max_values=len(options) if options[0].value != "-1" else 1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "-1":
            return await interaction.response.send_message("Playlist is empty.", ephemeral=True)
            
        from music.db import remove_multiple_from_playlist, get_playlist
        indices = [int(v) for v in self.values]
        
        remove_multiple_from_playlist(self.guild_id, self.user_id, indices)
        
        await interaction.response.send_message(f"Removed **{len(indices)}** song(s) from your playlist.", ephemeral=True)

class ManageSavedPlaylistView(discord.ui.View):
    def __init__(self, guild_id, user_id, tracks):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(ManageSavedPlaylistSelect(guild_id, user_id, tracks))

    @discord.ui.button(emoji="⚠️", label="Clear Entire Playlist", style=discord.ButtonStyle.danger, row=1)
    async def clear_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        from music.db import clear_playlist
        clear_playlist(self.guild_id, self.user_id)
        await interaction.response.send_message("Your saved playlist has been completely cleared!", ephemeral=True)

class EditPlaylistView(discord.ui.View):
    def __init__(self, manager):
        super().__init__(timeout=60)
        self.manager = manager
        self.add_item(EditPlaylistSelect(manager))

    @discord.ui.button(emoji="🔄", label="Move a Song", style=discord.ButtonStyle.primary, row=1)
    async def move_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MoveTrackModal(self.manager))

    @discord.ui.button(emoji="🗑️", label="Clear Queue", style=discord.ButtonStyle.danger, row=1)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.manager.queue.clear()
        await interaction.response.send_message("The queue has been completely cleared!", ephemeral=True)
        await self.manager.update_panel(is_new=False)

class PlayerButtons(discord.ui.View):
    def __init__(self, manager):
        super().__init__(timeout=None)
        self.manager = manager
        self.add_item(SimilarSongSelect(manager))

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        random.shuffle(self.manager.queue)
        await interaction.response.defer()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary, row=1)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.manager.history:
            if self.manager.current_track:
                self.manager.queue.insert(0, self.manager.current_track)
            
            prev_track = self.manager.history.pop()
            self.manager.queue.insert(0, prev_track)
            
            if self.manager.voice_client and self.manager.voice_client.is_playing():
                self.manager.voice_client.stop()
            else:
                self.manager.play_next()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, row=1)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.manager.voice_client:
            if self.manager.voice_client.is_paused():
                self.manager.voice_client.resume()
            elif self.manager.voice_client.is_playing():
                self.manager.voice_client.pause()
        await interaction.response.defer()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.manager.voice_client and self.manager.voice_client.is_playing():
            self.manager.voice_client.stop()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1, custom_id="loop_btn")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.manager.queue) == 0:
            # If no queue, toggle between Off (0) and Track (2)
            self.manager.loop_mode = 2 if self.manager.loop_mode == 0 else 0
        else:
            self.manager.loop_mode = (self.manager.loop_mode + 1) % 3
        await interaction.response.defer()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="📻", style=discord.ButtonStyle.secondary, row=2, custom_id="autoplay_btn")
    async def autoplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.manager.autoplay = not self.manager.autoplay
        await interaction.response.defer()
        if self.manager.autoplay and len(self.manager.queue) < 1:
            self.manager.bot.loop.create_task(self.manager.fill_autoplay_queue())
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=2)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.manager.voice_client and self.manager.voice_client.source:
            self.manager.volume = max(0, self.manager.volume - 10)
            self.manager.voice_client.source.volume = self.manager.volume / 100.0
        await interaction.response.defer()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=2)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.manager.voice_client:
            self.manager.reset_state()
            self.manager.voice_client.stop()
            await self.manager.voice_client.disconnect()
            self.manager.voice_client = None
            if self.manager.panel_message:
                await self.manager.panel_message.delete()
                self.manager.panel_message = None

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=2)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.manager.voice_client and self.manager.voice_client.source:
            self.manager.volume = min(100, self.manager.volume + 10)
            self.manager.voice_client.source.volume = self.manager.volume / 100.0
        await interaction.response.defer()
        await self.manager.update_panel(is_new=False)

    @discord.ui.button(emoji="📜", style=discord.ButtonStyle.secondary, row=2)
    async def playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Playlist Details", color=discord.Color.blurple())
        
        history_list = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(self.manager.history[-5:])])
        if not history_list:
            history_list = "No history."
            
        queue_list = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(self.manager.queue[:10])])
        if not queue_list:
            queue_list = "Queue is empty."
            
        embed.add_field(name="📜 Up Next (Queue)", value=queue_list, inline=False)
        embed.add_field(name="🕒 Played History (Last 5)", value=history_list, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @discord.ui.button(emoji="💾", label="Save Song", style=discord.ButtonStyle.secondary, row=3)
    async def save_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.current_track:
            return await interaction.response.send_message("No song is currently playing.", ephemeral=True)
            
        from music.db import add_to_playlist
        add_to_playlist(str(interaction.guild_id), str(interaction.user.id), {
            "title": self.manager.current_track.title,
            "url": self.manager.current_track.url,
            "duration": self.manager.current_track.duration,
            "thumbnail": self.manager.current_track.thumbnail,
            "artist": self.manager.current_track.artist,
            "video_id": self.manager.current_track.video_id
        })
        await interaction.response.send_message(f"💾 Saved **{self.manager.current_track.title}** to your playlist! Use `/myplaylist` to play it.", ephemeral=True)
        
    @discord.ui.button(emoji="🗑️", label="Edit Queue", style=discord.ButtonStyle.secondary, row=3)
    async def edit_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.queue:
            await interaction.response.send_message("The queue is empty!", ephemeral=True)
            return
        await interaction.response.send_message("Select a song to remove from the queue:", view=EditPlaylistView(self.manager), ephemeral=True)

    @discord.ui.button(emoji="📂", label="My Playlist", style=discord.ButtonStyle.secondary, row=3)
    async def manage_saved_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        from music.db import get_playlist
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        tracks = get_playlist(guild_id, user_id)
        if not tracks:
            return await interaction.response.send_message("Your saved playlist is currently empty. Use the 💾 button to save songs!", ephemeral=True)
            
        await interaction.response.send_message(
            f"Manage your saved playlist ({len(tracks)} songs):", 
            view=ManageSavedPlaylistView(guild_id, user_id, tracks), 
            ephemeral=True
        )

class GuildMusicManager:
    def __init__(self, bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue = []
        self.history = []
        self.similar_tracks = []
        self.current_track = None
        self.voice_client = None
        
        self.text_channel = None
        self.panel_message = None
        self.start_time = 0
        self.updater_task = None
        
        self.autoplay = False
        self.loop_mode = 0 # 0=Off, 1=Queue, 2=Track
        self.volume = 100

    def reset_state(self):
        self.queue.clear()
        self.history.clear()
        self.similar_tracks.clear()
        self.current_track = None
        self.start_time = 0
        if self.updater_task:
            self.updater_task.cancel()
            self.updater_task = None
        self.autoplay = False
        self.loop_mode = 0
        self.volume = 100

    def play_next(self, error=None):
        if error:
            print(f'Player error: {error}')
            
        if self.updater_task:
            self.updater_task.cancel()
            
        if self.current_track:
            if self.loop_mode == 2:
                self.queue.insert(0, self.current_track)
            elif self.loop_mode == 1:
                self.queue.append(self.current_track)
                self.history.append(self.current_track)
            else:
                self.history.append(self.current_track)
        
        if self.queue:
            self.current_track = self.queue.pop(0)
            self.bot.loop.create_task(self._start_playback_async())
        else:
            if self.autoplay and self.history:
                self.bot.loop.create_task(self.play_autoplay_track())
            else:
                self.current_track = None
                if self.panel_message:
                    try:
                        self.bot.loop.create_task(self.panel_message.delete())
                    except Exception:
                        pass
                    self.panel_message = None

    async def fill_autoplay_queue(self):
        if not self.autoplay:
            return
        if len(self.queue) < 5 and (self.history or self.current_track):
            last_track = self.current_track if self.current_track else self.history[-1]
            if not last_track or not last_track.video_id:
                return
                
            history_ids = [t.video_id for t in self.history if t.video_id] + [t.video_id for t in self.queue if t.video_id]
            if self.current_track and self.current_track.video_id:
                history_ids.append(self.current_track.video_id)
                
            cog = self.bot.get_cog("MusicCog")
            if cog:
                tracks = await cog.resolver.get_autoplay_tracks(last_track.video_id, self.bot.user.id, history_ids, count=5 - len(self.queue))
                if tracks:
                    self.queue.extend(tracks)
                    await self.update_panel(is_new=False)

    async def play_autoplay_track(self):
        last_track = self.history[-1] if self.history else None
        if not last_track or not last_track.video_id:
            return
            
        history_ids = [t.video_id for t in self.history if t.video_id]
        
        cog = self.bot.get_cog("MusicCog")
        if cog:
            tracks = await cog.resolver.get_autoplay_tracks(last_track.video_id, self.bot.user.id, history_ids, count=1)
            if tracks:
                self.queue.extend(tracks)
                self.current_track = self.queue.pop(0)
                await self._start_playback_async()
                return

        self.current_track = None
        if self.panel_message:
            try:
                await self.panel_message.delete()
            except:
                pass
            self.panel_message = None

    async def _start_playback_async(self):
        # Always re-resolve the URL right before playback to prevent 403 Forbidden errors from expired CDN links
        cog = self.bot.get_cog("MusicCog")
        if cog:
            try:
                resolved_list = await cog.resolver.search(self.current_track.url, self.current_track.requester)
                if resolved_list:
                    resolved = resolved_list[0]
                    if resolved and resolved.source_url:
                        self.current_track = resolved
            except Exception as e:
                print(f"Error re-resolving track: {e}")
                    
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -headers "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36\r\n"',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio(self.current_track.source_url, executable="ffmpeg.exe", **ffmpeg_options)
        volume_source = discord.PCMVolumeTransformer(source, volume=self.volume / 100.0)
        self.voice_client.play(volume_source, after=self.play_next)
        self.start_time = time.time()
        
        self.updater_task = self.bot.loop.create_task(self.panel_updater())

    async def generate_embed(self, elapsed, is_new=False):
        if not self.current_track:
            return None, None
            
        embed = discord.Embed(
            title=f"Now Playing — {self.current_track.title[:50]}",
            description=f"By {self.current_track.artist}\nRequested by <@{self.current_track.requester}>",
            color=discord.Color.from_rgb(43, 45, 49)
        )
        
        if self.current_track.thumbnail:
            embed.set_thumbnail(url=self.current_track.thumbnail)
            
        loop_str = {0: "Off", 1: "Queue", 2: "Track"}[self.loop_mode]
        auto_str = "On" if self.autoplay else "Off"
        
        embed.add_field(name="Autoplay", value=auto_str, inline=True)
        embed.add_field(name="Loop", value=loop_str, inline=True)
        embed.add_field(name="Volume", value=f"{self.volume}%", inline=True)
        
        if self.current_track.duration > 0:
            bar_length = 20
            progress = int((elapsed / self.current_track.duration) * bar_length)
            bar = "▬" * progress + "🔘" + "▬" * (bar_length - progress - 1)
            
            def fmt(sec):
                m, s = divmod(int(sec), 60)
                h, m = divmod(m, 60)
                if h > 0: return f"{h}:{m:02d}:{s:02d}"
                return f"{m}:{s:02d}"
                
            embed.add_field(name="Progress", value=f"`{bar}`\n`{fmt(elapsed)} / {fmt(self.current_track.duration)}`", inline=False)
            
        return embed, None

    async def update_panel(self, is_new=False):
        if not self.text_channel or not self.current_track:
            return
            
        elapsed = 0
        if self.current_track.duration > 0:
            elapsed = int(time.time() - self.start_time)
            if elapsed > self.current_track.duration:
                elapsed = self.current_track.duration
                
        embed, file = await self.generate_embed(elapsed, is_new=is_new)
        if not embed:
            return
            
        view = PlayerButtons(self)
        
        for item in view.children:
            if hasattr(item, "custom_id"):
                if item.custom_id == "loop_btn":
                    if self.loop_mode == 1:
                        item.style = discord.ButtonStyle.success
                        item.emoji = "🔁"
                    elif self.loop_mode == 2:
                        item.style = discord.ButtonStyle.primary
                        item.emoji = "🔂" # Repeat One emoji
                    else:
                        item.style = discord.ButtonStyle.secondary
                        item.emoji = "🔁"
                elif item.custom_id == "autoplay_btn":
                    if self.autoplay:
                        item.style = discord.ButtonStyle.success
                    else:
                        item.style = discord.ButtonStyle.secondary
        try:
            if is_new:
                if self.panel_message:
                    try:
                        await self.panel_message.delete()
                    except:
                        pass
                self.panel_message = await self.text_channel.send(embed=embed, file=file, view=view)
            elif self.panel_message:
                if file:
                    await self.panel_message.edit(embed=embed, attachments=[file], view=view)
                else:
                    await self.panel_message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"Panel error: {e}")
            
    async def fetch_similar_tracks(self):
        cog = self.bot.get_cog("MusicCog")
        if cog and self.current_track and self.current_track.video_id:
            loop = asyncio.get_event_loop()
            try:
                watch_playlist = await loop.run_in_executor(None, lambda: cog.resolver.ytmusic.get_watch_playlist(videoId=self.current_track.video_id, limit=25))
                tracks = []
                if 'tracks' in watch_playlist:
                    for t in watch_playlist['tracks']:
                        if t['videoId'] != self.current_track.video_id:
                            from music.track import Track
                            track = Track(
                                title=t.get('title', 'Unknown'),
                                url=f"https://music.youtube.com/watch?v={t['videoId']}",
                                source_url="",
                                duration=0,
                                requester=self.bot.user.id,
                                thumbnail=t.get('thumbnails', [{'url': ''}])[0]['url'],
                                artist=t.get('artists', [{'name': 'Unknown'}])[0]['name'],
                                video_id=t['videoId']
                            )
                            tracks.append(track)
                self.similar_tracks = tracks
                await self.update_panel(is_new=False)
            except Exception as e:
                print(f"Failed to fetch similar tracks: {e}")

    async def panel_updater(self):
        await asyncio.sleep(1)
        self.similar_tracks = [] 
        await self.update_panel(is_new=True) 
        
        self.bot.loop.create_task(self.fetch_similar_tracks())
        
        while self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            await asyncio.sleep(10)
            if self.voice_client.is_playing():
                if self.autoplay and len(self.queue) < 1:
                    self.bot.loop.create_task(self.fill_autoplay_queue())
                await self.update_panel(is_new=False)
