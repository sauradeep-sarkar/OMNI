# OMNI Music Bot

OMNI is a feature-rich, high-performance Discord music bot designed to provide seamless playback with an intuitive, dynamic user interface.

## 🌟 Features
- **Playback**: YouTube, Spotify, Apple Music, and direct URLs. Auto-resolves playable sources.
- **Queue Control**: Add, remove, clear, reorder, shuffle, skip, stop, and pause.
- **Modes**: Track loop, Queue loop, and Autoplay (Infinite Radio).
- **Interactive UI**: Embedded player with dynamic buttons, progress bar, and "Similar Songs" dropdown.
- **User Playlists**: Save favorite songs to your personal cross-server database.
- **Server Isolation**: Each server gets its own independent queue and player state.

## 🛠️ Tech Stack
- **Core**: Python 3.10+, `discord.py` (v2.x)
- **Audio**: `FFmpeg`, `yt-dlp`
- **APIs**: `ytmusicapi`, `spotipy`
- **Database**: `SQLite3`

---

## 🚀 General Setup (Windows/Linux)

1. **Clone & Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure FFmpeg is installed and added to your system PATH)*

2. **Configuration**:
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   SPOTIPY_CLIENT_ID=your_spotify_client_id
   SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
   ```

3. **Run the Bot**:
   ```bash
   python main.py
   ```

---

## 📱 Termux / Android Setup

Running OMNI on an Android phone using Termux requires specific native packages for audio processing. Follow these steps exactly:

### Step 1: Install Native Packages
Open Termux and run:
```bash
pkg update && pkg upgrade
pkg install python clang make pkg-config libffi libsodium rust rust-std-aarch64-linux-android ffmpeg
```

### Step 2: Grant Storage Access
Allow Termux to read your Android files:
```bash
termux-setup-storage
```
Then navigate to your bot folder (e.g., `cd /storage/emulated/0/Download/OMNI`).

### Step 3: Install Python Dependencies
Install the required packages in this exact order to prevent native build errors:
```bash
python -m pip install --upgrade pip
python -m pip install -U discord.py Pillow yt-dlp ytmusicapi python-dotenv
SODIUM_INSTALL=system python -m pip install --no-cache-dir PyNaCl
python -m pip install --no-cache-dir davey
```

### Step 4: Fix FFmpeg Path
If moving the bot from Windows to Termux, open `music/manager.py` and ensure the FFmpeg executable is set to `ffmpeg` (not `ffmpeg.exe`):
```python
executable="ffmpeg"
```

### Step 5: Start the Bot
```bash
python main.py
```

---

## 🔧 Troubleshooting

- **`Executable 'ffmpeg.exe' was not found`**: You are running on Android/Linux but the code still says `ffmpeg.exe`. Change it to `ffmpeg` in `manager.py`.
- **`PyNaCl library needed in order to use voice`**: Native C compilation failed. Ensure you ran `pkg install libsodium` and re-run the `PyNaCl` pip install command from Step 3.
- **`davey library needed in order to use voice`**: Rust compilation failed. Ensure you installed the Rust packages from Step 1 before installing `davey`.
- **`Unknown interaction (10062)`**: This is a Discord API timeout. The bot took too long to respond to a button press, this is normal on slower network connections.
