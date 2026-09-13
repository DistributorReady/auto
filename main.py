import asyncio
import json
import os
import random
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, PreCheckoutQuery,
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================== НАСТРОЙКИ ==================
TOKEN = "8639390909:AAF3QBYwZM23Z48vSfmxX1W9Bo9mroVR0Uk"
ADMIN_ID = 6603375763
MANAGER_CRYPTO = "@FasteNEWDid"
CHANNEL_APPS = "https://t.me/frogmenIot"

USERS_FILE = "users.json"
KEYS_FILE = "keys.json"
APPS_FILE = "apps.json"
SETTINGS_FILE = "settings.json"

# ================== ИНИЦИАЛИЗАЦИЯ ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
BOT_USERNAME = ""

# ================== ХЕЛПЕРЫ ДАННЫХ ==================
def load_json(path, default):
    if not os.path.exists(path):
        save_json(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка чтения {path}: {e}")
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка записи {path}: {e}")

def get_settings():
    default = {
        "price_1": 5,
        "price_10": 4,
        "price_50": 3,
        "min_batch": 10,
        "big_batch": 50
    }
    s = load_json(SETTINGS_FILE, default)
    for k, v in default.items():
        s.setdefault(k, v)
    return s

def save_settings(s):
    save_json(SETTINGS_FILE, s)

def get_users():
    return load_json(USERS_FILE, {})

def save_users(users):
    save_json(USERS_FILE, users)

def get_user(user_id):
    users = get_users()
    uid = str(user_id)
    user = users.get(uid)
    if user and "received_keys" not in user:
        user["received_keys"] = []
        users[uid] = user
        save_users(users)
    return user

def register_user(user_id, username, first_name, referrer_id=None):
    users = get_users()
    uid = str(user_id)
    if uid in users:
        if "received_keys" not in users[uid]:
            users[uid]["received_keys"] = []
            save_users(users)
        return False

    referrer = None
    if referrer_id:
        rid = str(referrer_id)
        if rid != uid and rid in users:
            referrer = rid

    users[uid] = {
        "username": username,
        "first_name": first_name,
        "balance": 0.0,
        "referrer": referrer,
        "referrals": [],
        "earned": 0.0,
        "purchases": [],
        "received_keys": [],
        "reg_date": datetime.now().isoformat()
    }

    if referrer:
        users[referrer]["referrals"].append(uid)
        users[referrer]["balance"] = round(users[referrer]["balance"] + 3.0, 2)
        users[referrer]["earned"] = round(users[referrer]["earned"] + 3.0, 2)

        ref2 = users[referrer].get("referrer")
        if ref2 and ref2 in users:
            users[ref2]["balance"] = round(users[ref2]["balance"] + 1.0, 2)
            users[ref2]["earned"] = round(users[ref2]["earned"] + 1.0, 2)
            ref3 = users[ref2].get("referrer")
            if ref3 and ref3 in users:
                users[ref3]["balance"] = round(users[ref3]["balance"] + 0.25, 2)
                users[ref3]["earned"] = round(users[ref3]["earned"] + 0.25, 2)
    save_users(users)
    return True

def add_balance(user_id, amount):
    users = get_users()
    uid = str(user_id)
    if uid not in users:
        return False
    users[uid]["balance"] = round(users[uid]["balance"] + amount, 2)
    save_users(users)
    return True

def deduct_balance(user_id, amount):
    users = get_users()
    uid = str(user_id)
    if uid not in users or users[uid]["balance"] < amount:
        return False
    users[uid]["balance"] = round(users[uid]["balance"] - amount, 2)
    save_users(users)
    return True

def bonus_referrer(user_id, amount):
    users = get_users()
    uid = str(user_id)
    if uid not in users:
        return None
    ref = users[uid].get("referrer")
    if ref and ref in users:
        users[ref]["balance"] = round(users[ref]["balance"] + amount, 2)
        users[ref]["earned"] = round(users[ref]["earned"] + amount, 2)
        save_users(users)
        return ref
    return None

def log_purchase(user_id, ptype, value, price):
    users = get_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["purchases"].append({
            "type": ptype, "value": value, "price": price,
            "date": datetime.now().isoformat()
        })
        save_users(users)

def get_available_keys_for_user(user_id):
    """Общий пул keys.json НЕ трогается. Возвращаем ключи, что юзер ещё не получал."""
    all_keys = load_json(KEYS_FILE, [])
    user = get_user(user_id)
    received = set(user.get("received_keys", [])) if user else set()
    return [k for k in all_keys if k not in received]

def mark_keys_received(user_id, keys):
    """Пишем ТОЛЬКО в личный список юзера. keys.json НЕ перезаписываем."""
    users = get_users()
    uid = str(user_id)
    if uid in users:
        if "received_keys" not in users[uid]:
            users[uid]["received_keys"] = []
        users[uid]["received_keys"].extend(keys)
        save_users(users)

def get_key_price(count, settings):
    """Возвращает цену за 1 ключ в зависимости от количества."""
    if count >= settings["big_batch"]:
        return settings["price_50"]
    elif count >= settings["min_batch"]:
        return settings["price_10"]
    else:
        return settings["price_1"]

# ================== КЛАВИАТУРЫ ==================
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Приобрести", callback_data="shop")],
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="🎁 Реферальная система", callback_data="ref_sys")],
    ])

