import os
import logging
import asyncio
import tempfile
from dotenv import load_dotenv
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def search_youtube(query: str, limit: int = 5) -> list[dict]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        tracks = []
        if results and "entries" in results:
            for entry in results["entries"]:
                if entry:
                    duration_ms = int((entry.get("duration") or 0) * 1000)
                    tracks.append({
                        "title": entry.get("title", "Unknown"),
                        "artist": entry.get("uploader", "Unknown"),
                        "duration_ms": duration_ms,
                        "webpage_url": entry.get("webpage_url") or entry.get("url", ""),
                    })
        return tracks


def download_from_youtube(url: str, output_dir: str) -> str | None:
    base = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    attempts = [
        {**base, "cookiesfrombrowser": ("edge",)},
        {**base, "cookiesfrombrowser": ("chrome",)},
        {**base, "extractor_args": {"youtube": {"player_client": ["ios"], "player_skip": ["webpage"]}}},
        {**base, "extractor_args": {"youtube": {"player_client": ["ios"]}}},
    ]
    for ydl_opts in attempts:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
            files = [f for f in os.listdir(output_dir) if not f.endswith(".part")]
            if files:
                return os.path.join(output_dir, files[0])
        except Exception as e:
            logger.warning(f"Yuklash xatosi: {e}")
            for f in os.listdir(output_dir):
                try:
                    os.remove(os.path.join(output_dir, f))
                except Exception:
                    pass
    return None


def format_duration(ms: int) -> str:
    seconds = ms // 1000
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Xato yuz berdi:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(f"⚠️ Ichki xato: {context.error}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎵 *Musiqa Bot*\n\n"
        "Qo'shiq nomi yoki ijrochi ismini yuboring!\n\n"
        "Misol: `Dua Lipa Levitating` yoki `Ulug'bek Rahmatullayev`",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Yordam*\n\n"
        "• Qo'shiq nomini yozing — YouTube'dan topaman\n"
        "• Kerakli qo'shiqni tanlang — yuklab beraman\n"
        "• /start — botni qayta ishga tushirish\n\n"
        "🔍 Misol: `Billie Eilish Bad Guy`",
        parse_mode="Markdown",
    )


async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    logger.info(f"Qidiruv: {query}")
    if not query:
        return

    searching_msg = await update.message.reply_text("🔍 Qidirilmoqda...")

    try:
        loop = asyncio.get_event_loop()
        tracks = await loop.run_in_executor(None, search_youtube, query)
    except Exception as e:
        logger.error(f"Qidiruv xatosi: {e}")
        await searching_msg.edit_text("❌ Qidiruvda xato. Qaytadan urinib ko'ring.")
        return

    if not tracks:
        await searching_msg.edit_text("❌ Hech narsa topilmadi. Boshqa nom bilan qidiring.")
        return

    keyboard = []
    context.user_data["tracks"] = tracks

    for i, track in enumerate(tracks):
        duration = format_duration(track["duration_ms"])
        label = f"🎵 {track['title']} ({duration})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"track_{i}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await searching_msg.edit_text(
        f"🎶 *'{query}'* uchun natijalar:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    track_index = int(query.data.split("_")[1])
    tracks = context.user_data.get("tracks", [])

    if track_index >= len(tracks):
        await query.edit_message_text("❌ Xato yuz berdi.")
        return

    track = tracks[track_index]
    info_text = (
        f"⏳ Yuklanmoqda...\n\n"
        f"🎵 *{track['title']}*\n"
        f"👤 {track['artist']}\n"
        f"⏱ {format_duration(track['duration_ms'])}"
    )
    await query.edit_message_text(info_text, parse_mode="Markdown")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            loop = asyncio.get_event_loop()
            mp3_path = await loop.run_in_executor(
                None, download_from_youtube, track["webpage_url"], tmpdir
            )

            if not mp3_path or not os.path.exists(mp3_path):
                await query.message.reply_text("❌ Musiqa yuklab bo'lmadi.")
                return

            caption = f"🎵 *{track['title']}*\n👤 {track['artist']}"
            filename = os.path.basename(mp3_path)

            with open(mp3_path, "rb") as audio_file:
                await query.message.reply_document(
                    document=audio_file,
                    caption=caption,
                    parse_mode="Markdown",
                    filename=filename,
                )

        except Exception as e:
            logger.error(f"Yuklash xatosi: {e}")
            await query.message.reply_text("❌ Yuklab bo'lmadi. Qaytadan urinib ko'ring.")


def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN topilmadi! .env faylni tekshiring.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(download_track, pattern=r"^track_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
