import os
import logging
import asyncio
import tempfile
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
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
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
    )
)


def search_spotify(query: str, limit: int = 5) -> list[dict]:
    results = sp.search(q=query, type="track", limit=limit)
    tracks = []
    for item in results["tracks"]["items"]:
        artists = ", ".join(a["name"] for a in item["artists"])
        tracks.append({
            "title": item["name"],
            "artist": artists,
            "album": item["album"]["name"],
            "duration_ms": item["duration_ms"],
            "spotify_url": item["external_urls"]["spotify"],
            "search_query": f"{item['name']} {artists} official audio",
        })
    return tracks


def download_from_youtube(search_query: str, output_dir: str) -> str | None:
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{search_query}", download=True)
        if info and "entries" in info and info["entries"]:
            entry = info["entries"][0]
            filename = ydl.prepare_filename(entry)
            mp3_path = os.path.splitext(filename)[0] + ".mp3"
            return mp3_path
    return None


def format_duration(ms: int) -> str:
    seconds = ms // 1000
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎵 *Musiqa Bot*\n\n"
        "Qo'shiq nomi yoki ijrochi ismini yuboring, men topib beraman!\n\n"
        "Misol: `Dua Lipa Levitating` yoki `Ulug'bek Rahmatullayev`",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Yordam*\n\n"
        "• Qo'shiq nomini yozing — men Spotify'dan topaman\n"
        "• Kerakli qo'shiqni tanlang — yuklab beraman\n"
        "• /start — botni qayta ishga tushirish\n\n"
        "🔍 Misol: `Billie Eilish Bad Guy`",
        parse_mode="Markdown",
    )


async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    if not query:
        return

    searching_msg = await update.message.reply_text("🔍 Qidirilmoqda...")

    try:
        tracks = search_spotify(query)
    except Exception as e:
        logger.error(f"Spotify search error: {e}")
        await searching_msg.edit_text("❌ Qidiruvda xato yuz berdi. Qaytadan urinib ko'ring.")
        return

    if not tracks:
        await searching_msg.edit_text("❌ Hech narsa topilmadi. Boshqa nom bilan qidiring.")
        return

    keyboard = []
    context.user_data["tracks"] = tracks

    for i, track in enumerate(tracks):
        duration = format_duration(track["duration_ms"])
        label = f"🎵 {track['artist']} — {track['title']} ({duration})"
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
        f"💿 {track['album']}\n"
        f"⏱ {format_duration(track['duration_ms'])}"
    )
    await query.edit_message_text(info_text, parse_mode="Markdown")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            loop = asyncio.get_event_loop()
            mp3_path = await loop.run_in_executor(
                None, download_from_youtube, track["search_query"], tmpdir
            )

            if not mp3_path or not os.path.exists(mp3_path):
                await query.message.reply_text("❌ Musiqa yuklab bo'lmadi.")
                return

            caption = (
                f"🎵 *{track['title']}*\n"
                f"👤 {track['artist']}\n"
                f"💿 {track['album']}"
            )

            with open(mp3_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    title=track["title"],
                    performer=track["artist"],
                    caption=caption,
                    parse_mode="Markdown",
                )

        except Exception as e:
            logger.error(f"Download error: {e}")
            await query.message.reply_text(
                "❌ Yuklab bo'lmadi. Qaytadan urinib ko'ring."
            )


def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN topilmadi! .env faylni tekshiring.")
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError("SPOTIFY kalitlari topilmadi! .env faylni tekshiring.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(download_track, pattern=r"^track_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