def kb_shop():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Ключи (Urent)", callback_data="keys_menu")],
        [InlineKeyboardButton(text="📱 Приложения", callback_data="apps_menu")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])

def kb_topup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Звёздами", callback_data="topup_stars")],
        [InlineKeyboardButton(text="💎 Криптой", url=f"https://t.me/{MANAGER_CRYPTO[1:]}")],
        [InlineKeyboardButton(text="💼 Заработать", callback_data="earn_money")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])

def kb_keys(settings):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔑 Купить 1 ключ ({settings['price_1']}₽)", callback_data="buy_key_1")],
        [InlineKeyboardButton(text="🔑 Купить несколько", callback_data="buy_key_multi")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="shop")],
    ])

def kb_back(to="main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=to)]
    ])

def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🔑 Заменить ключи", callback_data="adm_add_keys")],
        [InlineKeyboardButton(text="💲 Изменить цены", callback_data="adm_prices")],
        [InlineKeyboardButton(text="📱 Добавить приложение", callback_data="adm_add_app")],
        [InlineKeyboardButton(text="💰 Выдать баланс", callback_data="adm_give_bal")],
        [InlineKeyboardButton(text="💸 Забрать баланс", callback_data="adm_take_bal")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="adm_broadcast")],
    ])

# ================== STATES ==================
class TopUpStars(StatesGroup):
    waiting_amount = State()

class BuyKeys(StatesGroup):
    waiting_count = State()

class AdminFSM(StatesGroup):
    add_keys = State()
    add_app = State()
    give_balance = State()
    take_balance = State()
    broadcast = State()
    change_prices = State()

# ================== УТИЛИТА ==================
async def safe_edit(callback: CallbackQuery, text: str, keyboard=None, parse_mode="Markdown"):
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception:
            try:
                await callback.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
            except Exception as e:
                logging.error(f"safe_edit error: {e}")

# ================== /start ==================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
        except Exception:
            pass

    is_new = register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        referrer_id
    )

    caption = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🛒 Добро пожаловать в магазин ключей и приложений Frogmen.\n"
        "💰 Пополняй баланс, покупай ключи, зарабатывай на рефералах!"
    )

    if os.path.exists("main.jpg"):
        try:
            photo = FSInputFile("main.jpg")
            await message.answer_photo(photo=photo, caption=caption, reply_markup=kb_main())
        except Exception as e:
            logging.error(f"Ошибка отправки фото: {e}")
            await message.answer(caption, reply_markup=kb_main())
    else:
        await message.answer(caption, reply_markup=kb_main())

    if referrer_id and is_new:
        try:
            await bot.send_message(
                referrer_id,
                "🎉 По вашей ссылке зарегистрировался новый пользователь! +3₽ на баланс."
            )
        except Exception:
            pass

# ================== ГЛАВНОЕ МЕНЮ ==================
@dp.callback_query(F.data == "main_menu")
async def cb_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await safe_edit(callback, "🏠 Главное меню Frogmen\n\nВыбери действие:", kb_main())

# ================== ПРОФИЛЬ ==================
@dp.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    await callback.answer()
    u = get_user(callback.from_user.id)
    if not u:
        await callback.answer("Сначала /start", show_alert=True)
        return
    text = (
        f"👤 **Мой профиль**\n\n"
        f"🆔 ID: `{callback.from_user.id}`\n"
        f"💰 Баланс: **{u.get('balance', 0)}₽**\n"
        f"👥 Рефералов: **{len(u.get('referrals', []))}**\n"
        f"💵 Всего заработано: **{u.get('earned', 0)}₽**\n"
        f"🛍 Покупок: **{len(u.get('purchases', []))}**\n"
        f"🔑 Ключей получено: **{len(u.get('received_keys', []))}**"
    )
    await safe_edit(callback, text, kb_back())

