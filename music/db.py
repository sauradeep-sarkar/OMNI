import sqlite3
import json

DB_FILE = "OMNI_Playlists.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS playlists (user_id TEXT, track_data TEXT)")
        # Check if guild_id column exists (for backwards compatibility if DB was already created)
        cursor = conn.execute("PRAGMA table_info(playlists)")
        columns = [col[1] for col in cursor.fetchall()]
        if "guild_id" not in columns:
            conn.execute("ALTER TABLE playlists ADD COLUMN guild_id TEXT DEFAULT 'global'")
        conn.commit()

def add_to_playlist(guild_id: str, user_id: str, track_dict: dict):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO playlists (guild_id, user_id, track_data) VALUES (?, ?, ?)", 
                     (str(guild_id), str(user_id), json.dumps(track_dict)))
        conn.commit()

def get_playlist(guild_id: str, user_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT track_data FROM playlists WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
        rows = cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

def remove_multiple_from_playlist(guild_id: str, user_id: str, indices: list[int]):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT track_data FROM playlists WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
        rows = cursor.fetchall()
        
        # Sort descending to safely pop by index
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(rows):
                rows.pop(idx)
                
        conn.execute("DELETE FROM playlists WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
        for row in rows:
            conn.execute("INSERT INTO playlists (guild_id, user_id, track_data) VALUES (?, ?, ?)", (str(guild_id), str(user_id), row[0]))
        conn.commit()
        return True

def clear_playlist(guild_id: str, user_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM playlists WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
        conn.commit()
        return True
