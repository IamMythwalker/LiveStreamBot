from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

answer = []

answer.extend(
    [
        InlineQueryResultArticle(
            title="Pᴀᴜsᴇ",
            description=f"ᴩᴀᴜsᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
            thumb_url="http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ",
            input_message_content=InputTextMessageContent("/pause"),
        ),
        InlineQueryResultArticle(
            title="Rᴇsᴜᴍᴇ",
            description=f"ʀᴇsᴜᴍᴇ ᴛʜᴇ ᴩᴀᴜsᴇᴅ sᴛʀᴇᴀᴍ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
            thumb_url="http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ",
            input_message_content=InputTextMessageContent("/resume"),
        ),
        InlineQueryResultArticle(
            title="Sᴋɪᴩ",
            description=f"sᴋɪᴩ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ ᴀɴᴅ ᴍᴏᴠᴇs ᴛᴏ ᴛʜᴇ ɴᴇxᴛ sᴛʀᴇᴀᴍ.",
            thumb_url="http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ",
            input_message_content=InputTextMessageContent("/skip"),
        ),
        InlineQueryResultArticle(
            title="Eɴᴅ",
            description="ᴇɴᴅ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
            thumb_url="http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ",
            input_message_content=InputTextMessageContent("/end"),
        ),
        InlineQueryResultArticle(
            title="Sʜᴜғғʟᴇ",
            description="sʜᴜғғʟᴇ ᴛʜᴇ ǫᴜᴇᴜᴇᴅ sᴏɴɢs ɪɴ ᴩʟᴀʏʟɪsᴛ.",
            thumb_url="http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ",
            input_message_content=InputTextMessageContent("/shuffle"),
        ),
        InlineQueryResultArticle(
            title="Lᴏᴏᴩ",
            description="ʟᴏᴏᴩ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ ᴛʀᴀᴄᴋ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
            thumb_url="http://telegraph.controller.bot/files/7994865408/AgACAgUAAxkBAAID52mmsJp71qEEpXWN4um1zY6yUqSJAAJiD2sbNFkxVdj348mCgd56AQADAgADeAADOgQ",
            input_message_content=InputTextMessageContent("/loop 3"),
        ),
    ]
)
