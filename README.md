# OMNI Music Bot

OMNI is a feature-rich, high-performance Discord music bot designed to provide seamless playback with an intuitive, dynamic user interface.

## 🌟 Features
- **Playback**: YouTube, Spotify, Apple Music, and direct URLs. Auto-resolves playable sources.
- **Queue Control**: Add, remove, clear, reorder, shuffle, skip, stop, and pause.
- **Modes**: Track loop, Queue loop, and Autoplay (Infinite Radio).
- **Interactive UI**: Embedded player with dynamic buttons, progress bar, and "Similar Songs" dropdown.
- **User Playlists**: Save favorite songs to your personal server-specific database.
- **Server Isolation**: Each server gets its own independent queue and player state.

---

## 🛠️ Dependencies & Packages

### Dependencies
*(These are external tools or system-level dependencies)*
- **FFmpeg**: The core external binary engine required to encode and stream live audio chunks over Discord's voice protocol.
- **SQLite**: The lightweight database engine used to store user playlists (this comes pre-installed with Python natively, so it doesn't need to be downloaded separately).

### Packages
*(These are the Python modules that should be listed in your `requirements.txt`)*
- **discord.py**: The core Discord framework that handles everything from the bot's connection to Slash Commands and the interactive button UI.
- **PyNaCl**: An encryption library specifically required by `discord.py` to support transmitting audio data to Discord voice channels.
- **yt-dlp**: The heavy-lifting extraction library used to bypass restrictions, grab metadata, and resolve the actual `.m3u8` or `.webm` direct media streams.
- **ytmusicapi**: Used extensively for the rapid text-based search, autocomplete suggestions, and the "Autoplay / Similar Songs" recommendation engine.
- **Pillow**: The Python Imaging Library (PIL) used behind the scenes to dynamically draw and generate the beautiful, customized music player card graphic.
- **python-dotenv**: A simple utility used to securely load your `DISCORD_TOKEN` from the hidden `.env` file.

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
pkg install python clang make pkg-config libffi libsodium ffmpeg rust binutils
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
SODIUM_INSTALL=system python -m pip install --no-cache-dir PyNaCl davey
```

### Step 4: Create Configuration File
Create the `.env` file for your Discord bot token. Run this command (replace `YOUR_TOKEN_HERE` with your actual token):
```bash
echo "DISCORD_TOKEN=YOUR_TOKEN_HERE" > .env
```

### Step 5: Fix FFmpeg Path
If moving the bot from Windows to Termux, open `music/manager.py` and ensure the FFmpeg executable is set to `ffmpeg` (not `ffmpeg.exe`):
```python
executable="ffmpeg"
```

### Step 6: Start the Bot
```bash
python main.py
```

---

## 🔧 Troubleshooting

- **`Executable 'ffmpeg.exe' was not found`**: You are running on Android/Linux but the code still says `ffmpeg.exe`. Change it to `ffmpeg` in `manager.py`.
- **`PyNaCl library needed in order to use voice`**: Native C compilation failed. Ensure you ran `pkg install libsodium` and re-run the `PyNaCl` pip install command from Step 3.
- **`Unknown interaction (10062)`**: This is a Discord API timeout. The bot took too long to respond to a button press, this is normal on slower network connections.
