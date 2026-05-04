"""Conversation flow for picking a model, collecting inputs, and generating.

Flow (each step driven by ConversationHandler state):

    /menu / /start  -> shows the 4-mode menu (entry button outside the
                       ConversationHandler).
    user taps mode  -> CHOOSING_MODEL state, bot asks "Pilih model" with
                       inline buttons for the models in that mode.
    user taps model -> AWAITING_PROMPT state, bot asks for the text prompt.
    user sends text -> AWAITING_NEGATIVE if model supports it, else next.
    /skip           -> skips an optional step.
    user uploads    -> AWAITING_START_IMAGE / AWAITING_END_IMAGE /
                       AWAITING_REFERENCE_VIDEO depending on the model.
    all collected   -> kicks off generation in a background task and edits
                       a single status message until the result is ready.
    /cancel         -> abort the conversation at any point.
    /stop           -> abort an in-flight generation (uses cancel_event).
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import Config
from bot.freepik_client import (
    FreepikClient,
    extract_task_id,
    poll_until_done,
)
from bot.freepik_models import (
    Mode,
    Model,
    build_post_body,
    extract_result_urls,
    get_model,
    models_for_mode,
)
from bot.storage import Storage

logger = logging.getLogger(__name__)


CHOOSING_MODEL = 1
AWAITING_PROMPT = 2
AWAITING_NEGATIVE = 3
AWAITING_START_IMAGE = 4
AWAITING_END_IMAGE = 5
AWAITING_REFERENCE_VIDEO = 6


_MODE_LABELS: dict[Mode, str] = {
    "text-to-image": "🖼 Text → Image",
    "text-to-video": "🎬 Text → Video",
    "image-to-video": "🎞 Image → Video",
    "motion-control": "💃 Motion Control",
}


@dataclass
class Job:
    """Per-conversation job state, parked in user_data while the user replies."""

    mode: Mode | None = None
    model_id: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    duration: str | None = None
    generate_audio: bool = True
    start_image_url: str | None = None
    end_image_url: str | None = None
    reference_video_url: str | None = None


def _job(context: ContextTypes.DEFAULT_TYPE) -> Job:
    if "job" not in context.user_data:
        context.user_data["job"] = Job()
    return context.user_data["job"]


def _reset_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["job"] = Job()


def _model_keyboard(mode: Mode) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for m in models_for_mode(mode):
        rows.append([InlineKeyboardButton(m.label, callback_data=f"model:{m.id}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="back:mode")])
    return InlineKeyboardMarkup(rows)


def _mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(_MODE_LABELS["text-to-image"], callback_data="mode:text-to-image"),
                InlineKeyboardButton(_MODE_LABELS["text-to-video"], callback_data="mode:text-to-video"),
            ],
            [
                InlineKeyboardButton(_MODE_LABELS["image-to-video"], callback_data="mode:image-to-video"),
                InlineKeyboardButton(_MODE_LABELS["motion-control"], callback_data="mode:motion-control"),
            ],
        ]
    )


# ---------------------------------------------------------------- entrypoints


async def on_mode_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or not query.data:
        return ConversationHandler.END
    await query.answer()
    mode = query.data.split(":", 1)[1]
    if mode not in _MODE_LABELS:
        return ConversationHandler.END
    job = _job(context)
    job.mode = mode  # type: ignore[assignment]
    job.model_id = None
    await query.edit_message_text(
        f"{_MODE_LABELS[mode]} — pilih model:",  # type: ignore[index]
        reply_markup=_model_keyboard(mode),  # type: ignore[arg-type]
    )
    return CHOOSING_MODEL


async def on_back_to_modes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("Pilih mode:", reply_markup=_mode_keyboard())
    return CHOOSING_MODEL


async def on_model_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or not query.data:
        return ConversationHandler.END
    await query.answer()
    model_id = query.data.split(":", 1)[1]
    model = get_model(model_id)
    if model is None:
        await query.edit_message_text("Model tidak dikenal. /menu untuk mulai lagi.")
        return ConversationHandler.END

    job = _job(context)
    job.model_id = model.id
    # Prefill defaults from the first option of each setting
    job.aspect_ratio = model.aspect_ratio_options[0] if model.aspect_ratio_options else None
    job.resolution = model.resolution_options[0] if model.resolution_options else None
    job.duration = model.duration_options[0] if model.duration_options else None

    note_lines = [
        f"*{model.label}* dipilih.",
        f"_{model.description}_",
        "",
        "Sekarang kirim *prompt* Anda sebagai pesan teks.",
    ]
    if model.aspect_ratio_options:
        note_lines.append(f"Aspect ratio default: `{job.aspect_ratio}`")
    if model.resolution_options:
        note_lines.append(f"Resolution default: `{job.resolution}`")
    if model.duration_options:
        note_lines.append(f"Duration default: `{job.duration}s`")
    note_lines.append("\nKetik /cancel kapan saja untuk batal.")
    await query.edit_message_text("\n".join(note_lines), parse_mode="Markdown")
    return AWAITING_PROMPT


# ---------------------------------------------------------------- prompt flow


async def on_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if msg is None or not msg.text:
        return AWAITING_PROMPT
    job = _job(context)
    if job.model_id is None:
        await msg.reply_text("Mulai dari /menu dulu.")
        return ConversationHandler.END
    job.prompt = msg.text.strip()
    return await _next_after_prompt(update, context)


async def _next_after_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    job = _job(context)
    model = get_model(job.model_id or "")
    msg = update.effective_message
    if model is None or msg is None:
        return ConversationHandler.END

    if model.supports.negative_prompt and job.negative_prompt is None:
        await msg.reply_text(
            "Optional: kirim *negative prompt* (hal yang TIDAK ingin muncul) "
            "atau /skip untuk lewati.",
            parse_mode="Markdown",
        )
        return AWAITING_NEGATIVE

    return await _next_after_negative(update, context)


async def on_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if msg is None or not msg.text:
        return AWAITING_NEGATIVE
    job = _job(context)
    job.negative_prompt = msg.text.strip()
    return await _next_after_negative(update, context)


async def on_skip_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    job = _job(context)
    job.negative_prompt = ""
    return await _next_after_negative(update, context)


async def _next_after_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    job = _job(context)
    model = get_model(job.model_id or "")
    msg = update.effective_message
    if model is None or msg is None:
        return ConversationHandler.END

    if model.supports.start_image and not job.start_image_url:
        label = (
            "character image" if model.mode == "motion-control" else "start frame image"
        )
        await msg.reply_text(
            f"Kirim {label} (foto atau dokumen image). "
            "Maksimum 10 MB."
        )
        return AWAITING_START_IMAGE

    if model.supports.end_image and not job.end_image_url:
        await msg.reply_text(
            "Optional: kirim *end frame image* (foto/dokumen) atau /skip.",
            parse_mode="Markdown",
        )
        return AWAITING_END_IMAGE

    if model.supports.reference_video and not job.reference_video_url:
        await msg.reply_text(
            "Kirim *reference motion video* (mp4/webm/mov, maks 15 MB). "
            "Catatan: beberapa endpoint Freepik wajib URL publik — kalau "
            "base64 ditolak, host video di tempat lain dan paste URL pakai "
            "/seturl <url>.",
            parse_mode="Markdown",
        )
        return AWAITING_REFERENCE_VIDEO

    return await _kick_off_generation(update, context)


# ---------------------------------------------------------------- media intake


async def _photo_or_document_to_data_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str
) -> tuple[str | None, str | None]:
    """Returns (data_url, error). Caller decides how to display the error."""
    msg = update.effective_message
    if msg is None:
        return None, "no_message"

    config: Config = context.application.bot_data["config"]
    cap = config.max_image_bytes if kind == "image" else config.max_video_bytes

    file_id: str | None = None
    mime: str = "image/jpeg" if kind == "image" else "video/mp4"

    if msg.photo:
        # The largest variant is last.
        file_id = msg.photo[-1].file_id
        mime = "image/jpeg"
    elif msg.document:
        file_id = msg.document.file_id
        if msg.document.mime_type:
            mime = msg.document.mime_type
        if (
            kind == "image"
            and not (mime.startswith("image/") or msg.document.mime_type is None)
        ):
            return None, f"file_bukan_image (mime={mime})"
        if (
            kind == "video"
            and not (mime.startswith("video/") or msg.document.mime_type is None)
        ):
            return None, f"file_bukan_video (mime={mime})"
    elif kind == "video" and msg.video:
        file_id = msg.video.file_id
        mime = msg.video.mime_type or "video/mp4"
    elif kind == "video" and msg.animation:
        file_id = msg.animation.file_id
        mime = msg.animation.mime_type or "video/mp4"
    else:
        return None, "tidak_ada_file"

    file = await context.bot.get_file(file_id)
    if file.file_size and file.file_size > cap:
        cap_mb = cap / (1024 * 1024)
        actual_mb = file.file_size / (1024 * 1024)
        return None, (
            f"file_terlalu_besar ({actual_mb:.1f} MB). Maksimum {cap_mb:.1f} MB."
        )

    buf = await file.download_as_bytearray()
    if len(buf) > cap:
        cap_mb = cap / (1024 * 1024)
        actual_mb = len(buf) / (1024 * 1024)
        return None, (
            f"file_terlalu_besar ({actual_mb:.1f} MB). Maksimum {cap_mb:.1f} MB."
        )

    b64 = base64.b64encode(bytes(buf)).decode("ascii")
    return f"data:{mime};base64,{b64}", None


async def on_start_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if msg is None:
        return AWAITING_START_IMAGE
    data_url, err = await _photo_or_document_to_data_url(update, context, "image")
    if err:
        await msg.reply_text(f"❌ {err}\nCoba lagi atau /cancel.")
        return AWAITING_START_IMAGE
    job = _job(context)
    job.start_image_url = data_url
    return await _next_after_negative(update, context)


async def on_end_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if msg is None:
        return AWAITING_END_IMAGE
    data_url, err = await _photo_or_document_to_data_url(update, context, "image")
    if err:
        await msg.reply_text(f"❌ {err}\nCoba lagi atau /skip untuk lewati.")
        return AWAITING_END_IMAGE
    job = _job(context)
    job.end_image_url = data_url
    return await _next_after_negative(update, context)


async def on_skip_end_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    job = _job(context)
    job.end_image_url = ""
    return await _next_after_negative(update, context)


async def on_reference_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if msg is None:
        return AWAITING_REFERENCE_VIDEO
    data_url, err = await _photo_or_document_to_data_url(update, context, "video")
    if err:
        await msg.reply_text(f"❌ {err}\nCoba lagi atau /cancel.")
        return AWAITING_REFERENCE_VIDEO
    job = _job(context)
    job.reference_video_url = data_url
    return await _next_after_negative(update, context)


async def on_seturl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lets the user paste a public HTTPS URL for the reference video instead
    of uploading the bytes — handy for motion-control where Freepik may reject
    base64."""
    msg = update.effective_message
    if msg is None:
        return AWAITING_REFERENCE_VIDEO
    args = context.args or []
    if not args:
        await msg.reply_markdown("Format: `/seturl https://...mp4`")
        return AWAITING_REFERENCE_VIDEO
    url = args[0].strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await msg.reply_text("URL harus diawali http(s)://")
        return AWAITING_REFERENCE_VIDEO
    job = _job(context)
    job.reference_video_url = url
    await msg.reply_text("URL diterima.")
    return await _next_after_negative(update, context)


