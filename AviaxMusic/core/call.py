import asyncio
import os
import random
import signal
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.errors import RPCError
from pyrogram.raw import functions
from pyrogram.raw import types as raw_types
from pyrogram.types import ChatPrivileges, InlineKeyboardMarkup

import config
from AviaxMusic import LOGGER, YouTube, app
from AviaxMusic.misc import db
from AviaxMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    del_rtmp_creds,
    get_lang,
    get_loop,
    get_rtmp_creds,
    group_assistant,
    is_autoend,
    load_rtmp_creds,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
    set_rtmp_creds,
)
from AviaxMusic.utils.exceptions import AssistantErr
from AviaxMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from AviaxMusic.utils.inline.play import stream_markup
from AviaxMusic.utils.stream.autoclear import auto_clean
from AviaxMusic.utils.thumbnails import gen_thumb
from strings import get_string

# In-memory FFmpeg process tracking: {chat_id: asyncio.subprocess.Process}
_active_procs: dict = {}

autoend = {}
counter = {}


async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call:
    """RTMP-based streaming controller.
    Each group chat gets an RTMP ingest URL obtained via
    phone.getGroupCallStreamRtmpUrl and audio/video is piped into it
    by an FFmpeg subprocess."""

    def __init__(self):
        self.userbot1 = Client(
            name="AviaxAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.one = self.userbot1

        self.userbot2 = Client(
            name="AviaxAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.two = self.userbot2

        self.userbot3 = Client(
            name="AviaxAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.three = self.userbot3

        self.userbot4 = Client(
            name="AviaxAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.four = self.userbot4

        self.userbot5 = Client(
            name="AviaxAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )
        self.five = self.userbot5

    async def _get_or_create_rtmp_creds(self, chat_id: int):
        """Return (url, key) for the RTMP ingest endpoint of chat_id.

        If no creds are stored in cache/DB the method will:
          1. Promote the userbot to admin (manage video chats + invite users).
          2. Create an RTMP group call if none is active.
          3. Fetch the RTMP URL/key and persist them.
          4. Make the userbot leave the chat (it is no longer needed).
        """
        creds = await get_rtmp_creds(chat_id)
        if not creds:
            creds = await load_rtmp_creds(chat_id)
        if creds:
            return creds["url"], creds["key"]

        client = await group_assistant(self, chat_id)

        try:
            peer = await client.resolve_peer(chat_id)
        except Exception as exc:
            raise AssistantErr(f"Failed to resolve peer for chat {chat_id}: {exc}")

        # Promote the userbot so it can manage the RTMP stream
        try:
            await app.promote_chat_member(
                chat_id,
                client.id,
                privileges=ChatPrivileges(
                    can_manage_video_chats=True,
                    can_invite_users=True,
                ),
            )
            # Allow Telegram to propagate the admin-rights change
            await asyncio.sleep(2)
        except Exception as exc:
            raise AssistantErr(f"Failed to promote assistant: {exc}")

        # Try to get an existing RTMP URL first
        try:
            result = await client.invoke(
                functions.phone.GetGroupCallStreamRtmpUrl(
                    peer=peer,
                    revoke=False,
                )
            )
            url = result.url
            key = result.key
        except Exception:
            # No active RTMP call — create one
            try:
                await client.invoke(
                    functions.phone.CreateGroupCall(
                        peer=peer,
                        random_id=random.randint(1, 2**31 - 1),
                        rtmp_stream=True,
                    )
                )
                await asyncio.sleep(1)
            except RPCError as exc:
                upper = str(exc).upper()
                if "GROUPCALL_ALREADY_STARTED" in upper or "ALREADY_STARTED" in upper:
                    # A non-RTMP call is active — end it and start an RTMP one
                    try:
                        full = await self._get_full_chat(client, peer)
                        if full and full.full_chat.call:
                            await client.invoke(
                                functions.phone.DiscardGroupCall(
                                    call=full.full_chat.call
                                )
                            )
                            await asyncio.sleep(1)
                    except Exception:
                        pass
                    try:
                        await client.invoke(
                            functions.phone.CreateGroupCall(
                                peer=peer,
                                random_id=random.randint(1, 2**31 - 1),
                                rtmp_stream=True,
                            )
                        )
                        await asyncio.sleep(1)
                    except Exception as exc2:
                        raise AssistantErr(f"Failed to create RTMP call: {exc2}")
                else:
                    raise AssistantErr(f"Failed to create group call: {exc}")
            except Exception as exc:
                raise AssistantErr(f"Failed to create group call: {exc}")

            try:
                result = await client.invoke(
                    functions.phone.GetGroupCallStreamRtmpUrl(
                        peer=peer,
                        revoke=False,
                    )
                )
                url = result.url
                key = result.key
            except Exception as exc2:
                raise AssistantErr(f"Failed to get RTMP credentials: {exc2}")

        await set_rtmp_creds(chat_id, url, key)

        # Userbot is no longer needed — leave the chat
        try:
            await client.leave_chat(chat_id)
        except Exception:
            pass

        return url, key

    async def _get_full_chat(self, client, peer):
        """Return the FullChat object for the given peer (channel or basic group)."""
        try:
            if isinstance(peer, raw_types.InputPeerChannel):
                return await client.invoke(
                    functions.channels.GetFullChannel(
                        channel=raw_types.InputChannel(
                            channel_id=peer.channel_id,
                            access_hash=peer.access_hash,
                        )
                    )
                )
            if isinstance(peer, raw_types.InputPeerChat):
                return await client.invoke(
                    functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
        except Exception:
            pass
        return None

    def is_stream_active(self, chat_id: int) -> bool:
        """Return True if an FFmpeg RTMP process is currently running for this chat."""
        proc = _active_procs.get(chat_id)
        return proc is not None and proc.returncode is None

    def _build_ffmpeg_cmd(
        self,
        input_path: str,
        rtmp_url: str,
        rtmp_key: str,
        video: bool = False,
        ss=None,
        to=None,
    ):
        """Return the FFmpeg argv list for an RTMP stream."""
        full_url = f"{rtmp_url}{rtmp_key}"
        cmd = ["ffmpeg", "-re", "-loglevel", "quiet"]

        if ss is not None:
            cmd += ["-ss", str(ss)]
        cmd += ["-i", input_path]
        if to is not None:
            cmd += ["-to", str(to)]

        if video:
            cmd += [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-b:v", "2000k",
                "-maxrate", "2000k",
                "-bufsize", "4000k",
                "-pix_fmt", "yuv420p",
                "-g", "50",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-f", "flv",
                full_url,
            ]
        else:
            cmd += [
                "-vn",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-f", "flv",
                full_url,
            ]

        return cmd

    async def _start_ffmpeg(self, chat_id: int, cmd: list):
        await self._kill_proc(chat_id)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _active_procs[chat_id] = proc

        asyncio.create_task(self._monitor_stream(chat_id, proc))
        return proc

    async def _kill_proc(self, chat_id: int):
        proc = _active_procs.pop(chat_id, None)
        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except Exception:
                pass

    async def _monitor_stream(self, chat_id: int, proc):
        try:
            await proc.communicate()
        except Exception:
            pass

        if _active_procs.get(chat_id) is proc:
            _active_procs.pop(chat_id, None)
            await self.change_stream(None, chat_id)

    async def pause_stream(self, chat_id: int):
        proc = _active_procs.get(chat_id)
        if proc is not None and proc.returncode is None:
            try:
                proc.send_signal(signal.SIGSTOP)
            except Exception:
                pass

    async def resume_stream(self, chat_id: int):
        proc = _active_procs.get(chat_id)
        if proc is not None and proc.returncode is None:
            try:
                proc.send_signal(signal.SIGCONT)
            except Exception:
                pass

    async def stop_stream(self, chat_id: int):
        try:
            await _clear_(chat_id)
            await self._kill_proc(chat_id)
        except Exception:
            pass

    async def stop_stream_force(self, chat_id: int):
        try:
            await _clear_(chat_id)
            await self._kill_proc(chat_id)
        except Exception:
            pass

    async def force_stop_stream(self, chat_id: int):
        try:
            check = db.get(chat_id)
            check.pop(0)
        except Exception:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await self._kill_proc(chat_id)

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        creds = await get_rtmp_creds(chat_id)
        if creds:
            rtmp_url, rtmp_key = creds["url"], creds["key"]
        else:
            rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)

        cmd = self._build_ffmpeg_cmd(link, rtmp_url, rtmp_key, video=bool(video))
        await self._start_ffmpeg(chat_id, cmd)

    async def seek_stream(
        self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str
    ):
        creds = await get_rtmp_creds(chat_id)
        if creds:
            rtmp_url, rtmp_key = creds["url"], creds["key"]
        else:
            rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)

        video = mode == "video"
        cmd = self._build_ffmpeg_cmd(
            file_path, rtmp_url, rtmp_key, video=video, ss=to_seek, to=duration
        )
        await self._start_ffmpeg(chat_id, cmd)

    async def speedup_stream(
        self, chat_id: int, file_path: str, speed: str, playing: list
    ):
        if str(speed) != str("1.0"):
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == str("0.5"):
                    vs = 2.0
                elif str(speed) == str("0.75"):
                    vs = 1.35
                elif str(speed) == str("1.5"):
                    vs = 0.68
                elif str(speed) == str("2.0"):
                    vs = 0.5
                else:
                    raise AssistantErr(f"Unsupported speed value: {speed}")
                sp = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-i", file_path,
                    "-filter:v", f"setpts={vs}*PTS",
                    "-filter:a", f"atempo={speed}",
                    out,
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await sp.communicate()
        else:
            out = file_path

        dur = await asyncio.get_event_loop().run_in_executor(
            None, check_duration, out
        )
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)

        creds = await get_rtmp_creds(chat_id)
        if creds:
            rtmp_url, rtmp_key = creds["url"], creds["key"]
        else:
            rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)

        video = playing[0]["streamtype"] == "video"
        cmd = self._build_ffmpeg_cmd(
            out, rtmp_url, rtmp_key, video=video, ss=played, to=duration
        )

        if str(db[chat_id][0]["file"]) == str(file_path):
            await self._start_ffmpeg(chat_id, cmd)
        else:
            raise AssistantErr("Umm")

        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        language = await get_lang(chat_id)
        _ = get_string(language)

        try:
            rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)
        except AssistantErr:
            raise
        except Exception as exc:
            raise AssistantErr(f"RTMP setup error: {exc}")

        cmd = self._build_ffmpeg_cmd(link, rtmp_url, rtmp_key, video=bool(video))
        await self._start_ffmpeg(chat_id, cmd)

        # Verify the stream actually started; if FFmpeg exited quickly the
        # RTMP credentials are likely stale or revoked — clear them and retry once.
        # 3 s is enough for FFmpeg to fail fast on a bad RTMP URL while still
        # being well below the time a successful stream takes to exit.
        await asyncio.sleep(3)
        if not self.is_stream_active(chat_id):
            await del_rtmp_creds(chat_id)
            try:
                rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)
            except AssistantErr:
                raise
            except Exception as exc:
                raise AssistantErr(f"RTMP setup error on retry: {exc}")
            cmd = self._build_ffmpeg_cmd(link, rtmp_url, rtmp_key, video=bool(video))
            await self._start_ffmpeg(chat_id, cmd)
            # Shorter wait on the second attempt
            await asyncio.sleep(2)
            if not self.is_stream_active(chat_id):
                raise AssistantErr(_["call_8"])

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

    async def change_stream(self, client, chat_id: int):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                return
        except Exception:
            try:
                await _clear_(chat_id)
            except Exception:
                pass
            return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0
            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = str(streamtype) == "video"

            creds = await get_rtmp_creds(chat_id)
            if creds:
                rtmp_url, rtmp_key = creds["url"], creds["key"]
            else:
                try:
                    rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(
                        original_chat_id, text=_["call_6"]
                    )
                cmd = self._build_ffmpeg_cmd(link, rtmp_url, rtmp_key, video=video)
                try:
                    await self._start_ffmpeg(chat_id, cmd)
                except Exception:
                    return await app.send_message(
                        original_chat_id, text=_["call_6"]
                    )
                img = await gen_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=video,
                    )
                except Exception:
                    return await mystic.edit_text(
                        _["call_6"], disable_web_page_preview=True
                    )
                cmd = self._build_ffmpeg_cmd(file_path, rtmp_url, rtmp_key, video=video)
                try:
                    await self._start_ffmpeg(chat_id, cmd)
                except Exception:
                    return await app.send_message(
                        original_chat_id, text=_["call_6"]
                    )
                img = await gen_thumb(videoid)
                button = stream_markup(_, chat_id)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                cmd = self._build_ffmpeg_cmd(videoid, rtmp_url, rtmp_key, video=video)
                try:
                    await self._start_ffmpeg(chat_id, cmd)
                except Exception:
                    return await app.send_message(
                        original_chat_id, text=_["call_6"]
                    )
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                cmd = self._build_ffmpeg_cmd(queued, rtmp_url, rtmp_key, video=video)
                try:
                    await self._start_ffmpeg(chat_id, cmd)
                except Exception:
                    return await app.send_message(
                        original_chat_id, text=_["call_6"]
                    )
                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.TELEGRAM_AUDIO_URL
                        if str(streamtype) == "audio"
                        else config.TELEGRAM_VIDEO_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_GROUP,
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_GROUP,
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                else:
                    img = await gen_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        from AviaxMusic.core.userbot import assistants
        return str(len(assistants))

    async def stream_call(self, link: str):
        pass

    async def call_listeners(self, chat_id: int):
        """Participant counting is not available via RTMP; returns empty list.
        The auto-end feature will not trigger based on listener count in RTMP mode."""
        return []

    async def start(self):
        LOGGER(__name__).info("Starting RTMP streaming clients...")
        if config.STRING1:
            await self.userbot1.start()
        if config.STRING2:
            await self.userbot2.start()
        if config.STRING3:
            await self.userbot3.start()
        if config.STRING4:
            await self.userbot4.start()
        if config.STRING5:
            await self.userbot5.start()

    async def decorators(self):
        pass


Aviax = Call()
