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
    BotCommand,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from weather import (
    get_weather_data,
    get_air_status,
    get_time_mode,
    get_sky_text,
    calculate_ararat_score,
    get_ararat_status_from_score,
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
    add_photo,
    get_photo_by_id,
    add_best_photo,
    clear_best_photos_today,
    get_best_photos_today,
    get_total_users,
    get_total_subscribed,
    get_photos_count,
    get_recent_photos_count,
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


def t(lang: str, key: str, default=""):
    return TEXTS.get(lang, {}).get(key, default)


def pick_from_list(values, default: str = "") -> str:
    if isinstance(values, list) and values:
        return random.choice(values)
    if isinstance(values, str):
        return values
    return default


def safe_status_line(lang: str, status_key: str) -> str:
    return pick_from_list(
        TEXTS.get(lang, {}).get(status_key),
        pick_from_list(TEXTS.get("ru", {}).get(status_key), status_key),
    )


def safe_oracle_phrase(lang: str, status_key: str) -> str:
    oracle_block = TEXTS.get(lang, {}).get("oracle", {})
    phrases = oracle_block.get(status_key)

    if not phrases:
        phrases = TEXTS.get("ru", {}).get("oracle", {}).get(status_key)

    return pick_from_list(phrases, "Сегодня лучше просто наблюдать.")


def safe_air_line(lang: str, air_key: str) -> str:
    return TEXTS.get(lang, {}).get("air_status", {}).get(
        air_key,
        TEXTS.get("ru", {}).get("air_status", {}).get(air_key, air_key),
    )


def safe_decision_line(lang: str, status_key: str) -> str:
    return TEXTS.get(lang, {}).get("decision_text", {}).get(
        status_key,
        TEXTS.get("ru", {}).get("decision_text", {}).get(status_key, status_key),
    )


def safe_time_tail(lang: str, time_mode: str) -> str:
    values = TEXTS.get(lang, {}).get("time_tail", {}).get(time_mode)
    if not values:
        values = TEXTS.get("ru", {}).get("time_tail", {}).get(time_mode, [])
    return pick_from_list(values, "")


def get_language_name(lang: str) -> str:
    return {
        "ru": "Русский 🇷🇺",
        "en": "English 🇬🇧",
        "hy": "Հայերեն 🇦🇲",
    }.get(lang, "Русский 🇷🇺")


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
    rows = []

    rows.append([
        InlineKeyboardButton(
            text=t(lang, "check_now_button", "👀 Проверить сейчас"),
            callback_data="check_now_inline"
        ),
        InlineKeyboardButton(
            text=t(lang, "oracle_button", "🔮 Оракул"),
            callback_data="oracle"
        )
    ])

    if is_user_subscribed(chat_id):
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "unsubscribe_button", "🔕 Отключить"),
                callback_data="unsubscribe"
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "subscribe_button", "🔔 Включить"),
                callback_data="subscribe"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text=t(lang, "photo_button", "📸 Отправить фото"),
            callback_data="send_photo"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def set_main_menu():
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="check_now", description="Проверить Арарат"),
        BotCommand(command="oracle", description="Араратный оракул"),
        BotCommand(command="subscribe", description="Включить уведомления"),
        BotCommand(command="unsubscribe", description="Отключить уведомления"),
    ]
    await bot.set_my_commands(commands)


async def send_language_picker(message: Message):
    await message.answer(
        t(
            "ru",
            "welcome",
            "🏔 <b>Ararat Now</b>\n\n"
            "Бот, который говорит — видно ли сегодня Арарат\n\n"
            "🔔 При подписке:\n"
            "— утром ты получишь статус видимости\n"
            "— вечером лучшее фото дня 📸\n\n"
            "Выбери язык:"
        ),
        reply_markup=language_keyboard(),
    )


def get_status_with_score(data: dict) -> str:
    recent_photos = 0
    crowd_bonus = 0

    try:
        recent_photos = get_recent_photos_count(3)
        if recent_photos > 0:
            crowd_bonus = 10
    except Exception:
        recent_photos = 0
        crowd_bonus = 0

    score = calculate_ararat_score(data, crowd_bonus=crowd_bonus)
    return get_ararat_status_from_score(score, data)


def build_weather_text(lang: str, data: dict, status_key: str) -> str:
    visibility_km = round(data["visibility"] / 1000, 1)
    air_key = get_air_status(data)
    time_mode = get_time_mode()
    sky_text = get_sky_text(lang, data["clouds"])

    status_line = safe_status_line(lang, status_key)
    air_line = safe_air_line(lang, air_key)
    decision_line = safe_decision_line(lang, status_key)

    time_tail = safe_time_tail(lang, time_mode) if status_key in ("good", "excellent") else ""
    tail_block = f"\n\n{time_tail}" if time_tail else ""

    return (
        f"<b>🏔 Ararat Now</b>\n\n"
        f"<i>{status_line}</i>\n\n"
        f"🌤 {t(lang, 'sky_label', 'Небо')}: <b>{sky_text}</b>\n\n"
        f"🌡 {t(lang, 'temp_label', 'Температура')}: <b>{round(data['temp'])}°C</b>\n"
        f"💨 {t(lang, 'wind_label', 'Ветер')}: {round(data['wind'], 1)} m/s\n"
        f"☁️ {t(lang, 'clouds_label', 'Облачность')}: {data['clouds']}%\n"
        f"👀 {t(lang, 'visibility_label', 'Видимость')}: {visibility_km} km\n\n"
        f"🌫 {t(lang, 'air_label', 'Воздух')}: <b>{air_line}</b>\n"
        f"AQI {data['aqi']} • PM2.5 {round(data['pm25'])} • PM10 {round(data['pm10'])}\n\n"
        f"🎯 {t(lang, 'decision_label', 'Вердикт')}: <i>{decision_line}</i>"
        f"{tail_block}"
    )


def build_morning_notification_text(lang: str, data: dict, status_key: str) -> str:
    visibility_km = round(data["visibility"] / 1000, 1)
    air_key = get_air_status(data)

    status_line = safe_status_line(lang, status_key)
    air_line = safe_air_line(lang, air_key)
    decision_line = safe_decision_line(lang, status_key)

    return (
        f"🏔 Ararat Now\n\n"
        f"{status_line}\n\n"
        f"👀 {t(lang, 'visibility_label', 'Видимость')}: {visibility_km} km\n"
        f"🌫 {t(lang, 'air_label', 'Воздух')}: {air_line}\n\n"
        f"🎯 {decision_line}"
    )


def build_best_photo_caption(lang: str = "ru") -> str:
    return t(
        lang,
        "best_photo_day_caption",
        "📸 Лучшие фото дня\n\nСегодня Арарат поймали так 👀"
    )


def should_send_notification(status_key: str, data: dict) -> bool:
    air_key = get_air_status(data)

    if status_key == "excellent":
        return True
    if status_key == "good" and air_key in ("air_clean", "air_ok"):
        return True
    if status_key == "smog":
        return True

    return False