# ---------------------------------------------------------------- /cancel /stop


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if msg is not None:
        await msg.reply_text("Dibatalkan. /menu untuk mulai lagi.")
    # Cancel an in-flight background generation, if any.
    ev = context.user_data.get("active_cancel_event") if context.user_data else None
    if isinstance(ev, asyncio.Event) and not ev.is_set():
        ev.set()
    _reset_job(context)
    return ConversationHandler.END


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    ev = context.user_data.get("active_cancel_event") if context.user_data else None
    if isinstance(ev, asyncio.Event) and not ev.is_set():
        ev.set()
        if msg is not None:
            await msg.reply_text("⏹ Permintaan stop diterima.")
        return
    if msg is not None:
        await msg.reply_text("Tidak ada generasi yang sedang berjalan.")


# ---------------------------------------------------------------- generate


async def _kick_off_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return ConversationHandler.END

    job = _job(context)
    model = get_model(job.model_id or "")
    if model is None:
        await msg.reply_text("Model tidak ditemukan. /menu.")
        return ConversationHandler.END

    storage: Storage = context.application.bot_data["storage"]
    keys = await storage.list_api_keys(user.id)
    if not keys:
        await msg.reply_text(
            "Belum ada API key Freepik. Kirim /addkey <FPSX...> di chat private "
            "untuk menambahkan, lalu /menu untuk mulai lagi."
        )
        _reset_job(context)
        return ConversationHandler.END

    payload = {
        "prompt": job.prompt,
        "negative_prompt": job.negative_prompt or None,
        "aspect_ratio": job.aspect_ratio,
        "resolution": job.resolution,
        "duration": job.duration,
        "generate_audio": job.generate_audio,
        "start_image_url": job.start_image_url,
        "end_image_url": job.end_image_url,
        "reference_video_url": job.reference_video_url,
    }
    body = build_post_body(model, payload)

    history_id = await storage.insert_history(
        user_id=user.id,
        mode=model.mode,
        model_id=model.id,
        prompt=job.prompt,
        status="IN_PROGRESS",
    )

    await context.bot.send_chat_action(
        chat_id=msg.chat_id,
        action=ChatAction.TYPING,
    )
    status_msg = await msg.reply_text(
        f"⏳ Generating dengan *{model.label}*…\nKetik /stop untuk batalkan.",
        parse_mode="Markdown",
    )

    cancel_event = asyncio.Event()
    # Stash a reference to the cancel event in a stable user_data key so
    # /stop can find it after we reset the job state for the next flow.
    context.user_data["active_cancel_event"] = cancel_event
    asyncio.create_task(
        _run_generation(
            context=context,
            chat_id=msg.chat_id,
            status_message_id=status_msg.message_id,
            user_id=user.id,
            model=model,
            body=body,
            api_keys=[k.api_key for k in keys],
            api_key_ids=[k.id for k in keys],
            history_id=history_id,
            cancel_event=cancel_event,
        )
    )
    # Conversation is done; the background task drives the rest of the UI.
    _reset_job(context)
    return ConversationHandler.END


async def _edit_status(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    text: str,
) -> None:
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="Markdown",
        )
    except BadRequest as exc:
        # "Message is not modified" is harmless and very common.
        if "not modified" not in str(exc).lower():
            logger.debug("edit_message_text failed: %s", exc)


async def _run_generation(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    status_message_id: int,
    user_id: int,
    model: Model,
    body: dict,
    api_keys: list[str],
    api_key_ids: list[int],
    history_id: int,
    cancel_event: asyncio.Event,
) -> None:
    storage: Storage = context.application.bot_data["storage"]
    config: Config = context.application.bot_data["config"]
    client: FreepikClient = context.application.bot_data["freepik_client"]

    # 1) POST to start the task.
    post = await client.call(
        "POST",
        model.post_path,
        api_keys,
        json_body=body,
    )
    if not post.ok:
        await _edit_status(
            context,
            chat_id,
            status_message_id,
            f"❌ Gagal start task: {post.error_message or post.status}",
        )
        await storage.update_history(
            history_id,
            status="FAILED",
            error_message=post.error_message or f"http_{post.status}",
            api_key_fingerprint=post.api_key_fingerprint,
        )
        return

    if post.api_key_index is not None and 0 <= post.api_key_index < len(api_key_ids):
        await storage.touch_api_key(user_id, api_key_ids[post.api_key_index])

    task_id = extract_task_id(post.data)
    if not task_id:
        await _edit_status(
            context,
            chat_id,
            status_message_id,
            "❌ Freepik tidak mengembalikan task_id. Coba model lain atau "
            "cek API key Anda.",
        )
        await storage.update_history(
            history_id,
            status="FAILED",
            error_message="missing_task_id",
            api_key_fingerprint=post.api_key_fingerprint,
        )
        return

    await storage.update_history(
        history_id,
        task_id=task_id,
        api_key_fingerprint=post.api_key_fingerprint,
    )

    last_status: dict[str, str] = {"value": ""}

    async def on_tick(status: str, _data: object) -> None:
        if status and status != last_status["value"]:
            last_status["value"] = status
            await _edit_status(
                context,
                chat_id,
                status_message_id,
                f"⏳ *{model.label}* — status: `{status}`\n"
                f"task `{task_id}`\n"
                "Ketik /stop untuk batalkan.",
            )

    final = await poll_until_done(
        client,
        model.task_base_path,
        task_id,
        api_keys,
        interval_seconds=config.poll_interval_seconds,
        on_tick=on_tick,
        cancel_event=cancel_event,
    )

    if not final.ok:
        if final.error_message == "cancelled_by_user":
            text = "🚫 Dibatalkan oleh user."
            status = "CANCELED"
        else:
            text = f"❌ Gagal: {final.error_message or final.status}"
            status = "FAILED"
        await _edit_status(context, chat_id, status_message_id, text)
        await storage.update_history(
            history_id,
            status=status,
            error_message=final.error_message,
        )
        return

    urls = extract_result_urls(final.data)
    if not urls:
        await _edit_status(
            context,
            chat_id,
            status_message_id,
            "❌ Task selesai tapi tidak ada URL hasil di response.",
        )
        await storage.update_history(
            history_id,
            status="FAILED",
            error_message="no_result_urls",
        )
        return

    await _edit_status(
        context,
        chat_id,
        status_message_id,
        f"✅ *{model.label}* selesai. Mengirim hasil…",
    )

    # Stream the result(s) back to the user.
    sent_url = urls[0]
    try:
        if model.result_kind == "image":
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=sent_url,
                caption=f"{model.label}\n{sent_url}",
            )
        else:
            await context.bot.send_video(
                chat_id=chat_id,
                video=sent_url,
                caption=f"{model.label}\n{sent_url}",
                supports_streaming=True,
            )
        # Send any extras as additional messages
        for extra in urls[1:5]:
            await context.bot.send_message(chat_id=chat_id, text=extra)
    except BadRequest as exc:
        # Telegram occasionally refuses a remote URL upload (size, mime). Fall
        # back to just sending the link so the user can click & download.
        logger.warning("telegram refused remote upload (%s): %s", model.label, exc)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Telegram tidak bisa fetch hasilnya langsung — buka link berikut:\n"
                + "\n".join(urls[:5])
            ),
            disable_web_page_preview=False,
        )

    await storage.update_history(
        history_id,
        status="COMPLETED",
        result_url=sent_url,
    )


# ---------------------------------------------------------------- registration


def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(on_mode_chosen, pattern=r"^mode:"),
        ],
        states={
            CHOOSING_MODEL: [
                CallbackQueryHandler(on_model_chosen, pattern=r"^model:"),
                CallbackQueryHandler(on_back_to_modes, pattern=r"^back:mode$"),
                CallbackQueryHandler(on_mode_chosen, pattern=r"^mode:"),
            ],
            AWAITING_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_prompt),
            ],
            AWAITING_NEGATIVE: [
                CommandHandler("skip", on_skip_negative),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_negative),
            ],
            AWAITING_START_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_start_image),
            ],
            AWAITING_END_IMAGE: [
                CommandHandler("skip", on_skip_end_image),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_end_image),
            ],
            AWAITING_REFERENCE_VIDEO: [
                CommandHandler("seturl", on_seturl),
                MessageHandler(
                    filters.VIDEO
                    | filters.ANIMATION
                    | filters.Document.VIDEO,
                    on_reference_video,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
    )
