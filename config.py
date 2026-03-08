import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")

# Get your token from @BotFather on Telegram.
BOT_TOKEN = getenv("BOT_TOKEN")

# Get your mongo url from cloud.mongodb.com
MONGO_DB_URI = getenv("MONGO_DB_URI", None)

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 999))

# Chat id of a group for logging bot's activities
LOG_GROUP_ID = int(getenv("LOG_GROUP_ID", None))

# Get this value from @MissRose_Bot on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", None))

## Fill these variables if you're deploying on heroku.
# Your heroku app name
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

API_URL = getenv("API_URL", 'https://api.thequickearn.xyz') #youtube song url
VIDEO_API_URL = getenv("VIDEO_API_URL", 'https://api.video.thequickearn.xyz')
API_KEY = getenv("API_KEY", None) # youtube song api key, generate free key or buy paid plan from panel.thequickearn.xyz

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/IamMythwalker/KittyMusic-",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "master")
GIT_TOKEN = getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/CrescentxNetwork")
SUPPORT_GROUP = getenv("SUPPORT_GROUP", "https://t.me/CrescentSupport")

# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

# make your bots privacy from telegra.ph and put your url here 
PRIVACY_LINK = getenv("PRIVACY_LINK", "https://telegra.ph/Privacy-Policy-for-AviaxMusic-08-14")


# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", None)
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", None)


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 25))


# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 2145386496))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes


# Get your pyrogram v2 session from Replit
STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)


BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}

FAILED = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
START_IMG_URL = getenv(
    "START_IMG_URL", "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
)
PING_IMG_URL = getenv(
    "PING_IMG_URL", "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
)
PLAYLIST_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
STATS_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
TELEGRAM_AUDIO_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
TELEGRAM_VIDEO_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
STREAM_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
SOUNCLOUD_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
YOUTUBE_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
SPOTIFY_ARTIST_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
SPOTIFY_ALBUM_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"
SPOTIFY_PLAYLIST_IMG_URL = "http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ"


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))


if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_GROUP:
    if not re.match("(?:http|https)://", SUPPORT_GROUP):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_GROUP url is wrong. Please ensure that it starts with https://"
        )






