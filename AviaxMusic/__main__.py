import asyncio
import importlib
import threading

from flask import Flask
from pyrogram import idle

import config
from AviaxMusic import LOGGER, app, userbot
from AviaxMusic.core.call import Aviax
from AviaxMusic.misc import sudo
from AviaxMusic.plugins import ALL_MODULES
from AviaxMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS

# Flask app setup
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running."

def run_flask():
    """Run Flask server on all interfaces at port 8080."""
    flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("AviaxMusic.plugins" + all_module)
    LOGGER("AviaxMusic.plugins").info("Successfully Imported Modules...")
    await userbot.start()
    await Aviax.start()
    await Aviax.decorators()
    LOGGER("AviaxMusic").info(
        "\x41\x76\x69\x61\x78\x20\x4d\x75\x73\x69\x63\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e\x0a\x0a\x44\x6f\x6e\x27\x74\x20\x66\x6f\x72\x67\x65\x74\x20\x74\x6f\x20\x76\x69\x73\x69\x74\x20\x40\x41\x76\x69\x61\x78\x4f\x66\x66\x69\x63\x69\x61\x6c"
    )

    # Start Flask server in a background thread
    threading.Thread(target=run_flask, daemon=True).start()
    LOGGER("AviaxMusic").info("Flask server started on 0.0.0.0:8080")

    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("AviaxMusic").info("Stopping Aviax Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())