# ================== РЕФЕРАЛЬНАЯ СИСТЕМА ==================
@dp.callback_query(F.data == "ref_sys")
async def cb_ref(callback: CallbackQuery):
    await callback.answer()
    u = get_user(callback.from_user.id)
    if not u:
        await callback.answer("Сначала /start", show_alert=True)
        return
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{callback.from_user.id}"
    text = (
        f"🎁 **Реферальная система**\n\n"
        f"🔗 Ваша ссылка:\n`{link}`\n\n"
        f"💵 **Начисления:**\n"
        f"• +3₽ — за каждого приглашённого\n"
        f"• +10₽ — если он что-то купит\n"
        f"• +30₽ — если он пополнит баланс\n"
        f"• +1₽ — за каждого реферала реферала (2 ур.)\n"
        f"• +0.25₽ — за каждого реферала реферала реферала (3 ур.)\n\n"
        f"👥 Ваших рефералов: **{len(u.get('referrals', []))}**"
    )
    await safe_edit(callback, text, kb_back())

# ================== ПОПОЛНЕНИЕ ==================
@dp.callback_query(F.data == "topup")
async def cb_topup(callback: CallbackQuery):
    await callback.answer()
    u = get_user(callback.from_user.id)
    bal = u.get("balance", 0) if u else 0
    await safe_edit(
        callback,
        f"💳 **Пополнение баланса**\n\nТекущий баланс: **{bal}₽**\n\nВыбери способ:",
        kb_topup()
    )

@dp.callback_query(F.data == "earn_money")
async def cb_earn(callback: CallbackQuery):
    await callback.answer()
    text = (
        "💼 **Заработать на баланс**\n\n"
        "Доступные задания:\n"
        "🎵 Съёмка TikTok-видео\n"
        "💬 Комментарии под видео\n\n"
        "💰 Оплата на баланс бота — от **5₽ до 100₽** за задание.\n\n"
        f"📩 Напиши менеджеру: {MANAGER_CRYPTO}\n"
        "и получи задание + условия оплаты."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать менеджеру", url=f"https://t.me/{MANAGER_CRYPTO[1:]}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="topup")],
    ])
    await safe_edit(callback, text, keyboard)

@dp.callback_query(F.data == "topup_stars")
async def cb_topup_stars(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopUpStars.waiting_amount)
    await safe_edit(
        callback,
        "⭐ **Пополнение звёздами**\n\n"
        "Отправь количество звёзд одним числом.\n"
        "1 звезда = 2₽\n\n"
        "Например: `50` → 100₽ на баланс",
        kb_back("topup")
    )

@dp.message(TopUpStars.waiting_amount)
async def process_stars_amount(message: Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        if stars < 1 or stars > 10000:
            raise ValueError
    except Exception:
        await message.answer("❌ Введите корректное число (1–10000).")
        return

    await state.clear()
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Пополнение баланса",
            description=f"Пополнение на {stars * 2}₽",
            payload=f"topup_{stars}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=stars)],
        )
    except Exception as e:
        logging.error(f"Ошибка отправки инвойса: {e}")
        await message.answer(
            "❌ Не удалось создать счёт.\n"
            f"Обратитесь к {MANAGER_CRYPTO}"
        )

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("topup_"):
        try:
            stars = int(payload.split("_")[1])
        except Exception:
            return
        amount = stars * 2
        add_balance(message.from_user.id, amount)
        ref = bonus_referrer(message.from_user.id, 30.0)
        await message.answer(f"✅ Баланс пополнен на **{amount}₽**!", parse_mode="Markdown")
        if ref:
            try:
                await bot.send_message(ref, "💸 Ваш реферал пополнил баланс! +30₽ на баланс.")
            except Exception:
                pass

# ================== МАГАЗИН ==================
@dp.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery):
    await callback.answer()
    await safe_edit(callback, "🛒 **Магазин**\n\nВыбери категорию:", kb_shop())

