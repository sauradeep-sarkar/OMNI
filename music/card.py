import asyncio
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

async def generate_music_card(thumbnail_url: str, title: str, artist: str, elapsed: int = 0, duration: int = 0) -> io.BytesIO:
    W, H = 800, 300

    # 1. Fetch thumbnail
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status == 200:
                    thumb_data = await resp.read()
                    thumb = Image.open(io.BytesIO(thumb_data)).convert("RGBA")
                else:
                    thumb = Image.new("RGBA", (400, 400), (60, 60, 60, 255))
    except:
        thumb = Image.new("RGBA", (400, 400), (60, 60, 60, 255))
        
    # Crop thumbnail to square
    w, h = thumb.size
    if w != h:
        min_dim = min(w, h)
        left = (w - min_dim) / 2
        top = (h - min_dim) / 2
        right = (w + min_dim) / 2
        bottom = (h + min_dim) / 2
        thumb = thumb.crop((left, top, right, bottom))
        
    # Blur background
    bg_thumb = thumb.resize((W, int(W * thumb.height / thumb.width)), Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC)
    bg_thumb = bg_thumb.filter(ImageFilter.GaussianBlur(radius=50))
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    base.paste(bg_thumb, (0, int((H - bg_thumb.height) / 2)))
    
    # Overlay dark tint for contrast
    overlay = Image.new("RGBA", (W, H), (15, 15, 20, 190))
    base = Image.alpha_composite(base, overlay)
    
    # Draw rounded background corners
    mask_card = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask_card).rounded_rectangle([0, 0, W, H], radius=35, fill=255)
    base.putalpha(mask_card)

    # Prepare high-res thumbnail
    thumb_size = 220
    thumb = thumb.resize((thumb_size, thumb_size), Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC)
    
    # Round thumbnail corners (using mask to preserve original colors, no tint)
    mask_thumb = Image.new("L", (thumb_size, thumb_size), 0)
    ImageDraw.Draw(mask_thumb).rounded_rectangle([0, 0, thumb_size, thumb_size], radius=30, fill=255)
    
    thumb_canvas = Image.new("RGBA", (thumb_size, thumb_size), (0,0,0,0))
    thumb_canvas.paste(thumb, (0, 0))
    thumb_canvas.putalpha(mask_thumb)
    
    # Paste thumbnail at left side
    base.paste(thumb_canvas, (40, 40), mask=thumb_canvas)

    # Setup Drawing & Fonts
    draw = ImageDraw.Draw(base)
    try:
        font_title = ImageFont.truetype("arial.ttf", 42)
        font_artist = ImageFont.truetype("arial.ttf", 32)
    except:
        font_title = ImageFont.load_default()
        font_artist = ImageFont.load_default()
        
    # Draw Title & Artist
    text_x = 300
    title_text = title[:30] + ("..." if len(title) > 30 else "")
    artist_text = artist[:40] + ("..." if len(artist) > 40 else "")
    draw.text((text_x, 90), title_text, font=font_title, fill=(255, 255, 255, 255))
    draw.text((text_x, 150), artist_text, font=font_artist, fill=(200, 200, 200, 255))

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf
