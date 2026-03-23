import asyncio
import os
import random
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from weather import (
    get_weather_data,
    get_ararat_status,
    get_air_status,
    get_time_mode,
    get_sky_text,
)
from texts import TEXTS
from db import (
    init_db,
    ensure_user,
    set_user_language,
    get_user_language,
    subscribe_user,
    unsubscribe_user,
    is_user_subscribed,
    get_all_subscribed_users,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Yerevan")


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
                InlineKeyboardButton(text="🇦🇲 Հայերեն", callback_data="lang_hy"),
            ]
        ]
    )


def action_keyboard(lang: str, chat_id: int):
    buttons = []

    if is_user_subscribed(chat_id):
        buttons.append([
            InlineKeyboardButton(
                text=TEXTS[lang]["unsubscribe_button"],
                callback_data="unsubscribe"
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text=TEXTS[lang]["subscribe_button"],
                callback_data="subscribe"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=TEXTS[lang]["photo_button"],
            callback_data="send_photo"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_language_name(lang: str) -> str:
    names = {
        "ru": "Русский 🇷🇺",
        "en": "English 🇬🇧",
        "hy": "Հայերեն 🇦🇲",
    }
    return names.get(lang, "Русский 🇷🇺")


def build_weather_text(lang: str, data: dict, status_key: str) -> str:
    visibility_km = round(data["visibility"] / 1000, 1)
    air_key = get_air_status(data)
    time_mode = get_time_mode()
    sky_text = get_sky_text(lang, data["clouds"])

    status_line = random.choice(TEXTS[lang][status_key])
    time_tail = random.choice(TEXTS[lang]["time_tail"][time_mode])
    air_line = TEXTS[lang]["air_status"][air_key]
    decision_line = TEXTS[lang]["decision_text"][status_key]

    text = (
        f"<b>🏔 Ararat Now</b>\n\n"
        f"<i>{status_line}</i>\n\n"
        f"🌤 {TEXTS[lang]['sky_label']}: <b>{sky_text}</b>\n\n"
        f"🌡 {TEXTS[lang]['temp_label']}: <b>{round(data['temp'])}°C</b>\n"
        f"💨 {TEXTS[lang]['wind_label']}: {round(data['wind'], 1)} m/s\n"
        f"☁️ {TEXTS[lang]['clouds_label']}: {data['clouds']}%\n"
        f"👀 {TEXTS[lang]['visibility_label']}: {visibility_km} km\n\n"
        f"🌫 {TEXTS[lang]['air_label']}: <b>{air_line}</b>\n"
        f"AQI {data['aqi']} • PM2.5 {round(data['pm25'])} • PM10 {round(data['pm10'])}\n\n"
        f"🎯 {TEXTS[lang]['decision_label']}: <i>{decision_line}</i>\n\n"
        f"{time_tail}"
    )

    return text


def should_send_notification(status_key: str, data: dict) -> bool:
    air_key = get_air_status(data)

    if status_key == "excellent":
        return True

    if status_key == "good" and air_key in ("air_clean", "air_ok"):
        return True

    if status_key == "smog":
        return True

    return False


def build_morning_notification_text(lang: str, data: dict, status_key: str) -> str:
    visibility_km = round(data["visibility"] / 1000, 1)
    air_key = get_air_status(data)

    status_line = random.choice(TEXTS[lang][status_key])
    air_line = TEXTS[lang]["air_status"][air_key]
    decision_line = TEXTS[lang]["decision_text"][status_key]

    text = (
        f"🏔 Ararat Now\n\n"
        f"{status_line}\n\n"
        f"👀 {TEXTS[lang]['visibility_label']}: {visibility_km} km\n"
        f"🌫 {TEXTS[lang]['air_label']}: {air_line}\n\n"
        f"🎯 {decision_line}"
    )

    return text


@dp.message(Command("start"))
async def start_handler(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)

    lang = get_user_language(chat_id)

    if not lang:
        await message.answer(
            TEXTS["ru"]["welcome"],
            reply_markup=language_keyboard(),
        )
        return

    subscription_text = (
        TEXTS[lang]["subscription_on"]
        if is_user_subscribed(chat_id)
        else TEXTS[lang]["subscription_off"]
    )

    text = (
        f"<b>🏔 Ararat Now</b>\n\n"
        f"{TEXTS[lang]['start_ready']}\n\n"
        f"{TEXTS[lang]['current_language_label']}: <b>{get_language_name(lang)}</b>\n"
        f"🔔 {subscription_text}\n\n"
        f"{TEXTS[lang]['start_hint']}"
    )

    await message.answer(
        text,
        reply_markup=action_keyboard(lang, chat_id),
    )


@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    if callback.message is None:
        await callback.answer()
        return

    chat_id = callback.message.chat.id
    data = callback.data

    if data == "lang_ru":
        ensure_user(chat_id)
        set_user_language(chat_id, "ru")
        lang = "ru"
        await callback.message.answer(
            f"{TEXTS[lang]['language_set']}\n\n{TEXTS[lang]['check_prompt']}",
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "lang_en":
        ensure_user(chat_id)
        set_user_language(chat_id, "en")
        lang = "en"
        await callback.message.answer(
            f"{TEXTS[lang]['language_set']}\n\n{TEXTS[lang]['check_prompt']}",
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "lang_hy":
        ensure_user(chat_id)
        set_user_language(chat_id, "hy")
        lang = "hy"
        await callback.message.answer(
            f"{TEXTS[lang]['language_set']}\n\n{TEXTS[lang]['check_prompt']}",
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "subscribe":
        ensure_user(chat_id)
        lang = get_user_language(chat_id) or "ru"
        subscribe_user(chat_id)
        await callback.message.answer(
            TEXTS[lang]["subscribed_text"],
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "unsubscribe":
        ensure_user(chat_id)
        lang = get_user_language(chat_id) or "ru"
        unsubscribe_user(chat_id)
        await callback.message.answer(
            TEXTS[lang]["unsubscribed_text"],
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "send_photo":
        lang = get_user_language(chat_id) or "ru"
        await callback.message.answer(TEXTS[lang]["photo_prompt"])

    await callback.answer()


@dp.message(Command("subscribe"))
async def subscribe_command(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id) or "ru"
    subscribe_user(chat_id)
    await message.answer(
        TEXTS[lang]["subscribed_text"],
        reply_markup=action_keyboard(lang, chat_id),
    )


@dp.message(Command("unsubscribe"))
async def unsubscribe_command(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id) or "ru"
    unsubscribe_user(chat_id)
    await message.answer(
        TEXTS[lang]["unsubscribed_text"],
        reply_markup=action_keyboard(lang, chat_id),
    )


@dp.message(Command("check_now"))
async def check_now_handler(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id)

    if not lang:
        await message.answer(TEXTS["ru"]["no_language"])
        return

    try:
        data = get_weather_data(lang)
        status_key = get_ararat_status(data)
        text = build_weather_text(lang, data, status_key)
        await message.answer(text)

    except Exception as e:
        print("=== FULL ERROR /check_now ===")
        traceback.print_exc()
        await message.answer(f"Ошибка: {repr(e)}")


@dp.message()
async def handle_photo(message: Message):
    if not message.photo:
        return

    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id) or "ru"

    try:
        caption = (
            f"{TEXTS[lang]['photo_caption_prefix']}\n"
            f"From chat_id: {chat_id}"
        )

        if ADMIN_CHAT_ID:
            await bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=message.photo[-1].file_id,
                caption=caption,
            )

        await message.answer(TEXTS[lang]["photo_received"])

    except Exception:
        traceback.print_exc()
        await message.answer(TEXTS[lang]["photo_received"])


async def send_morning_notifications():
    users = get_all_subscribed_users()

    for chat_id in users:
        try:
            lang = get_user_language(chat_id) or "ru"
            data = get_weather_data(lang)
            status_key = get_ararat_status(data)

            if not should_send_notification(status_key, data):
                continue

            text = build_morning_notification_text(lang, data, status_key)
            await bot.send_message(chat_id, text)

        except Exception:
            print(f"=== FULL ERROR notify chat_id={chat_id} ===")
            traceback.print_exc()


async def main():
    init_db()
    scheduler.add_job(
        send_morning_notifications,
        CronTrigger(hour=10, minute=0, timezone="Asia/Yerevan")
    )
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())