# -------- КЛЮЧИ --------
@dp.callback_query(F.data == "keys_menu")
async def cb_keys(callback: CallbackQuery):
    await callback.answer()
    settings = get_settings()
    all_keys = load_json(KEYS_FILE, [])
    available = get_available_keys_for_user(callback.from_user.id)
    text = (
        f"🔑 **Ключи Urent**\n\n"
        f"Доступно вам: **{len(available)} шт.**\n"
        f"Всего в базе: **{len(all_keys)} шт.**\n\n"
        f"Цены:\n"
        f"• 1 ключ — {settings['price_1']}₽\n"
        f"• от {settings['min_batch']} ключей — {settings['price_10']}₽/шт\n"
        f"• от {settings['big_batch']} ключей — {settings['price_50']}₽/шт\n\n"
        f"_Повторки не выдаются._"
    )
    await safe_edit(callback, text, kb_keys(settings))

@dp.callback_query(F.data == "buy_key_1")
async def cb_buy_one(callback: CallbackQuery):
    u = get_user(callback.from_user.id)
    if not u:
        await callback.answer("Сначала /start", show_alert=True)
        return
    settings = get_settings()
    price = settings["price_1"]
    available = get_available_keys_for_user(callback.from_user.id)
    if not available:
        await callback.answer("❌ У вас закончились доступные ключи", show_alert=True)
        return
    if u.get("balance", 0) < price:
        await callback.answer(f"❌ Недостаточно средств (нужно {price}₽)", show_alert=True)
        return

    key = random.choice(available)
    # ВАЖНО: ключ пишется только в личный список юзера, keys.json НЕ трогается
    mark_keys_received(callback.from_user.id, [key])
    deduct_balance(callback.from_user.id, price)
    log_purchase(callback.from_user.id, "key", key, price)
    ref = bonus_referrer(callback.from_user.id, 10.0)

    new_available = get_available_keys_for_user(callback.from_user.id)

    await callback.answer("✅ Ключ выдан!", show_alert=False)
    await callback.message.answer(
        f"✅ **Ваш ключ:**\n`{key}`\n\n"
        f"💰 Списано: {price}₽\n"
        f"🔑 Осталось доступно вам: **{len(new_available)} шт.**",
        parse_mode="Markdown"
    )
    if ref:
        try:
            await bot.send_message(ref, "🛍 Ваш реферал купил товар! +10₽ на баланс.")
        except Exception:
            pass

@dp.callback_query(F.data == "buy_key_multi")
async def cb_buy_multi(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    settings = get_settings()
    available = get_available_keys_for_user(callback.from_user.id)
    if not available:
        await callback.answer("❌ У вас закончились доступные ключи", show_alert=True)
        return
    await state.set_state(BuyKeys.waiting_count)
    await safe_edit(
        callback,
        f"🔑 **Покупка нескольких ключей**\n\n"
        f"Доступно вам: **{len(available)} шт.**\n\n"
        f"Введите количество:\n"
        f"• 1–{settings['min_batch']-1} — {settings['price_1']}₽/шт\n"
        f"• {settings['min_batch']}–{settings['big_batch']-1} — {settings['price_10']}₽/шт\n"
        f"• {settings['big_batch']}+ — {settings['price_50']}₽/шт",
        kb_back("keys_menu")
    )

@dp.message(BuyKeys.waiting_count)
async def process_buy_multi(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1:
            raise ValueError
    except Exception:
        await message.answer("❌ Введите корректное число.")
        return

    settings = get_settings()
    available = get_available_keys_for_user(message.from_user.id)
    if count > len(available):
        await message.answer(f"❌ Доступно только {len(available)} ключей (уникальных для вас).")
        return

    price = get_key_price(count, settings)
    total_price = count * price

    u = get_user(message.from_user.id)
    if not u or u.get("balance", 0) < total_price:
        await message.answer(f"❌ Недостаточно средств. Нужно: {total_price}₽")
        return

    bought = random.sample(available, count)
    # ВАЖНО: пишем только в личный список, keys.json не трогаем
    mark_keys_received(message.from_user.id, bought)
    deduct_balance(message.from_user.id, total_price)
    log_purchase(message.from_user.id, "keys_batch", count, total_price)
    ref = bonus_referrer(message.from_user.id, 10.0)

    new_available = get_available_keys_for_user(message.from_user.id)
    keys_text = "\n".join(f"`{k}`" for k in bought)
    await message.answer(
        f"✅ Куплено ключей: **{count}**\n"
        f"💰 Списано: **{total_price}₽** ({price}₽/шт)\n"
        f"🔑 Осталось доступно вам: **{len(new_available)} шт.**\n\n"
        f"**Ваши ключи:**\n{keys_text}",
        parse_mode="Markdown"
    )
    await state.clear()
    if ref:
        try:
            await bot.send_message(ref, "🛍 Ваш реферал купил товар! +10₽ на баланс.")
        except Exception:
            pass

# -------- ПРИЛОЖЕНИЯ --------
@dp.callback_query(F.data == "apps_menu")
async def cb_apps(callback: CallbackQuery):
    await callback.answer()
    apps = load_json(APPS_FILE, [])
    text = "📱 **Приложения**\n\n"
    if apps:
        for i, app in enumerate(apps, 1):
            title = app.get("title", "Без названия")
            desc = app.get("description", "")
            link = app.get("link", "")
            text += f"{i}. **{title}**\n{desc}\n[Скачать]({link})\n\n"
    else:
        text += "_Пока нет добавленных приложений._\n\n"
    text += "🎁 Бесплатные приложения в канале @frogmenIot"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Бесплатные приложения", url=CHANNEL_APPS)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="shop")],
    ])
    await safe_edit(callback, text, keyboard, parse_mode="Markdown")

# ================== АДМИН-ПАНЕЛЬ ==================
@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    users = get_users()
    keys = load_json(KEYS_FILE, [])
    apps = load_json(APPS_FILE, [])
    total_revenue = sum(
        p.get("price", 0) for u in users.values() for p in u.get("purchases", [])
    )
    text = (
        f"🔐 **Админ-панель Frogmen**\n\n"
        f"👥 Пользователей: **{len(users)}**\n"
        f"🔑 Ключей в базе: **{len(keys)}**\n"
        f"📱 Приложений: **{len(apps)}**\n"
        f"💰 Общий оборот: **{total_revenue}₽**"
    )
    await message.answer(text, reply_markup=kb_admin(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("adm_"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔", show_alert=True)
        return
    await callback.answer()
    action = callback.data

    if action == "adm_stats":
        users = get_users()
        keys = load_json(KEYS_FILE, [])
        apps = load_json(APPS_FILE, [])
        total_revenue = sum(
            p.get("price", 0) for u in users.values() for p in u.get("purchases", [])
        )
        text = (
            f"📊 **Статистика**\n\n"
            f"👥 Пользователей: **{len(users)}**\n"
            f"🔑 Ключей в базе: **{len(keys)}**\n"
            f"📱 Приложений: **{len(apps)}**\n"
            f"💰 Оборот покупок: **{total_revenue}₽**"
        )
        await safe_edit(callback, text, kb_admin())

    elif action == "adm_add_keys":
        await state.set_state(AdminFSM.add_keys)
        await safe_edit(
            callback,
            "🔑 Отправьте новые ключи через запятую.\n\n"
            "⚠️ **Внимание:** старый список будет ЗАМЕНЁН.\n\n"
            "Пример:\n`key1,key2,key3`",
            kb_admin()
        )

    elif action == "adm_prices":
        settings = get_settings()
        await state.set_state(AdminFSM.change_prices)
        await safe_edit(
            callback,
            f"💲 **Текущие цены:**\n\n"
            f"• 1 ключ — {settings['price_1']}₽\n"
            f"• от {settings['min_batch']} шт — {settings['price_10']}₽/шт\n"
            f"• от {settings['big_batch']} шт — {settings['price_50']}₽/шт\n\n"
            f"Отправьте новые значения в формате:\n"
            f"`цена_1 цена_10 цена_50 порог_10 порог_50`\n\n"
            f"Пример:\n`5 4 3 10 50`",
            kb_admin()
        )

    elif action == "adm_add_app":
        await state.set_state(AdminFSM.add_app)
        await safe_edit(
            callback,
            "📱 Отправьте приложение в формате:\n"
            "`Название | Описание | Ссылка`\n\n"
            "Пример:\n`Telegram | Мессенджер | https://t.me/...`",
            kb_admin()
        )

    elif action == "adm_give_bal":
        await state.set_state(AdminFSM.give_balance)
        await safe_edit(
            callback,
            "💰 Отправьте: `user_id сумма`\n\nПример: `6603375763 100`",
            kb_admin()
        )

    elif action == "adm_take_bal":
        await state.set_state(AdminFSM.take_balance)
        await safe_edit(
            callback,
            "💸 Отправьте: `user_id сумма`\n\nПример: `6603375763 50`",
            kb_admin()
        )

    elif action == "adm_users":
        users = get_users()
        if not users:
            await safe_edit(callback, "📭 Нет пользователей.", kb_admin())
            return
        text = "👥 **Пользователи (до 30):**\n\n"
        for i, (uid, u) in enumerate(list(users.items())[:30], 1):
            uname = f"@{u.get('username')}" if u.get("username") else "—"
            text += f"{i}. `{uid}` {uname} | 💰{u.get('balance', 0)}₽\n"
        if len(users) > 30:
            text += f"\n... и ещё {len(users) - 30}"
        await safe_edit(callback, text, kb_admin())

    elif action == "adm_broadcast":
        await state.set_state(AdminFSM.broadcast)
        await safe_edit(
            callback,
            "📨 Отправьте сообщение для рассылки всем пользователям.",
            kb_admin()
        )

# ---- FSM обработчики админа ----
@dp.message(AdminFSM.add_keys)
async def adm_add_keys(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    new_keys = [k.strip() for k in text.split(",") if k.strip()]
    if not new_keys:
        await message.answer("❌ Не найдено ключей.")
        return
    save_json(KEYS_FILE, new_keys)
    await state.clear()
    await message.answer(
        f"✅ Список ключей заменён.\n"
        f"Теперь в базе: **{len(new_keys)}** ключей.",
        parse_mode="Markdown"
    )

@dp.message(AdminFSM.change_prices)
async def adm_change_prices(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) != 5:
            raise ValueError
        p1 = float(parts[0])
        p10 = float(parts[1])
        p50 = float(parts[2])
        min_b = int(parts[3])
        big_b = int(parts[4])
        if p1 <= 0 or p10 <= 0 or p50 <= 0 or min_b < 2 or big_b <= min_b:
            raise ValueError
    except Exception:
        await message.answer(
            "❌ Формат: `цена_1 цена_10 цена_50 порог_10 порог_50`\n"
            "Пример: `5 4 3 10 50`",
            parse_mode="Markdown"
        )
        return

    settings = get_settings()
    settings["price_1"] = p1
    settings["price_10"] = p10
    settings["price_50"] = p50
    settings["min_batch"] = min_b
    settings["big_batch"] = big_b
    save_settings(settings)
    await state.clear()
    await message.answer(
        f"✅ **Цены обновлены:**\n\n"
        f"• 1 ключ — {p1}₽\n"
        f"• от {min_b} шт — {p10}₽/шт\n"
        f"• от {big_b} шт — {p50}₽/шт",
        parse_mode="Markdown"
    )

@dp.message(AdminFSM.add_app)
async def adm_add_app(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 3:
        await message.answer("❌ Формат: `Название | Описание | Ссылка`", parse_mode="Markdown")
        return
    apps = load_json(APPS_FILE, [])
    apps.append({"title": parts[0], "description": parts[1], "link": parts[2]})
    save_json(APPS_FILE, apps)
    await state.clear()
    await message.answer(f"✅ Приложение добавлено. Всего: {len(apps)}")

@dp.message(AdminFSM.give_balance)
async def adm_give(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid, amount = message.text.split()
        uid = int(uid)
        amount = float(amount)
    except Exception:
        await message.answer("❌ Формат: `user_id сумма`", parse_mode="Markdown")
        return
    if add_balance(uid, amount):
        await message.answer(f"✅ Выдано {amount}₽ пользователю {uid}")
        try:
            await bot.send_message(uid, f"💰 Вам выдан баланс: +{amount}₽")
        except Exception:
            pass
    else:
        await message.answer("❌ Пользователь не найден.")
    await state.clear()

@dp.message(AdminFSM.take_balance)
async def adm_take(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid, amount = message.text.split()
        uid = int(uid)
        amount = float(amount)
    except Exception:
        await message.answer("❌ Формат: `user_id сумма`", parse_mode="Markdown")
        return
    if deduct_balance(uid, amount):
        await message.answer(f"✅ Списано {amount}₽ у {uid}")
    else:
        await message.answer("❌ Недостаточно средств или пользователь не найден.")
    await state.clear()

@dp.message(AdminFSM.broadcast)
async def adm_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    users = get_users()
    sent, failed = 0, 0
    progress = await message.answer(f"⏳ Рассылка {len(users)} пользователям...")
    for uid in users.keys():
        try:
            await message.copy_to(chat_id=int(uid))
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await state.clear()
    await progress.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )

# ================== ЗАПУСК ==================
async def main():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username
    print(f"🤖 Бот Frogmen запущен: @{BOT_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
