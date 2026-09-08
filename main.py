import telebot
from telebot import types
import sqlite3
import json
import os
import time
import threading
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
import re
import random
import string

TOKEN = "8757426021:AAGVqjJORFJFhh1iV1f37cw9Pw9fRmDP2T4"
ADMIN_ID = 6603375763

bot = telebot.TeleBot(TOKEN)
DB_NAME = "subscription_bot.db"

class SubscriptionBot:
    def __init__(self):
        self.init_database()
        self.subscription_prices = {
            'week': 9,
            'month': 19,
            'forever': 39
        }
        self.referral_bonus_days = 3
        self.trial_days = 5
        self.ad_text = "📢 Подпишитесь на наш канал: @frogmen_channel"
    
    def init_database(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                subscription_end TEXT,
                subscription_type TEXT,
                is_admin INTEGER DEFAULT 0,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                joined_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT,
                session_file TEXT,
                added_date TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_text TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_text TEXT,
                send_date TEXT,
                is_sent INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                bonus_days INTEGER,
                date TEXT,
                FOREIGN KEY(referrer_id) REFERENCES users(id),
                FOREIGN KEY(referred_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ad_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_text TEXT,
                is_enabled INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('INSERT OR IGNORE INTO ad_settings (id, ad_text, is_enabled) VALUES (1, ?, 1)', 
                      ("📢 Подпишитесь на наш канал: @frogmen_channel",))
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id, username, first_name, last_name, phone=None, referred_by=None):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return False
        
        subscription_end = (datetime.now() + timedelta(days=self.trial_days)).isoformat()
        
        cursor.execute('''
            INSERT INTO users (id, username, first_name, last_name, phone, subscription_end, 
                             subscription_type, referred_by, joined_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (user_id, username, first_name, last_name, phone, subscription_end, 'trial', 
              referred_by, datetime.now().isoformat()))
        
        if referred_by:
            cursor.execute('''
                UPDATE users SET referral_count = referral_count + 1 WHERE id = ?
            ''', (referred_by,))
            
            cursor.execute('''
                UPDATE users SET subscription_end = datetime(subscription_end, '+' || ? || ' days')
                WHERE id = ?
            ''', (self.referral_bonus_days, referred_by))
            
            cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, bonus_days, date)
                VALUES (?, ?, ?, ?)
            ''', (referred_by, user_id, self.referral_bonus_days, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    
    def get_user(self, user_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def get_user_subscription(self, user_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT subscription_end, subscription_type FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    def is_subscription_active(self, user_id):
        result = self.get_user_subscription(user_id)
        if not result:
            return False
        subscription_end, sub_type = result
        if sub_type == 'forever':
            return True
        if subscription_end:
            end_date = datetime.fromisoformat(subscription_end)
            return datetime.now() < end_date
        return False
    
    def add_subscription(self, user_id, days, sub_type):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if sub_type == 'forever':
            cursor.execute('''
                UPDATE users SET subscription_type = ?, subscription_end = NULL
                WHERE id = ?
            ''', ('forever', user_id))
        else:
            cursor.execute('''
                UPDATE users SET subscription_type = ?, 
                subscription_end = datetime('now', '+' || ? || ' days')
                WHERE id = ?
            ''', (sub_type, days, user_id))
        
        conn.commit()
        conn.close()
    
    def add_session(self, user_id, phone, session_file):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (user_id, phone, session_file, added_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, phone, session_file, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_user_sessions(self, user_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, phone, session_file, added_date, is_active 
            FROM sessions WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        sessions = cursor.fetchall()
        conn.close()
        return sessions
    
    def get_all_sessions(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.user_id, u.first_name, u.username, s.phone, s.session_file, s.added_date
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.is_active = 1
        ''')
        sessions = cursor.fetchall()
        conn.close()
        return sessions
    
    def deactivate_session(self, session_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE sessions SET is_active = 0 WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
    
    def get_ad_text(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT ad_text, is_enabled FROM ad_settings WHERE id = 1')
        result = cursor.fetchone()
        conn.close()
        if result and result[1]:
            return result[0]
        return None
    
    def set_ad_text(self, ad_text):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE ad_settings SET ad_text = ? WHERE id = 1', (ad_text,))
        conn.commit()
        conn.close()
    
    def toggle_ad(self, enabled):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE ad_settings SET is_enabled = ? WHERE id = 1', (1 if enabled else 0,))
        conn.commit()
        conn.close()
    
    def add_scheduled_message(self, user_id, message):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (user_id, message_text, send_date)
            VALUES (?, ?, ?)
        ''', (user_id, message, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, first_name, subscription_end, subscription_type FROM users')
        users = cursor.fetchall()
        conn.close()
        return users
    
    def get_stats(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM users WHERE subscription_type = "forever"')
        forever_users = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM sessions')
        total_sessions = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM referrals')
        total_referrals = cursor.fetchone()[0]
        conn.close()
        return total_users, forever_users, total_sessions, total_referrals
    
    def generate_referral_link(self, user_id):
        return f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"

bot_db = SubscriptionBot()

def check_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    return bot_db.is_subscription_active(user_id)

def get_ad_for_user(user_id):
    if bot_db.is_subscription_active(user_id) or user_id == ADMIN_ID:
        return None
    return bot_db.get_ad_text()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    referred_by = None
    if message.text and 'ref_' in message.text:
        try:
            referred_by = int(message.text.split('ref_')[1])
        except:
            pass
    
    user = bot_db.get_user(user_id)
    if not user:
        bot_db.add_user(user_id, username, first_name, last_name, None, referred_by)
        
        if referred_by:
            bot.send_message(
                message.chat.id,
                f"🎉 Вы зарегистрировались по реферальной ссылке!\n"
                f"✅ Вам начислено {bot_db.trial_days} дней подписки\n"
                f"➕ Реферал получил +{bot_db.referral_bonus_days} дней"
            )
        else:
            bot.send_message(
                message.chat.id,
                f"🎉 Добро пожаловать!\n"
                f"✅ Вам начислено {bot_db.trial_days} дней пробной подписки"
            )
    
    show_main_menu(message.chat.id, user_id)

def show_main_menu(chat_id, user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    is_subscribed = check_subscription(user_id)
    status = "✅ Активна" if is_subscribed else "❌ Неактивна"
    
    buttons = [
        types.InlineKeyboardButton("📊 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("💎 Подписка", callback_data="subscription"),
        types.InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
        types.InlineKeyboardButton("📱 Сессии", callback_data="sessions"),
        types.InlineKeyboardButton("📝 Отправить сообщение", callback_data="send_message"),
        types.InlineKeyboardButton("📢 Реферальная ссылка", callback_data="ref_link")
    ]
    
    if user_id == ADMIN_ID:
        buttons.append(types.InlineKeyboardButton("⚙️ Админ панель", callback_data="admin_panel"))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    text = f"🤖 <b>Главное меню</b>\n\n"
    text += f"👤 {bot_db.get_user(user_id)[2] or 'Пользователь'}\n"
    text += f"📊 Статус подписки: {status}\n"
    
    if not is_subscribed and user_id != ADMIN_ID:
        ad_text = bot_db.get_ad_text()
        if ad_text:
            text += f"\n📢 {ad_text}\n"
    
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "profile":
        show_profile(call.message, user_id)
    
    elif call.data == "subscription":
        show_subscription(call.message, user_id)
    
    elif call.data == "referrals":
        show_referrals(call.message, user_id)
    
    elif call.data == "sessions":
        show_sessions(call.message, user_id)
    
    elif call.data == "send_message":
        if not check_subscription(user_id) and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Требуется активная подписка")
            return
        bot.send_message(call.message.chat.id, "📝 Введите текст сообщения для отправки:")
        bot.register_next_step_handler(call.message, process_user_message)
    
    elif call.data == "ref_link":
        link = bot_db.generate_referral_link(user_id)
        bot.send_message(
            call.message.chat.id,
            f"📢 <b>Ваша реферальная ссылка</b>\n\n"
            f"{link}\n\n"
            f"👥 За каждого приведённого друга вы получаете +{bot_db.referral_bonus_days} дней подписки",
            parse_mode="HTML"
        )
    
    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        show_admin_panel(call.message)
    
    elif call.data.startswith("sub_"):
        if user_id != ADMIN_ID:
            sub_type = call.data.replace("sub_", "")
            show_subscription_purchase(call.message, user_id, sub_type)
        else:
            parts = call.data.split("_")
            if len(parts) == 4:
                _, target_id, sub_type, days = parts
                bot_db.add_subscription(int(target_id), int(days), sub_type)
                bot.answer_callback_query(call.id, "✅ Подписка добавлена")
                show_admin_panel(call.message)
    
    elif call.data.startswith("session_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        session_id = int(call.data.replace("session_", ""))
        download_session(call.message, session_id)
    
    elif call.data.startswith("delete_session_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        session_id = int(call.data.replace("delete_session_", ""))
        bot_db.deactivate_session(session_id)
        bot.answer_callback_query(call.id, "✅ Сессия удалена")
        show_admin_panel(call.message)
    
    elif call.data == "stats":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        show_stats(call.message)
    
    elif call.data == "users_list":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        show_users_list(call.message)
    
    elif call.data == "ad_settings":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        show_ad_settings(call.message)
    
    elif call.data == "back_to_main":
        show_main_menu(call.message.chat.id, user_id)
    
    elif call.data == "back_to_admin":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён")
            return
        show_admin_panel(call.message)
    
    bot.answer_callback_query(call.id)

def show_profile(message, user_id):
    user = bot_db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    is_subscribed = check_subscription(user_id)
    sub_end, sub_type = bot_db.get_user_subscription(user_id)
    
    text = "📊 <b>Ваш профиль</b>\n\n"
    text += f"🆔 ID: {user[0]}\n"
    text += f"👤 Имя: {user[2] or 'Нет'}\n"
    text += f"📛 Username: @{user[1] or 'Нет'}\n"
    text += f"📱 Телефон: {user[4] or 'Не указан'}\n"
    text += f"📊 Статус: {'✅ Активна' if is_subscribed else '❌ Неактивна'}\n"
    if sub_type:
        text += f"💎 Тип: {sub_type}\n"
    if sub_end and sub_type != 'forever':
        end_date = datetime.fromisoformat(sub_end)
        days_left = (end_date - datetime.now()).days
        text += f"⏳ Осталось: {days_left} дней\n"
    if sub_type == 'forever':
        text += f"♾️ Навсегда\n"
    text += f"👥 Приведено друзей: {user[7] or 0}\n"
    text += f"📅 Дата регистрации: {user[8][:16] if user[8] else 'Неизвестно'}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def show_subscription(message, user_id):
    is_subscribed = check_subscription(user_id)
    
    text = "💎 <b>Подписка</b>\n\n"
    text += f"📊 Статус: {'✅ Активна' if is_subscribed else '❌ Неактивна'}\n\n"
    text += "💰 <b>Цены:</b>\n"
    text += f"• 1 неделя - {bot_db.subscription_prices['week']} ⭐\n"
    text += f"• 1 месяц - {bot_db.subscription_prices['month']} ⭐\n"
    text += f"• Навсегда - {bot_db.subscription_prices['forever']} ⭐\n\n"
    text += "⭐ <i>Оплата через Telegram Stars</i>"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("1 неделя - 9⭐", callback_data=f"sub_{user_id}_week_7"),
        types.InlineKeyboardButton("1 месяц - 19⭐", callback_data=f"sub_{user_id}_month_30"),
        types.InlineKeyboardButton("Навсегда - 39⭐", callback_data=f"sub_{user_id}_forever_0")
    )
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def show_subscription_purchase(message, user_id, sub_type):
    days = 7 if sub_type == 'week' else 30 if sub_type == 'month' else 0
    price = bot_db.subscription_prices[sub_type]
    
    bot.send_message(
        message.chat.id,
        f"💎 <b>Оплата подписки {sub_type}</b>\n\n"
        f"💰 Цена: {price} ⭐\n"
        f"⏳ Срок: {'навсегда' if days == 0 else f'{days} дней'}\n\n"
        f"🔗 Для оплаты перейдите по ссылке и отправьте {price} звезд:\n"
        f"https://t.me/{bot.get_me().username}?start=pay_{sub_type}",
        parse_mode="HTML"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_pay_{user_id}_{sub_type}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="subscription"))
    
    bot.send_message(
        message.chat.id,
        "После оплаты нажмите 'Проверить оплату'",
        reply_markup=markup
    )

def show_referrals(message, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.first_name, u.username, r.date, r.bonus_days
        FROM referrals r
        JOIN users u ON r.referred_id = u.id
        WHERE r.referrer_id = ?
        ORDER BY r.date DESC
    ''', (user_id,))
    referrals = cursor.fetchall()
    conn.close()
    
    text = "👥 <b>Ваши рефералы</b>\n\n"
    
    if not referrals:
        text += "У вас пока нет приведённых друзей\n\n"
    else:
        for ref in referrals:
            text += f"👤 {ref[0] or 'Пользователь'} @{ref[1] or 'Нет'}\n"
            text += f"📅 {ref[2][:16]}\n"
            text += f"➕ +{ref[3]} дней\n\n"
    
    link = bot_db.generate_referral_link(user_id)
    text += f"📢 <b>Ваша ссылка:</b>\n{link}\n\n"
    text += f"👥 За каждого друга +{bot_db.referral_bonus_days} дней подписки"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def show_sessions(message, user_id):
    sessions = bot_db.get_user_sessions(user_id)
    
    text = "📱 <b>Ваши сессии</b>\n\n"
    
    if not sessions:
        text += "У вас нет активных сессий"
    else:
        for session in sessions:
            text += f"🆔 ID: {session[0]}\n"
            text += f"📱 Телефон: {session[1]}\n"
            text += f"📅 Добавлена: {session[3][:16]}\n"
            text += f"⚡ {'✅ Активна' if session[4] else '❌ Неактивна'}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить сессию", callback_data="add_session"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def process_user_message(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id) and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Требуется активная подписка")
        return
    
    bot_db.add_scheduled_message(user_id, message.text)
    bot.send_message(message.chat.id, "✅ Сообщение сохранено и будет отправлено")

def show_admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        types.InlineKeyboardButton("👥 Все пользователи", callback_data="users_list")
    )
    markup.add(
        types.InlineKeyboardButton("📱 Сессии пользователей", callback_data="all_sessions"),
        types.InlineKeyboardButton("📢 Настройка рекламы", callback_data="ad_settings")
    )
    markup.add(
        types.InlineKeyboardButton("💎 Добавить подписку", callback_data="add_subscription_admin"),
        types.InlineKeyboardButton("📤 Рассылка", callback_data="broadcast")
    )
    markup.add(types.InlineKeyboardButton("🔙 На главную", callback_data="back_to_main"))
    
    text = "⚙️ <b>Админ панель</b>\n\n"
    total_users, forever_users, total_sessions, total_referrals = bot_db.get_stats()
    text += f"👥 Всего пользователей: {total_users}\n"
    text += f"👑 Навсегда: {forever_users}\n"
    text += f"📱 Сессий: {total_sessions}\n"
    text += f"👥 Рефералов: {total_referrals}\n"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def show_stats(message):
    total_users, forever_users, total_sessions, total_referrals = bot_db.get_stats()
    
    text = "📊 <b>Статистика</b>\n\n"
    text += f"👥 Всего пользователей: {total_users}\n"
    text += f"👑 Навсегда: {forever_users}\n"
    text += f"📱 Сессий: {total_sessions}\n"
    text += f"👥 Рефералов: {total_referrals}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def show_users_list(message):
    users = bot_db.get_all_users()
    
    if not users:
        bot.send_message(message.chat.id, "📭 Нет пользователей")
        return
    
    text = "👥 <b>Все пользователи</b>\n\n"
    for user in users:
        sub_status = "✅" if bot_db.is_subscription_active(user[0]) else "❌"
        text += f"🆔 {user[0]} | {user[2] or 'Без имени'} | @{user[1] or 'Нет'} | {sub_status} | {user[4] or 'trial'}\n"
        if len(text) > 3500:
            bot.send_message(message.chat.id, text, parse_mode="HTML")
            text = ""
    
    if text:
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    bot.send_message(message.chat.id, "🔙 Назад", reply_markup=markup)

def show_all_sessions(message):
    sessions = bot_db.get_all_sessions()
    
    if not sessions:
        bot.send_message(message.chat.id, "📭 Нет сессий")
        return
    
    text = "📱 <b>Все сессии</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for session in sessions:
        text += f"🆔 {session[0]} | 👤 {session[2] or 'Нет'} | @{session[3] or 'Нет'} | 📱 {session[4]}\n"
        markup.add(types.InlineKeyboardButton(
            f"📥 Скачать {session[4]}",
            callback_data=f"session_{session[0]}"
        ))
        markup.add(types.InlineKeyboardButton(
            f"🗑 Удалить {session[0]}",
            callback_data=f"delete_session_{session[0]}"
        ))
    
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

def download_session(message, session_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT session_file, phone FROM sessions WHERE id = ?', (session_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        bot.send_message(message.chat.id, "❌ Сессия не найдена")
        return
    
    session_file, phone = result
    
    if not os.path.exists(session_file):
        bot.send_message(message.chat.id, "❌ Файл сессии не найден")
        return
    
    try:
        with open(session_file, 'rb') as f:
            bot.send_document(
                message.chat.id,
                f,
                caption=f"📱 Сессия для {phone}\n🆔 {session_id}"
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

def show_ad_settings(message):
    ad_text = bot_db.get_ad_text()
    
    text = "📢 <b>Настройка рекламы</b>\n\n"
    text += f"Текущий текст:\n{ad_text or 'Не установлен'}\n\n"
    text += "Для изменения отправьте новый текст командой /setad\n"
    text += "Для отключения рекламы используйте /ad_off\n"
    text += "Для включения рекламы используйте /ad_on"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён")
        return
    show_admin_panel(message)

@bot.message_handler(commands=['setad'])
def set_ad_command(message):
    if message.chat.id != ADMIN_ID:
        return
    
    ad_text = message.text.replace('/setad', '').strip()
    if not ad_text:
        bot.send_message(message.chat.id, "❌ Введите текст рекламы после команды")
        return
    
    bot_db.set_ad_text(ad_text)
    bot.send_message(message.chat.id, f"✅ Рекламный текст обновлён:\n{ad_text}")

@bot.message_handler(commands=['ad_on'])
def ad_on_command(message):
    if message.chat.id != ADMIN_ID:
        return
    bot_db.toggle_ad(True)
    bot.send_message(message.chat.id, "✅ Реклама включена")

@bot.message_handler(commands=['ad_off'])
def ad_off_command(message):
    if message.chat.id != ADMIN_ID:
        return
    bot_db.toggle_ad(False)
    bot.send_message(message.chat.id, "✅ Реклама отключена")

@bot.message_handler(commands=['add_sub'])
def add_sub_command(message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) != 4:
        bot.send_message(message.chat.id, "❌ Использование: /add_sub [user_id] [days] [type]")
        return
    
    try:
        user_id = int(parts[1])
        days = int(parts[2])
        sub_type = parts[3]
        bot_db.add_subscription(user_id, days, sub_type)
        bot.send_message(message.chat.id, f"✅ Подписка добавлена пользователю {user_id}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    if message.chat.id == ADMIN_ID and message.text and not message.text.startswith('/'):
        bot.send_message(
            message.chat.id,
            "ℹ️ Используйте команды:\n"
            "/admin - Админ панель\n"
            "/setad [текст] - Установить рекламу\n"
            "/ad_on - Включить рекламу\n"
            "/ad_off - Выключить рекламу\n"
            "/add_sub [id] [дни] [тип] - Добавить подписку"
        )

if __name__ == "__main__":
    if not os.path.exists("sessions"):
        os.makedirs("sessions")
    
    print("🤖 Бот запущен...")
    print("📱 Ожидание команд...")
    bot.infinity_polling()
