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

# ================== ИНИЦИАЛИЗАЦИЯ ==================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
BOT_USERNAME = ""

# ================== ХЕЛПЕРЫ ДАННЫХ ==================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_users():
    return load_json(USERS_FILE, {})

def save_users(users):
    save_json(USERS_FILE, users)

def get_user(user_id):
    return get_users().get(str(user_id))

def register_user(user_id, username, first_name, referrer_id=None):
    users = get_users()
    uid = str(user_id)
    if uid in users:
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
        "reg_date": datetime.now().isoformat()
    }

    # Начисление реферальных
    if referrer:
        users[referrer]["referrals"].append(uid)
        users[referrer]["balance"] = round(users[referrer]["balance"] + 3.0, 2)
        users[referrer]["earned"] = round(users[referrer]["earned"] + 3.0, 2)

        # Уровень 2: +1₽
        ref2 = users[referrer].get("referrer")
        if ref2 and ref2 in users:
            users[ref2]["balance"] = round(users[ref2]["balance"] + 1.0, 2)
            users[ref2]["earned"] = round(users[ref2]["earned"] + 1.0, 2)
            # Уровень 3: +0.25₽
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
    """Начисляет бонус прямому рефереру (10₽ за покупку / 30₽ за пополнение)."""
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])

def kb_keys():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Купить 1 ключ (5₽)", callback_data="buy_key_1")],
        [InlineKeyboardButton(text="🔑 Купить несколько", callback_data="buy_key_multi")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="shop")],
    ])

def kb_apps():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Бесплатные приложения", url=CHANNEL_APPS)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="shop")],
    ])

def kb_back(to="main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=to)]
    ])

def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🔑 Добавить ключи", callback_data="adm_add_keys")],
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

# ================== УТИЛИТА ==================
async def safe_edit(callback: CallbackQuery, text: str, keyboard=None, parse_mode="Markdown"):
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)

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
        photo = FSInputFile("main.jpg")
        await message.answer_photo(photo=photo, caption=caption, reply_markup=kb_main())
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
    await safe_edit(
        callback,
        "🏠 Главное меню Frogmen\n\nВыбери действие:",
        kb_main()
    )

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
        f"🛍 Покупок: **{len(u.get('purchases', []))}**"
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
            "❌ Не удалось создать счёт. Возможно, оплата звёздами не настроена.\n"
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
    keys = load_json(KEYS_FILE, [])
    text = (
        f"🔑 **Ключи Urent**\n\n"
        f"В наличии: **{len(keys)} шт.**\n\n"
        f"Цены:\n"
        f"• 1 ключ — 5₽\n"
        f"• от 10 ключей — 4₽/шт\n"
        f"• от 50 ключей — 3₽/шт"
    )
    await safe_edit(callback, text, kb_keys())

@dp.callback_query(F.data == "buy_key_1")
async def cb_buy_one(callback: CallbackQuery):
    u = get_user(callback.from_user.id)
    if not u:
        await callback.answer("Сначала /start", show_alert=True)
        return
    keys = load_json(KEYS_FILE, [])
    if not keys:
        await callback.answer("❌ Нет ключей в наличии", show_alert=True)
        return
    if u.get("balance", 0) < 5:
        await callback.answer("❌ Недостаточно средств (нужно 5₽)", show_alert=True)
        return

    key = random.choice(keys)
    keys.remove(key)
    save_json(KEYS_FILE, keys)
    deduct_balance(callback.from_user.id, 5)
    log_purchase(callback.from_user.id, "key", key, 5)
    ref = bonus_referrer(callback.from_user.id, 10.0)

    await callback.answer("✅ Ключ выдан!", show_alert=False)
    await callback.message.answer(
        f"✅ **Ваш ключ:**\n`{key}`\n\n"
        f"💰 Списано: 5₽",
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
    keys = load_json(KEYS_FILE, [])
    total = len(keys)
    if total == 0:
        await callback.answer("❌ Нет ключей в наличии", show_alert=True)
        return
    await state.set_state(BuyKeys.waiting_count)
    await safe_edit(
        callback,
        f"🔑 **Покупка нескольких ключей**\n\n"
        f"В наличии: **{total} шт.**\n\n"
        f"Введите количество:\n"
        f"• 1–9 — 5₽/шт\n"
        f"• 10–49 — 4₽/шт\n"
        f"• 50+ — 3₽/шт",
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

    keys = load_json(KEYS_FILE, [])
    if count > len(keys):
        await message.answer(f"❌ В наличии только {len(keys)} ключей.")
        return

    if count >= 50:
        price = 3
    elif count >= 10:
        price = 4
    else:
        price = 5
    total_price = count * price

    u = get_user(message.from_user.id)
    if not u or u.get("balance", 0) < total_price:
        await message.answer(f"❌ Недостаточно средств. Нужно: {total_price}₽")
        return

    bought = random.sample(keys, count)
    for k in bought:
        keys.remove(k)
    save_json(KEYS_FILE, keys)
    deduct_balance(message.from_user.id, total_price)
    log_purchase(message.from_user.id, "keys_batch", count, total_price)
    ref = bonus_referrer(message.from_user.id, 10.0)

    keys_text = "\n".join(f"`{k}`" for k in bought)
    await message.answer(
        f"✅ Куплено ключей: **{count}**\n"
        f"💰 Списано: **{total_price}₽** ({price}₽/шт)\n\n"
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
        f"🔑 Ключей: **{len(keys)}**\n"
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
        total_topup = 0
        # считаем только оборот, не знаем точное пополнение
        text = (
            f"📊 **Статистика**\n\n"
            f"👥 Пользователей: **{len(users)}**\n"
            f"🔑 Ключей в наличии: **{len(keys)}**\n"
            f"📱 Приложений: **{len(apps)}**\n"
            f"💰 Оборот покупок: **{total_revenue}₽**"
        )
        await safe_edit(callback, text, kb_admin())

    elif action == "adm_add_keys":
        await state.set_state(AdminFSM.add_keys)
        await safe_edit(
            callback,
            "🔑 Отправьте ключи через запятую.\n\nПример:\n`key1,key2,key3`",
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
            uname = f"@{u['username']}" if u.get("username") else "—"
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
    keys = load_json(KEYS_FILE, [])
    keys.extend(new_keys)
    save_json(KEYS_FILE, keys)
    await state.clear()
    await message.answer(f"✅ Добавлено: **{len(new_keys)}**\nВсего: **{len(keys)}**", parse_mode="Markdown")

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
