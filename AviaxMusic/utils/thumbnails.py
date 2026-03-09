# ATLEAST GIVE CREDITS IF YOU STEALING :(((((((((((((((((((((((((((((((((((((
# ELSE NO FURTHER PUBLIC THUMBNAIL UPDATES

import asyncio
import random
import logging
import os
import re
import aiofiles
import aiohttp
import traceback
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from pyrogram.types import InputMediaPhoto
from youtubesearchpython.__future__ import VideosSearch
from AviaxMusic.utils.formatters import seconds_to_min

# Use the central logger; do NOT call basicConfig here (logging.py owns that)
_log = logging.getLogger(__name__)

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Default fallback thumbnail URL if none provided
DEFAULT_THUMB = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"  # Replace with your actual fallback URL

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

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage

def truncate(text):
    list = text.split(" ")
    text1 = ""
    text2 = ""    
    for i in list:
        if len(text1) + len(i) < 30:        
            text1 += " " + i
        elif len(text2) + len(i) < 30:       
            text2 += " " + i

    text1 = text1.strip()
    text2 = text2.strip()     
    return [text1,text2]

def random_color():
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def generate_gradient(width, height, start_color, end_color):
    base = Image.new('RGBA', (width, height), start_color)
    top = Image.new('RGBA', (width, height), end_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(60 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

def add_border(image, border_width, border_color):
    width, height = image.size
    new_width = width + 2 * border_width
    new_height = height + 2 * border_width
    new_image = Image.new("RGBA", (new_width, new_height), border_color)
    new_image.paste(image, (border_width, border_width))
    return new_image

def crop_center_circle(img, output_size, border, border_color, crop_scale=1.5):
    half_the_width = img.size[0] / 2
    half_the_height = img.size[1] / 2
    larger_size = int(output_size * crop_scale)
    img = img.crop(
        (
            half_the_width - larger_size/2,
            half_the_height - larger_size/2,
            half_the_width + larger_size/2,
            half_the_height + larger_size/2
        )
    )
    
    img = img.resize((output_size - 2*border, output_size - 2*border))
    
    
    final_img = Image.new("RGBA", (output_size, output_size), border_color)
    
    
    mask_main = Image.new("L", (output_size - 2*border, output_size - 2*border), 0)
    draw_main = ImageDraw.Draw(mask_main)
    draw_main.ellipse((0, 0, output_size - 2*border, output_size - 2*border), fill=255)
    
    final_img.paste(img, (border, border), mask_main)
    
    
    mask_border = Image.new("L", (output_size, output_size), 0)
    draw_border = ImageDraw.Draw(mask_border)
    draw_border.ellipse((0, 0, output_size, output_size), fill=255)
    
    result = Image.composite(final_img, Image.new("RGBA", final_img.size, (0, 0, 0, 0)), mask_border)
    
    return result

def draw_text_with_shadow(background, draw, position, text, font, fill, shadow_offset=(3, 3), shadow_blur=5):
    
    shadow = Image.new('RGBA', background.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    
    
    shadow_draw.text(position, text, font=font, fill="black")
    
    
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    
    
    background.paste(shadow, shadow_offset, shadow)
    
    
    draw.text(position, text, font=font, fill=fill)

def _draw_card(base, draw, thumb, title, views, duration_text, is_live,
               title_font, regular_font, time_font, progress: float = 0.0,
               elapsed_text: str = "00:00"):
    """Draw the frosted card, thumbnail, title, metadata, and progress bar.

    Args:
        progress: float between 0.0 and 1.0 representing playback progress.
        elapsed_text: human-readable elapsed time string (e.g. "01:23").
    """
    # White frosted card with rounded corners
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle([(0, 0), (CARD_W, CARD_H)], radius=30, fill=(255, 255, 255, 180))
    frosted = card.filter(ImageFilter.GaussianBlur(5))
    base.paste(frosted, (CARD_X, CARD_Y), frosted)

    # Resize and paste thumbnail with rounded corners (album art style)
    thumb_r = thumb.resize((THUMB_W, THUMB_H), Image.Resampling.LANCZOS)
    thumb_rounded = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    thumb_draw_r = ImageDraw.Draw(thumb_rounded)
    thumb_draw_r.rounded_rectangle([(0, 0), (THUMB_W, THUMB_H)], radius=20, fill=(255, 255, 255, 255))
    thumb_mask = thumb_rounded.convert("L")
    thumb_r.putalpha(thumb_mask)
    base.paste(thumb_r, (THUMB_X, THUMB_Y), thumb_r)

    # Title
    title_text = trim_to_width(title, title_font, MAX_TITLE_WIDTH)
    draw.text((CARD_X + CARD_W // 2, TITLE_Y), title_text, fill="black", font=title_font, anchor="mm")

    # Metadata
    platform = "🔴 LIVE" if is_live else "YouTube"
    draw.text((CARD_X + CARD_W // 2, META_Y), f"{platform} | {views}", fill="black", font=regular_font, anchor="mm")

    # Progress bar  
    progress = max(0.0, min(1.0, progress))
    bar_green_len = int(BAR_W * progress)

    # Track background
    draw.rounded_rectangle(
        [(BAR_X, BAR_Y - BAR_H // 2), (BAR_X + BAR_W, BAR_Y + BAR_H // 2)],
        radius=BAR_H // 2, fill=(200, 200, 200, 220)
    )
    # Filled portion
    if bar_green_len > 0:
        draw.rounded_rectangle(
            [(BAR_X, BAR_Y - BAR_H // 2), (BAR_X + bar_green_len, BAR_Y + BAR_H // 2)],
            radius=BAR_H // 2, fill=(30, 215, 96, 255)  # Spotify-green
        )
    # Scrubber dot
    dot_x = BAR_X + bar_green_len
    draw.ellipse([(dot_x - 9, BAR_Y - 9), (dot_x + 9, BAR_Y + 9)], fill=(30, 215, 96, 255))

    # Time labels
    draw.text((BAR_X, BAR_Y + 14), elapsed_text, fill="#555555", font=time_font)
    draw.text(
        (BAR_X + BAR_W, BAR_Y + 14),
        "🔴 LIVE" if is_live else duration_text,
        fill="#cc0000" if is_live else "#555555",
        font=time_font,
        anchor="ra",
    )


async def gen_thumb(videoid: str) -> str:
    """Generate a cached thumbnail at progress=0 (or cached version)."""
    return await gen_thumb_with_progress(videoid, progress=0.0, elapsed_text="00:00")


async def gen_thumb_with_progress(
    videoid: str,
    progress: float = 0.0,
    elapsed_text: str = "00:00",
    force: bool = False,
) -> str:
    """Generate (or re-generate) a thumbnail image for *videoid*.

    Args:
        videoid: YouTube video ID.
        progress: Playback progress ratio in [0.0, 1.0].
        elapsed_text: Human-readable elapsed time, e.g. "02:45".
        force: When True, ignore any cached file and re-render.

    Returns:
        Path to the generated PNG, or None on failure.
    """
    try:
        # For static (initial) thumbnails we cache at progress=0.
        # Dynamic progress thumbnails use a separate filename so the static
        # cache is never invalidated.
        if force or progress > 0.0:
            cache_path = os.path.join(CACHE_DIR, f"{videoid}_prog.png")
        else:
            cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
            if os.path.exists(cache_path):
                return cache_path

        # ── Fetch video metadata ───────────────────────────────────────────
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        try:
            results_data = await results.next()
            data = results_data.get("result", [])[0]
            title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
            thumbnail = data.get("thumbnails", [{}])[0].get("url", DEFAULT_THUMB)
            duration = data.get("duration")
            views = data.get("viewCount", {}).get("short", "Unknown Views")
        except Exception as e:
            _log.error("Error fetching video data for %s: %s", videoid, e)
            title, thumbnail, duration, views = "Unsupported Title", DEFAULT_THUMB, None, "Unknown Views"

        is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
        duration_text = "LIVE" if is_live else (duration or "--:--")

        # ── Download YouTube thumbnail ─────────────────────────────────────
        thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
        thumb_downloaded = False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(thumbnail, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(thumb_path, "wb") as f:
                            await f.write(await resp.read())
                        thumb_downloaded = True
        except Exception as e:
            _log.warning("Thumbnail download failed for %s: %s", videoid, e)

        if not thumb_downloaded:
            thumb_img = Image.new("RGB", (THUMB_W, THUMB_H), color=(40, 40, 40))
            thumb_img.save(thumb_path)

        # ── Build the card ─────────────────────────────────────────────────
        thumb_img = Image.open(thumb_path).convert("RGB")

        # Blurred background
        bg = thumb_img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(30))
        base = bg.convert("RGBA")
        draw = ImageDraw.Draw(base)

        # Fonts
        try:
            title_font = ImageFont.truetype("AviaxMusic/assets/font2.ttf", 36)
            regular_font = ImageFont.truetype("AviaxMusic/assets/font.ttf", 22)
            time_font = ImageFont.truetype("AviaxMusic/assets/font.ttf", 20)
        except OSError:
            _log.warning("Custom fonts not found – falling back to default")
            title_font = regular_font = time_font = ImageFont.load_default()

        _draw_card(
            base, draw, thumb_img,
            title, views, duration_text, is_live,
            title_font, regular_font, time_font,
            progress=progress,
            elapsed_text=elapsed_text,
        )

        # ── Cleanup & save ─────────────────────────────────────────────────
        try:
            os.remove(thumb_path)
        except OSError:
            pass

        base.save(cache_path, "PNG", optimize=False)
        _log.debug("Thumbnail generated: %s (progress=%.2f)", cache_path, progress)
        return cache_path

    except Exception as e:
        _log.error("Error generating thumbnail for %s: %s", videoid, e)
        traceback.print_exc()
        return None


async def schedule_thumb_updates(
    chat_id: int,
    videoid: str,
    total_seconds: int,
    mystic,           # pyrogram Message object with the stream card
    markup,           # InlineKeyboardMarkup
    caption_fn,       # callable(elapsed_text, duration_text) -> str
    interval: int = 30,
):
    """Background task: refresh the stream card thumbnail every *interval* seconds.

    This gives viewers a live progress bar that moves as the track plays.
    The task is automatically cancelled when the stream ends (mystic is deleted)
    or when the total duration is reached.

    Args:
        chat_id: Telegram chat ID (used for logging only).
        videoid: YouTube video ID for thumbnail generation.
        total_seconds: Total track duration in seconds.
        mystic: The Pyrogram Message object to edit.
        markup: InlineKeyboardMarkup to keep on the edited message.
        caption_fn: Callable that returns the new caption given (elapsed, total).
        interval: How often (seconds) to update the thumbnail.
    """
    # Deferred import to avoid circular dependency at module load time
    from AviaxMusic import app  # noqa: F401 – used implicitly via mystic

    elapsed = 0
    while elapsed < total_seconds:
        await asyncio.sleep(interval)
        elapsed += interval
        if elapsed > total_seconds:
            elapsed = total_seconds

        progress = elapsed / total_seconds if total_seconds > 0 else 0.0
        elapsed_text = seconds_to_min(elapsed)

        try:
            new_thumb = await gen_thumb_with_progress(
                videoid, progress=progress, elapsed_text=elapsed_text, force=True
            )
            if new_thumb is None:
                continue

            caption = caption_fn(elapsed_text, seconds_to_min(total_seconds))

            await mystic.edit_media(
                InputMediaPhoto(media=new_thumb, caption=caption),
                reply_markup=markup,
            )
            _log.debug(
                "[THUMB_UPDATE] chat=%s vidid=%s progress=%.0f%%",
                chat_id, videoid, progress * 100,
            )
        except Exception as e:
            _log.warning("[THUMB_UPDATE] Failed for chat=%s: %s", chat_id, e)
            break  # Stop updates if editing fails (message deleted, etc.)