@dp.message(Command("start"))
async def start_handler(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)

    lang = get_user_language(chat_id)

    if not lang:
        await send_language_picker(message)
        return

    subscription_text = (
        t(lang, "subscribed_text", "Уведомления включены")
        if is_user_subscribed(chat_id)
        else t(lang, "unsubscribed_text", "Уведомления отключены")
    )

    text = (
        f"<b>🏔 Ararat Now</b>\n\n"
        f"{t(lang, 'language_set', 'Язык установлен')}: <b>{get_language_name(lang)}</b>\n"
        f"🔔 {subscription_text}\n\n"
        f"{t(lang, 'check_prompt', 'Теперь можно проверить видимость')}"
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
            f"{t(lang, 'language_set', 'Язык установлен')}\n\n{t(lang, 'check_prompt', 'Теперь можно проверить видимость')}",
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "lang_en":
        ensure_user(chat_id)
        set_user_language(chat_id, "en")
        lang = "en"
        await callback.message.answer(
            f"{t(lang, 'language_set', 'Language set')}\n\n{t(lang, 'check_prompt', 'Now you can check visibility')}",
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "lang_hy":
        ensure_user(chat_id)
        set_user_language(chat_id, "hy")
        lang = "hy"
        await callback.message.answer(
            f"{t(lang, 'language_set', 'Լեզուն ընտրված է')}\n\n{t(lang, 'check_prompt', 'Հիմա կարող ես ստուգել տեսանելիությունը')}",
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "subscribe":
        ensure_user(chat_id)
        lang = get_user_language(chat_id) or "ru"
        subscribe_user(chat_id)
        await callback.message.answer(
            t(lang, "subscribed_text", "Уведомления включены"),
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "unsubscribe":
        ensure_user(chat_id)
        lang = get_user_language(chat_id) or "ru"
        unsubscribe_user(chat_id)
        await callback.message.answer(
            t(lang, "unsubscribed_text", "Уведомления отключены"),
            reply_markup=action_keyboard(lang, chat_id),
        )

    elif data == "send_photo":
        lang = get_user_language(chat_id) or "ru"
        await callback.message.answer(
            t(lang, "photo_prompt", "Отправь фото Арарата 📸")
        )

    elif data == "check_now_inline":
        lang = get_user_language(chat_id)

        if not lang:
            await send_language_picker(callback.message)
            await callback.answer()
            return

        try:
            data_weather = get_weather_data(lang)
            status_key = get_status_with_score(data_weather)
            text = build_weather_text(lang, data_weather, status_key)
            await callback.message.answer(text)
        except Exception as e:
            traceback.print_exc()
            await callback.message.answer(f"Ошибка: {repr(e)}")

    elif data == "oracle":
        lang = get_user_language(chat_id)

        if not lang:
            await send_language_picker(callback.message)
            await callback.answer()
            return

        try:
            data_weather = get_weather_data(lang)
            status_key = get_status_with_score(data_weather)
            phrase = safe_oracle_phrase(lang, status_key)

            title = {
                "ru": "🔮 <b>Арарат сегодня говорит:</b>",
                "en": "🔮 <b>Ararat says today:</b>",
                "hy": "🔮 <b>Արարատն այսօր ասում է․</b>",
            }.get(lang, "🔮 <b>Арарат сегодня говорит:</b>")

            await callback.message.answer(f"{title}\n\n<i>{phrase}</i>")

        except Exception as e:
            traceback.print_exc()
            await callback.message.answer(f"Ошибка: {repr(e)}")

    await callback.answer()


@dp.message(Command("subscribe"))
async def subscribe_command(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id)

    if not lang:
        await send_language_picker(message)
        return

    subscribe_user(chat_id)
    await message.answer(
        t(lang, "subscribed_text", "Уведомления включены"),
        reply_markup=action_keyboard(lang, chat_id),
    )


@dp.message(Command("unsubscribe"))
async def unsubscribe_command(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id)

    if not lang:
        await send_language_picker(message)
        return

    unsubscribe_user(chat_id)
    await message.answer(
        t(lang, "unsubscribed_text", "Уведомления отключены"),
        reply_markup=action_keyboard(lang, chat_id),
    )


@dp.message(Command("check_now"))
async def check_now_handler(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id)

    if not lang:
        await send_language_picker(message)
        return

    try:
        data = get_weather_data(lang)
        status_key = get_status_with_score(data)
        text = build_weather_text(lang, data, status_key)
        await message.answer(text)

    except Exception as e:
        print("=== FULL ERROR /check_now ===")
        traceback.print_exc()
        await message.answer(f"Ошибка: {repr(e)}")


@dp.message(Command("oracle"))
async def oracle_handler(message: Message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id)

    if not lang:
        await send_language_picker(message)
        return

    try:
        data = get_weather_data(lang)
        status_key = get_status_with_score(data)
        phrase = safe_oracle_phrase(lang, status_key)

        title = {
            "ru": "🔮 <b>Арарат сегодня говорит:</b>",
            "en": "🔮 <b>Ararat says today:</b>",
            "hy": "🔮 <b>Արարատն այսօր ասում է․</b>",
        }.get(lang, "🔮 <b>Арарат сегодня говорит:</b>")

        await message.answer(f"{title}\n\n<i>{phrase}</i>")

    except Exception as e:
        traceback.print_exc()
        await message.answer(f"Ошибка: {repr(e)}")


@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    try:
        total_users = get_total_users()
        subscribed = get_total_subscribed()
        photos = get_photos_count()

        text = (
            f"📊 <b>Ararat Now — статистика</b>\n\n"
            f"👥 Всего пользователей: <b>{total_users}</b>\n"
            f"🔔 Подписаны: <b>{subscribed}</b>\n"
            f"📸 Фото в базе: <b>{photos}</b>"
        )

        await message.answer(text)

    except Exception as e:
        traceback.print_exc()
        await message.answer(f"Ошибка: {repr(e)}")


@dp.message(Command("best_today"))
async def best_today_handler(message: Message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer("Используй так: /best_today 12")
        return

    try:
        photo_id = int(parts[1])
    except ValueError:
        await message.answer("photo_id должен быть числом")
        return

    photo = get_photo_by_id(photo_id)

    if not photo:
        await message.answer("Фото с таким id не найдено")
        return

    add_best_photo(photo_id)
    await message.answer(f"Фото {photo_id} добавлено в лучшие фото дня 📸")


@dp.message(Command("clear_best_today"))
async def clear_best_today_handler(message: Message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    clear_best_photos_today()
    await message.answer("Лучшие фото дня очищены")


@dp.message(Command("send_best_now"))
async def send_best_now_handler(message: Message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    best_photos = get_best_photos_today()

    if not best_photos:
        await message.answer("На сегодня фото дня пока не выбраны")
        return

    users = get_all_subscribed_users()
    sent = 0

    for user_id in users:
        try:
            lang = get_user_language(user_id) or "ru"

            for index, photo in enumerate(best_photos):
                caption = build_best_photo_caption(lang) if index == 0 else None
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo["file_id"],
                    caption=caption,
                )

            sent += 1
        except Exception:
            traceback.print_exc()

    await message.answer(f"Подборка дня отправлена: {sent} пользователям")


@dp.message()
async def text_language_handler(message: Message):
    if message.photo:
        return

    raw = (message.text or "").strip().lower()

    language_map = {
        "русский": "ru",
        "russian": "ru",
        "🇷🇺 русский": "ru",
        "english": "en",
        "английский": "en",
        "🇬🇧 english": "en",
        "հայերեն": "hy",
        "армянский": "hy",
        "armenian": "hy",
        "🇦🇲 հայերեն": "hy",
    }

    if raw not in language_map:
        return

    chat_id = message.chat.id
    lang = language_map[raw]

    ensure_user(chat_id)
    set_user_language(chat_id, lang)

    await message.answer(
        f"{t(lang, 'language_set', 'Язык установлен')}\n\n{t(lang, 'check_prompt', 'Теперь можно проверить видимость')}",
        reply_markup=action_keyboard(lang, chat_id),
    )


@dp.message()
async def handle_photo(message: Message):
    if not message.photo:
        return

    chat_id = message.chat.id
    ensure_user(chat_id)
    lang = get_user_language(chat_id) or "ru"

    try:
        file_id = message.photo[-1].file_id
        photo_id = add_photo(chat_id, file_id)

        caption = (
            f"{t(lang, 'photo_caption_prefix', 'Новое фото Арарата')}\n"
            f"photo_id: {photo_id}\n"
            f"from chat_id: {chat_id}"
        )

        if ADMIN_CHAT_ID:
            await bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=file_id,
                caption=caption,
            )

        await message.answer(
            t(lang, "photo_received", "📸 Фото принято.")
        )

    except Exception:
        traceback.print_exc()
        await message.answer(
            t(lang, "photo_received", "📸 Фото принято.")
        )


async def send_morning_notifications():
    users = get_all_subscribed_users()

    for chat_id in users:
        try:
            lang = get_user_language(chat_id) or "ru"
            data = get_weather_data(lang)
            status_key = get_status_with_score(data)

            if not should_send_notification(status_key, data):
                continue

            text = build_morning_notification_text(lang, data, status_key)
            await bot.send_message(chat_id, text)

        except Exception:
            print(f"=== FULL ERROR notify chat_id={chat_id} ===")
            traceback.print_exc()


async def send_evening_best_photo():
    best_photos = get_best_photos_today()

    if not best_photos:
        print("No best photos selected for evening push")
        return

    users = get_all_subscribed_users()

    for user_id in users:
        try:
            lang = get_user_language(user_id) or "ru"

            for index, photo in enumerate(best_photos):
                caption = build_best_photo_caption(lang) if index == 0 else None
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo["file_id"],
                    caption=caption,
                )

        except Exception:
            print(f"=== ERROR evening best photos user_id={user_id} ===")
            traceback.print_exc()


async def main():
    init_db()
    await set_main_menu()

    scheduler.add_job(
        send_morning_notifications,
        CronTrigger(hour=10, minute=0, timezone="Asia/Yerevan")
    )

    scheduler.add_job(
        send_evening_best_photo,
        CronTrigger(hour=19, minute=0, timezone="Asia/Yerevan")
    )

    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())