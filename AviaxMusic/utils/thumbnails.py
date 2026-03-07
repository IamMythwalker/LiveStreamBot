import os 
import re 
import aiofiles 
import aiohttp 
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter 
from youtubesearchpython.__future__ import VideosSearch 
from config import FAILED 
from py_yt import VideosSearch

CACHE_DIR = "cache" 
os.makedirs(CACHE_DIR, exist_ok=True) 
 
# Canvas and Card Settings 
WIDTH, HEIGHT = 1280, 720 
CARD_W, CARD_H = 1000, 580 
CARD_X = (WIDTH - CARD_W) // 2 
CARD_Y = (HEIGHT - CARD_H) // 2 
 
THUMB_W, THUMB_H = 960, 400 
THUMB_X = CARD_X + (CARD_W - THUMB_W) // 2 
THUMB_Y = CARD_Y + 20 
 
# Adjusted positions to fit within card boundaries
TITLE_Y = THUMB_Y + THUMB_H + 20 
META_Y = TITLE_Y + 36 
BAR_Y = META_Y + 45 
BAR_W = 800 
BAR_H = 8  # Bold progress bar
BAR_X = CARD_X + (CARD_W - BAR_W) // 2  # Centered within card
 
MAX_TITLE_WIDTH = 940 
 
 
def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str: 
    ellipsis = "…" 
    if font.getlength(text) <= max_w: 
        return text 
    for i in range(len(text) - 1, 0, -1): 
        if font.getlength(text[:i] + ellipsis) <= max_w: 
            return text[:i] + ellipsis 
    return ellipsis 
 
 
async def gen_thumb(videoid: str) -> str: 
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_frosted_white.png") 
    if os.path.exists(cache_path): 
        return cache_path 
 
    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1) 
    try: 
        results_data = await results.next() 
        data = results_data.get("result", [])[0] 
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title() 
        thumbnail = data.get("thumbnails", [{}])[0].get("url", FAILED) 
        duration = data.get("duration") 
        views = data.get("viewCount", {}).get("short", "Unknown Views") 
    except Exception: 
        title, thumbnail, duration, views = "Unsupported Title", FAILED, None, "Unknown Views" 
 
    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"} 
    duration_text = "Live" if is_live else duration or "Unknown Mins" 
 
    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png") 
    try: 
        async with aiohttp.ClientSession() as session: 
            async with session.get(thumbnail) as resp: 
                if resp.status == 200: 
                    async with aiofiles.open(thumb_path, "wb") as f: 
                        await f.write(await resp.read()) 
    except Exception: 
        return FAILED 
 
    # Load and blur background 
    thumb = Image.open(thumb_path).convert("RGB") 
    bg = thumb.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(30)) 
    base = bg.convert("RGBA") 
 
    draw = ImageDraw.Draw(base) 
 
    # White frosted card with rounded corners
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0)) 
    card_draw = ImageDraw.Draw(card)
    # Draw rounded rectangle
    card_draw.rounded_rectangle([(0, 0), (CARD_W, CARD_H)], radius=30, fill=(255, 255, 255, 180))
    frosted = card.filter(ImageFilter.GaussianBlur(5)) 
    base.paste(frosted, (CARD_X, CARD_Y), frosted) 
 
    # Load fonts 
    try: 
        title_font = ImageFont.truetype("AviaxMusic/assets/font2.ttf", 36) 
        regular_font = ImageFont.truetype("AviaxMusic/assets/font.ttf", 22) 
        time_font = ImageFont.truetype("AviaxMusic/assets/font.ttf", 20) 
    except OSError: 
        title_font = regular_font = time_font = ImageFont.load_default() 
 
    # Resize and paste thumbnail with rounded corners (album art style)
    thumb = thumb.resize((THUMB_W, THUMB_H), Image.Resampling.LANCZOS)
    # Create rounded thumbnail
    thumb_rounded = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    thumb_draw = ImageDraw.Draw(thumb_rounded)
    thumb_draw.rounded_rectangle([(0, 0), (THUMB_W, THUMB_H)], radius=20, fill=(255, 255, 255, 255))
    thumb_mask = thumb_rounded.convert("L")
    thumb.putalpha(thumb_mask)
    base.paste(thumb, (THUMB_X, THUMB_Y), thumb) 
 
    # Title - centered within card width
    title_text = trim_to_width(title, title_font, MAX_TITLE_WIDTH) 
    draw.text((CARD_X + CARD_W // 2, TITLE_Y), title_text, fill="black", font=title_font, anchor="mm") 
 
    # Metadata - centered within card width
    draw.text((CARD_X + CARD_W // 2, META_Y), f"YouTube | {views}", fill="black", font=regular_font, anchor="mm") 
 
    # Bold green progress bar 
    bar_green_len = int(BAR_W * 0.3) 
    draw.line([(BAR_X, BAR_Y), (BAR_X + bar_green_len, BAR_Y)], fill="green", width=BAR_H) 
    draw.line([(BAR_X + bar_green_len, BAR_Y), (BAR_X + BAR_W, BAR_Y)], fill="gray", width=BAR_H) 
    draw.ellipse([(BAR_X + bar_green_len - 8, BAR_Y - 8), (BAR_X + bar_green_len + 8, BAR_Y + 8)], fill="green") 
 
    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=time_font) 
    draw.text((BAR_X + BAR_W - 60, BAR_Y + 15), 
              "Live" if is_live else duration_text, fill="red" if is_live else "black", font=time_font) 
 
    try: 
        os.remove(thumb_path) 
    except OSError: 
        pass 
 
    base.save(cache_path, "PNG", optimize=False) 
    return cache_path

