import asyncio
import os
import random
import signal
import time
from datetime import datetime, timedelta
from typing import Optional, Union

from pyrogram import Client
from pyrogram.raw import functions
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

_log = LOGGER(__name__)

# In-memory FFmpeg process tracking: {chat_id: asyncio.subprocess.Process}
_active_procs: dict = {}

# Track stream start times for accurate position calculation: {chat_id: (start_time, offset_seconds)}
_stream_start: dict = {}

# Track paused positions: {chat_id: paused_seconds}
_paused_pos: dict = {}

# Explicit stop flag to prevent _monitor_stream from restarting after /stop or /end
_stopped: set = set()

# Strong references to fire-and-forget tasks so they are not garbage-collected
# before they finish, which would cause "Task exception was never retrieved".
_background_tasks: set = set()

autoend = {}
counter = {}


def _on_task_done(task: asyncio.Task) -> None:
    """Done-callback: log any exception that escaped a background task."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _log.error(
            "[TASK] Unhandled exception in background task %r: %s",
            task.get_name(), exc, exc_info=(type(exc), exc, exc.__traceback__),
        )


def _create_background_task(coro, *, name: Optional[str] = None) -> asyncio.Task:
    """Schedule *coro* as a fire-and-forget background task.

    Keeps a strong reference in *_background_tasks* so the task is not
    garbage-collected before it finishes, and logs any unhandled exception
    that escapes the coroutine via :func:`_on_task_done`.
    """
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    task.add_done_callback(_on_task_done)
    return task


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

        Tries cached credentials first, then fetches/creates via Telegram.
        Raises AssistantErr with a user-visible ``call_11`` message when the
        live stream is not running and credentials cannot be obtained.
        """
        creds = await get_rtmp_creds(chat_id)
        if not creds:
            creds = await load_rtmp_creds(chat_id)
        if creds:
            _log.debug("[RTMP] Using cached credentials for chat_id=%s", chat_id)
            return creds["url"], creds["key"]

        _log.info("[RTMP] No cached credentials for chat_id=%s – fetching via assistant", chat_id)
        client = await group_assistant(self, chat_id)

        try:
            peer = await client.resolve_peer(chat_id)
        except Exception as exc:
            _log.error("[RTMP] Failed to resolve peer for chat_id=%s: %s", chat_id, exc)
            raise AssistantErr(f"Failed to resolve peer for chat {chat_id}: {exc}")

        try:
            result = await client.invoke(
                functions.phone.GetGroupCallStreamRtmpUrl(
                    peer=peer,
                    revoke=False,
                )
            )
            url = result.url
            key = result.key
            _log.info("[RTMP] Fetched existing RTMP credentials for chat_id=%s", chat_id)
        except Exception as e1:
            _log.warning("[RTMP] GetGroupCallStreamRtmpUrl failed for chat_id=%s: %s – trying CreateGroupCall", chat_id, e1)
            try:
                await client.invoke(
                    functions.phone.CreateGroupCall(
                        peer=peer,
                        random_id=random.randint(1, 2**31 - 1),
                        rtmp_stream=True,
                    )
                )
                await asyncio.sleep(1)
                result = await client.invoke(
                    functions.phone.GetGroupCallStreamRtmpUrl(
                        peer=peer,
                        revoke=False,
                    )
                )
                url = result.url
                key = result.key
                _log.info("[RTMP] Created new RTMP live stream for chat_id=%s", chat_id)
            except Exception as exc2:
                _log.error("[RTMP] Could not create RTMP stream for chat_id=%s: %s", chat_id, exc2)
                # Send a human-readable notification – translated via the chat's language
                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                    await app.send_message(chat_id, _["call_11"])
                except Exception:
                    pass
                raise AssistantErr(f"Failed to get RTMP credentials: {exc2}")

        await set_rtmp_creds(chat_id, url, key)
        return url, key

    def _build_ffmpeg_cmd(
        self,
        input_path: str,
        rtmp_url: str,
        rtmp_key: str,
        video: bool = False,
        ss=None,
        to=None,
    ):
        """Return the FFmpeg argv list for an RTMP stream.

        Low-latency tuning:
        - probesize / analyzeduration cut down the input-analysis phase that
          causes the initial buffer pause.
        - thread_queue_size avoids packet-queue overflows on fast sources.
        - fflags +genpts / flush_packets 1 ensure clean timestamps at every
          restart (seek / resume) so viewers don't see buffering artefacts.
        - tune zerolatency makes x264 emit frames immediately rather than
          buffering a full GOP before flushing.
        """
        import logging as _logging  # noqa: PLC0415 – local to avoid shadowing module-level LOGGER
        full_url = f"{rtmp_url}{rtmp_key}"

        # Verbosity: quiet in production, verbose when debug logging is active
        loglevel = "warning" if _logging.getLogger().isEnabledFor(_logging.DEBUG) else "quiet"

        cmd = [
            "ffmpeg",
            "-re",                      # read input at native rate (crucial for RTMP)
            "-fflags", "+genpts",        # regenerate PTS – avoids timestamp gaps on restart
            "-probesize", "500000",      # 500 KB probe (default 5 MB) → faster open
            "-analyzeduration", "500000", # 0.5 s analysis (default 5 s) → faster start
            "-loglevel", loglevel,
        ]

        if ss is not None:
            cmd += ["-ss", str(ss)]
        cmd += ["-i", input_path]
        if to is not None:
            cmd += ["-to", str(to)]

        if video:
            cmd += [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-tune", "zerolatency",  # flush encoded frames without extra buffering
                "-b:v", "2000k",
                "-maxrate", "2000k",
                "-bufsize", "4000k",
                "-pix_fmt", "yuv420p",
                "-g", "50",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-flush_packets", "1",   # push every packet immediately
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
                "-flush_packets", "1",
                "-f", "flv",
                full_url,
            ]

        _log.debug("[FFMPEG] cmd: %s", " ".join(cmd))
        return cmd

    async def _start_ffmpeg(self, chat_id: int, cmd: list):
        await self._kill_proc(chat_id)

        _log.debug("[FFMPEG] Starting process for chat_id=%s", chat_id)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,   # capture stderr for debug logging
        )
        _active_procs[chat_id] = proc
        _stream_start[chat_id] = time.monotonic()

        _create_background_task(self._monitor_stream(chat_id, proc), name=f"monitor-{chat_id}")
        _create_background_task(self._log_ffmpeg_stderr(chat_id, proc), name=f"stderr-{chat_id}")
        return proc

    async def _log_ffmpeg_stderr(self, chat_id: int, proc):
        """Read and debug-log FFmpeg's stderr output."""
        try:
            async for line in proc.stderr:
                decoded = line.decode(errors="replace").rstrip()
                if decoded:
                    _log.debug("[FFMPEG stderr] chat=%s | %s", chat_id, decoded)
        except Exception:
            pass

    async def _kill_proc(self, chat_id: int):
        proc = _active_procs.pop(chat_id, None)
        _stream_start.pop(chat_id, None)
        if proc is not None and proc.returncode is None:
            _log.debug("[FFMPEG] Terminating process for chat_id=%s", chat_id)
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

        try:
            # Only trigger auto-advance if this proc is still the registered one
            # AND the chat hasn't been explicitly stopped
            if _active_procs.get(chat_id) is proc and chat_id not in _stopped:
                _active_procs.pop(chat_id, None)
                _stream_start.pop(chat_id, None)
                _log.debug("[MONITOR] Stream ended normally for chat_id=%s – advancing queue", chat_id)
                await self.change_stream(None, chat_id)
            else:
                _log.debug("[MONITOR] Stream ended for chat_id=%s – no queue advance (stopped or replaced)", chat_id)
        except Exception as e:
            _log.error("[MONITOR] Error advancing queue for chat_id=%s: %s", chat_id, e)
        finally:
            _stopped.discard(chat_id)

    def _get_elapsed_seconds(self, chat_id: int) -> float:
        """Return seconds elapsed since the current FFmpeg process started."""
        start = _stream_start.get(chat_id)
        if start is None:
            return 0.0
        return time.monotonic() - start

    async def pause_stream(self, chat_id: int):
        """Pause playback by freezing the FFmpeg process (SIGSTOP).

        The current playback position is recorded so that resume can restart
        FFmpeg from exactly where we paused, avoiding the buffering artefact
        that occurs when the RTMP server's buffer drains during a freeze.
        """
        proc = _active_procs.get(chat_id)
        if proc is not None and proc.returncode is None:
            # Record position so resume can restart from here
            try:
                played_so_far = db[chat_id][0].get("played", 0)
                elapsed = self._get_elapsed_seconds(chat_id)
                _paused_pos[chat_id] = played_so_far + elapsed
                _log.debug("[PAUSE] chat_id=%s paused at %.1f s", chat_id, _paused_pos[chat_id])
            except Exception:
                pass
            try:
                proc.send_signal(signal.SIGSTOP)
            except Exception as e:
                _log.warning("[PAUSE] SIGSTOP failed for chat_id=%s: %s", chat_id, e)

    async def resume_stream(self, chat_id: int):
        """Resume playback.

        Instead of simply sending SIGCONT (which leaves a data gap in the RTMP
        stream and causes viewer-side buffering), we restart FFmpeg from the
        saved pause position.  Falls back to SIGCONT if no position was saved
        or if the file info is unavailable.
        """
        paused_at = _paused_pos.pop(chat_id, None)
        proc = _active_procs.get(chat_id)

        if paused_at is not None and proc is not None:
            # Try to restart from the saved position (preferred – no RTMP gap)
            try:
                playing = db.get(chat_id)
                if playing:
                    file_path = playing[0].get("speed_path") or playing[0]["file"]
                    if "live_" not in file_path and "index_" not in file_path:
                        creds = await get_rtmp_creds(chat_id)
                        if creds:
                            rtmp_url, rtmp_key = creds["url"], creds["key"]
                        else:
                            rtmp_url, rtmp_key = await self._get_or_create_rtmp_creds(chat_id)
                        duration = playing[0].get("dur", "00:00")
                        video = playing[0].get("streamtype") == "video"
                        seek_to = seconds_to_min(int(paused_at))
                        cmd = self._build_ffmpeg_cmd(
                            file_path, rtmp_url, rtmp_key, video=video,
                            ss=seek_to, to=duration
                        )
                        db[chat_id][0]["played"] = int(paused_at)
                        _log.info("[RESUME] Restarting FFmpeg from %.1f s for chat_id=%s", paused_at, chat_id)
                        await self._start_ffmpeg(chat_id, cmd)
                        return
            except Exception as e:
                _log.warning("[RESUME] Restart-from-position failed for chat_id=%s: %s – falling back to SIGCONT", chat_id, e)

        # Fallback: thaw the frozen process
        if proc is not None and proc.returncode is None:
            _log.debug("[RESUME] SIGCONT for chat_id=%s", chat_id)
            try:
                proc.send_signal(signal.SIGCONT)
            except Exception as e:
                _log.warning("[RESUME] SIGCONT failed for chat_id=%s: %s", chat_id, e)

    async def stop_stream(self, chat_id: int):
        _log.info("[STOP] Stopping stream for chat_id=%s", chat_id)
        _stopped.add(chat_id)
        _paused_pos.pop(chat_id, None)
        try:
            await _clear_(chat_id)
            await self._kill_proc(chat_id)
        except Exception as e:
            _log.error("[STOP] Error stopping stream for chat_id=%s: %s", chat_id, e)

    async def stop_stream_force(self, chat_id: int):
        _log.info("[STOP_FORCE] Force-stopping stream for chat_id=%s", chat_id)
        _stopped.add(chat_id)
        _paused_pos.pop(chat_id, None)
        try:
            await _clear_(chat_id)
            await self._kill_proc(chat_id)
        except Exception as e:
            _log.error("[STOP_FORCE] Error for chat_id=%s: %s", chat_id, e)

    async def force_stop_stream(self, chat_id: int):
        _log.info("[FORCE_STOP] force_stop_stream for chat_id=%s", chat_id)
        _stopped.add(chat_id)
        _paused_pos.pop(chat_id, None)
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

    async def _try_promote_assistant(self, chat_id: int, client) -> None:
        """Try to promote the assistant account with admin + manage live stream
        permissions in the given chat.  Failures are logged but not raised since
        the bot may already have insufficient rights to promote others."""
        try:
            assistant_id = client.me.id if client.me else None
            if not assistant_id:
                _log.warning("[PROMOTE] Could not determine assistant user id for chat %s", chat_id)
                return
            await app.promote_chat_member(
                chat_id,
                assistant_id,
                privileges=ChatPrivileges(
                    can_manage_chat=True,
                    can_manage_video_chats=True,
                    can_invite_users=True,
                ),
            )
            _log.info(
                "[PROMOTE] Promoted assistant %s as admin in chat %s",
                assistant_id, chat_id,
            )
        except Exception as e:
            assistant_id = client.me.id if client.me else "unknown"
            _log.warning(
                "[PROMOTE] Could not promote assistant %s in chat %s: %s",
                assistant_id, chat_id, e,
            )

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
            raise AssistantErr(_["call_11"])

        # Promote the assistant so it can manage the live stream
        try:
            assistant_client = await group_assistant(self, chat_id)
            _create_background_task(self._try_promote_assistant(chat_id, assistant_client), name=f"promote-{chat_id}")
        except Exception as e:
            _log.warning("[JOIN] Could not get assistant for promotion in chat %s: %s", chat_id, e)

        _log.info("[JOIN] Starting RTMP stream for chat_id=%s (video=%s)", chat_id, bool(video))
        cmd = self._build_ffmpeg_cmd(link, rtmp_url, rtmp_key, video=bool(video))
        await self._start_ffmpeg(chat_id, cmd)

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
                # If the local file no longer exists (e.g. cleaned up) and this
                # is a YouTube video (not telegram/soundcloud), re-download it.
                if not os.path.isfile(queued) and videoid not in ("telegram", "soundcloud"):
                    mystic = await app.send_message(original_chat_id, _["call_7"])
                    try:
                        file_path, direct = await YouTube.download(
                            videoid,
                            mystic,
                            videoid=True,
                            video=video,
                        )
                        if not file_path:
                            return await mystic.edit_text(
                                _["call_6"], disable_web_page_preview=True
                            )
                        db[chat_id][0]["file"] = file_path
                        queued = file_path
                    except Exception as redownload_err:
                        _log.warning(
                            "[CHANGE_STREAM] Re-download failed for video %s in chat %s: %s",
                            videoid, chat_id, redownload_err,
                        )
                        return await app.send_message(
                            original_chat_id, text=_["call_6"]
                        )
                    await mystic.delete()
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
