from pyrogram import filters
from pyrogram.types import Message

from AviaxMusic import LOGGER, app
from AviaxMusic.core.call import Aviax
from AviaxMusic.utils.database import set_loop
from AviaxMusic.utils.decorators import AdminRightsCheck
from AviaxMusic.utils.inline import close_markup
from config import BANNED_USERS

_log = LOGGER(__name__)


@app.on_message(
    filters.command(["end", "stop", "cend", "cstop"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def stop_music(cli, message: Message, _, chat_id):
    _log.debug("[STOP] /stop or /end called for chat_id=%s by user=%s", chat_id, message.from_user.id)
    try:
        await set_loop(chat_id, 0)
        await Aviax.stop_stream(chat_id)
        _log.info("[STOP] Stream stopped successfully for chat_id=%s", chat_id)
    except Exception as e:
        _log.error("[STOP] Error while stopping stream for chat_id=%s: %s", chat_id, e)
    await message.reply_text(
        _["admin_5"].format(message.from_user.mention), reply_markup=close_markup(_)
    )
