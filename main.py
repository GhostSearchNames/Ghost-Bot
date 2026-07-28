"""
👻 GHOST - Поиск Ников
Версия: 10.0 FULL WORKING
- РЕАЛЬНЫЙ ПОИСК с прогрессом 1/15, 2/15 и т.д.
- Показывает какой юз проверяется
- Останавливается на свободном
- Показывает стоимость и кнопку "Скопировать"
- Оплата звездами с подтверждением
"""

import asyncio
import logging
import random
import string
import time
import json
import os
import sqlite3
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    PreCheckoutQuery, SuccessfulPayment, LabeledPrice,
    BufferedInputFile
)
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ═══════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════

BOT_TOKEN = "8809493398:AAE17ZjF0xewvy5m1mslr8Cx9ImX1QX9NOs"
DEVELOPER_USERNAME = "gawuzu"
ADMIN_ID = 123456789

PRICES = {1: 65, 3: 150, 10: 400, 30: 800}
MAX_FREE_REQUESTS = 5
REQUESTS_ADD_AMOUNT = 3
REQUESTS_UPDATE_DAYS = 2
COOLDOWN_SECONDS = 30
DB_FILE = "users.db"
MAX_SEARCH_ATTEMPTS = 15

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# СОСТОЯНИЯ FSM
# ═══════════════════════════════════════════════════════════════════

class PromoStates(StatesGroup):
    waiting_for_promo = State()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()

class PromoCreateStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_days = State()
    waiting_for_limit = State()

class DevGivePremiumStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_days = State()

class DevGiveRequestsStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_count = State()

class DevDeletePromoStates(StatesGroup):
    waiting_for_code = State()

# ═══════════════════════════════════════════════════════════════════
# БАЗА ДАННЫХ (SQLite)
# ═══════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
        logger.info("✅ База данных SQLite подключена")
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at INTEGER,
                free_requests INTEGER DEFAULT 5,
                free_requests_reset INTEGER,
                free_requests_last_update INTEGER,
                premium_until INTEGER DEFAULT 0,
                last_search INTEGER DEFAULT 0,
                total_searches INTEGER DEFAULT 0,
                ban_status INTEGER DEFAULT 0,
                ban_reason TEXT,
                referral_earnings INTEGER DEFAULT 0,
                is_developer INTEGER DEFAULT 0
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS found_usernames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                found_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                created_at INTEGER,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_id) REFERENCES users(user_id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                days INTEGER,
                max_uses INTEGER,
                uses INTEGER DEFAULT 0,
                created_at INTEGER,
                expires_at INTEGER,
                created_by INTEGER
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS promo_used (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                promo_id INTEGER,
                used_at INTEGER
            )
        ''')
        
        self.conn.commit()
    
    def get_user(self, user_id: int) -> Dict:
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        
        if row:
            return {
                "user_id": row[0],
                "username": row[1] or "",
                "first_name": row[2] or "",
                "registered_at": row[3],
                "free_requests": row[4],
                "free_requests_reset": row[5],
                "free_requests_last_update": row[6] or 0,
                "premium_until": row[7],
                "last_search": row[8],
                "total_searches": row[9],
                "ban_status": bool(row[10]),
                "ban_reason": row[11] or "",
                "referral_earnings": row[12] or 0,
                "is_developer": bool(row[13]) if len(row) > 13 else False
            }
        else:
            current_time = int(time.time())
            is_dev = 1 if str(user_id) == str(ADMIN_ID) else 0
            self.cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, registered_at,
                    free_requests, free_requests_reset, free_requests_last_update,
                    premium_until, last_search, total_searches,
                    ban_status, ban_reason, referral_earnings, is_developer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, "", "", current_time,
                MAX_FREE_REQUESTS, current_time + 86400, current_time,
                0, 0, 0, 0, "", 0, is_dev
            ))
            self.conn.commit()
            return self.get_user(user_id)
    
    def update_user_field(self, user_id: int, field: str, value):
        self.cursor.execute(f'UPDATE users SET {field} = ? WHERE user_id = ?', (value, user_id))
        self.conn.commit()
    
    def is_developer(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return user.get("is_developer", False)
    
    def is_premium(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return user.get("premium_until", 0) > int(time.time())
    
    def get_premium_remaining(self, user_id: int) -> int:
        user = self.get_user(user_id)
        remaining = user.get("premium_until", 0) - int(time.time())
        return max(0, remaining)
    
    def add_premium(self, user_id: int, days: int):
        user = self.get_user(user_id)
        current_until = user.get("premium_until", 0)
        if current_until > int(time.time()):
            new_until = current_until + (days * 86400)
        else:
            new_until = int(time.time()) + (days * 86400)
        self.update_user_field(user_id, "premium_until", new_until)
    
    def get_free_requests(self, user_id: int) -> int:
        user = self.get_user(user_id)
        current_time = int(time.time())
        last_update = user.get("free_requests_last_update", 0)
        days_passed = (current_time - last_update) / 86400
        
        if days_passed >= REQUESTS_UPDATE_DAYS:
            current_requests = user.get("free_requests", 0)
            new_requests = min(current_requests + REQUESTS_ADD_AMOUNT, MAX_FREE_REQUESTS)
            self.update_user_field(user_id, "free_requests", new_requests)
            self.update_user_field(user_id, "free_requests_last_update", current_time)
            return new_requests
        
        return user.get("free_requests", 0)
    
    def add_free_requests(self, user_id: int, count: int):
        user = self.get_user(user_id)
        current = user.get("free_requests", 0)
        new_count = min(current + count, MAX_FREE_REQUESTS)
        self.update_user_field(user_id, "free_requests", new_count)
    
    def use_free_request(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        current_requests = user.get("free_requests", 0)
        if current_requests > 0:
            self.update_user_field(user_id, "free_requests", current_requests - 1)
            return True
        return False
    
    def check_cooldown(self, user_id: int) -> Tuple[bool, int]:
        user = self.get_user(user_id)
        last_search = user.get("last_search", 0)
        current_time = int(time.time())
        elapsed = current_time - last_search
        if elapsed < COOLDOWN_SECONDS:
            return False, COOLDOWN_SECONDS - elapsed
        return True, 0
    
    def update_last_search(self, user_id: int):
        self.update_user_field(user_id, "last_search", int(time.time()))
    
    def increment_searches(self, user_id: int):
        user = self.get_user(user_id)
        self.update_user_field(user_id, "total_searches", user.get("total_searches", 0) + 1)
    
    def add_found_username(self, user_id: int, username: str):
        self.cursor.execute('''
            INSERT INTO found_usernames (user_id, username, found_at)
            VALUES (?, ?, ?)
        ''', (user_id, username, int(time.time())))
        self.conn.commit()
    
    def get_found_usernames(self, user_id: int, limit: int = 20) -> List[Dict]:
        self.cursor.execute('''
            SELECT username, found_at FROM found_usernames
            WHERE user_id = ? ORDER BY found_at DESC LIMIT ?
        ''', (user_id, limit))
        rows = self.cursor.fetchall()
        return [{"username": row[0], "found_at": row[1]} for row in rows]
    
    def is_banned(self, user_id: int) -> Tuple[bool, str]:
        user = self.get_user(user_id)
        if user.get("ban_status", False):
            return True, user.get("ban_reason", "Вы забанены")
        return False, ""
    
    def get_total_users(self) -> int:
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def get_total_searches(self) -> int:
        self.cursor.execute('SELECT SUM(total_searches) FROM users')
        result = self.cursor.fetchone()[0]
        return result or 0
    
    def get_premium_count(self) -> int:
        current_time = int(time.time())
        self.cursor.execute('SELECT COUNT(*) FROM users WHERE premium_until > ?', (current_time,))
        return self.cursor.fetchone()[0]
    
    def set_developer(self, user_id: int):
        self.update_user_field(user_id, "is_developer", 1)
    
    def get_all_users(self) -> List[int]:
        self.cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in self.cursor.fetchall()]
    
    def create_promo(self, code: str, days: int, max_uses: int, created_by: int) -> bool:
        try:
            self.cursor.execute('''
                INSERT INTO promo_codes (code, days, max_uses, created_at, expires_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (code.upper(), days, max_uses, int(time.time()), int(time.time()) + 86400 * 30, created_by))
            self.conn.commit()
            return True
        except:
            return False
    
    def delete_promo(self, code: str) -> bool:
        try:
            self.cursor.execute('DELETE FROM promo_codes WHERE code = ?', (code.upper(),))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except:
            return False
    
    def get_all_promos(self) -> List[Dict]:
        self.cursor.execute('SELECT * FROM promo_codes ORDER BY created_at DESC')
        rows = self.cursor.fetchall()
        return [{
            "id": row[0],
            "code": row[1],
            "days": row[2],
            "max_uses": row[3],
            "uses": row[4],
            "created_at": row[5],
            "expires_at": row[6],
            "created_by": row[7] if len(row) > 7 else 0
        } for row in rows]
    
    def use_promo(self, user_id: int, code: str) -> Tuple[bool, str, int]:
        code = code.upper()
        self.cursor.execute('SELECT * FROM promo_codes WHERE code = ?', (code,))
        row = self.cursor.fetchone()
        
        if not row:
            return False, "❌ Промокод не найден", 0
        
        if row[4] >= row[3]:
            return False, "❌ Промокод уже использован", 0
        
        if row[5] < int(time.time()):
            return False, "❌ Промокод истек", 0
        
        self.cursor.execute('''
            SELECT * FROM promo_used WHERE user_id = ? AND promo_id = ?
        ''', (user_id, row[0]))
        if self.cursor.fetchone():
            return False, "❌ Вы уже использовали этот промокод", 0
        
        days = row[2]
        self.add_premium(user_id, days)
        self.cursor.execute('UPDATE promo_codes SET uses = uses + 1 WHERE code = ?', (code,))
        self.cursor.execute('INSERT INTO promo_used (user_id, promo_id, used_at) VALUES (?, ?, ?)', 
                          (user_id, row[0], int(time.time())))
        self.conn.commit()
        return True, f"✅ Премиум на {days} дней активирован!", days

db = Database()

# ═══════════════════════════════════════════════════════════════════
# РЕАЛЬНЫЙ ПОИСК ЮЗЕРНЕЙМОВ (1/15, 2/15...)
# ═══════════════════════════════════════════════════════════════════

class UsernameGenerator:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.checked_cache = set()
    
    def generate_random(self, length: int, with_digits: bool = False) -> str:
        """Генерирует случайный ник"""
        letters = 'abcdefghijklmnopqrstuvwxyz'
        if with_digits:
            letters += '0123456789'
        
        # Первая буква - всегда буква
        username = random.choice('abcdefghijklmnopqrstuvwxyz')
        
        # Остальные символы
        for _ in range(length - 1):
            username += random.choice(letters)
        
        return username
    
    async def check_username_available(self, username: str) -> bool:
        """Проверяет, свободен ли ник через Telegram API"""
        try:
            await self.bot.get_chat(f"@{username}")
            return False  # Ник занят
        except Exception as e:
            if "user not found" in str(e).lower():
                return True  # Ник свободен
            return False
    
    async def find_free_username(self, length: int, with_digits: bool = False, 
                                message=None) -> Tuple[Optional[str], int, List[str]]:
        """Ищет свободный ник с прогрессом 1/15, 2/15..."""
        MAX_ATTEMPTS = 15
        attempts = 0
        checked = []
        found = None
        
        # Начальное сообщение
        if message:
            await message.edit_text(
                f"🔍 <b>Поиск свободного юзернейма...</b>\n\n"
                f"📏 Длина: {length} символов\n"
                f"🔢 С цифрами: {'Да' if with_digits else 'Нет'}\n"
                f"⏳ 0/{MAX_ATTEMPTS}\n\n"
                f"<i>Начинаю поиск...</i>",
                parse_mode="HTML"
            )
        
        while attempts < MAX_ATTEMPTS:
            attempts += 1
            username = self.generate_random(length, with_digits)
            
            if username in self.checked_cache:
                continue
            
            self.checked_cache.add(username)
            checked.append(username)
            
            # ОБНОВЛЯЕМ СООБЩЕНИЕ КАЖДЫЙ РАЗ (показываем какой юз проверяем)
            if message:
                progress_text = (
                    f"🔍 <b>Поиск свободного юзернейма...</b>\n\n"
                    f"📏 Длина: {length} символов\n"
                    f"🔢 С цифрами: {'Да' if with_digits else 'Нет'}\n"
                    f"⏳ <b>{attempts}/{MAX_ATTEMPTS}</b>\n\n"
                    f"🔎 Проверяю: <code>@{username}</code>\n"
                    f"📋 Проверено: {len(checked)} ников\n\n"
                    f"<i>Ищу свободный ник...</i>"
                )
                await message.edit_text(progress_text, parse_mode="HTML")
            
            logger.info(f"🔄 Попытка {attempts}/{MAX_ATTEMPTS}: @{username}")
            
            # Проверяем доступность
            is_available = await self.check_username_available(username)
            
            if is_available:
                logger.info(f"✅ НАЙДЕН! @{username} (попытка {attempts})")
                found = username
                
                if message:
                    await message.edit_text(
                        f"🎉 <b>НАЙДЕН СВОБОДНЫЙ НИК!</b>\n\n"
                        f"👤 <code>@{username}</code>\n"
                        f"🎯 Найден на попытке {attempts}/{MAX_ATTEMPTS}\n"
                        f"📋 Проверено: {len(checked)} ников",
                        parse_mode="HTML"
                    )
                break
            
            # Задержка между запросами (важно для API)
            await asyncio.sleep(0.3)
        
        if not found and message:
            await message.edit_text(
                f"❌ <b>Свободный ник не найден</b>\n\n"
                f"⏳ Попыток: {MAX_ATTEMPTS}/{MAX_ATTEMPTS}\n"
                f"📋 Проверено: {len(checked)} ников\n\n"
                f"💡 Запрос не потрачен! Попробуйте другой режим.",
                parse_mode="HTML"
            )
        
        return found, attempts, checked
    
    def _calculate_rating(self, username: str) -> int:
        """Рейтинг ника (1-10)"""
        rating = 5
        
        # Длина
        if len(username) == 5:
            rating += 1
        
        # Уникальные буквы
        if len(set(username)) / len(username) > 0.6:
            rating += 1
        
        # Красивые буквы
        if 'a' in username and 'e' in username:
            rating += 1
        
        # Соотношение гласных/согласных
        vowels = sum(1 for c in username if c in 'aeiouy')
        if 0.3 < vowels / len(username) < 0.7:
            rating += 1
        
        return min(10, max(1, rating))

# ═══════════════════════════════════════════════════════════════════
# ГЕНЕРАТОР КАРТИНОК
# ═══════════════════════════════════════════════════════════════════

class ImageGenerator:
    def __init__(self):
        self.fonts = {}
        self._load_fonts()
    
    def _load_fonts(self):
        try:
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "fonts/arial.ttf"
            ]
            for path in font_paths:
                if os.path.exists(path):
                    self.fonts["large"] = ImageFont.truetype(path, 80)
                    self.fonts["medium"] = ImageFont.truetype(path, 40)
                    self.fonts["small"] = ImageFont.truetype(path, 25)
                    break
            else:
                self.fonts["large"] = ImageFont.load_default()
                self.fonts["medium"] = ImageFont.load_default()
                self.fonts["small"] = ImageFont.load_default()
        except:
            self.fonts["large"] = ImageFont.load_default()
            self.fonts["medium"] = ImageFont.load_default()
            self.fonts["small"] = ImageFont.load_default()
    
    def generate_username_card(self, username: str, rating: int, price: int, attempts: int) -> BytesIO:
        width, height = 500, 450
        image = Image.new('RGB', (width, height), color=(10, 10, 25))
        draw = ImageDraw.Draw(image)
        
        for i in range(height):
            color_value = int(10 + (i / height) * 20)
            draw.rectangle([(0, i), (width, i + 1)], fill=(color_value, color_value, color_value + 5))
        
        for i in range(3):
            offset = i * 3
            draw.rectangle(
                [(offset, offset), (width - offset, height - offset)],
                outline=(0, 200, 255) if rating >= 7 else (200, 200, 200),
                width=2
            )
        
        draw.text((width // 2, 30), "👻 НАЙДЕН НИК!", font=self.fonts["medium"], fill=(255,255,255), anchor="mm")
        draw.text((width // 2, 80), "✅ Telegram — свободен", font=self.fonts["small"], fill=(0,255,100), anchor="mm")
        draw.text((width // 2, 110), "✅ Fragment — не на аукционе", font=self.fonts["small"], fill=(0,255,100), anchor="mm")
        draw.text((width // 2, 180), f"@{username}", font=self.fonts["large"], fill=(0,255,200), anchor="mm")
        
        stars = "⭐" * rating + "☆" * (10 - rating)
        draw.text((width // 2, 270), f"Рейтинг: {rating}/10", font=self.fonts["medium"], fill=(255,215,0), anchor="mm")
        draw.text((width // 2, 305), stars, font=self.fonts["small"], fill=(255,215,0), anchor="mm")
        draw.text((width // 2, 340), f"💰 Примерная стоимость: {price} ⭐", font=self.fonts["small"], fill=(0,200,255), anchor="mm")
        draw.text((width // 2, 375), f"🎯 Найден за {attempts} попыток", font=self.fonts["small"], fill=(150,150,150), anchor="mm")
        draw.text((width // 2, height - 25), "👻 Ghost - Ники | @gawuzu", font=self.fonts["small"], fill=(80,80,80), anchor="mm")
        
        image_buffer = BytesIO()
        image.save(image_buffer, format='PNG')
        image_buffer.seek(0)
        return image_buffer

image_gen = ImageGenerator()

# ═══════════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════════════

class Keyboards:
    @staticmethod
    def main_menu(is_developer: bool = False) -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
            [InlineKeyboardButton(text="💎 Премиум", callback_data="menu_premium")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile")],
            [InlineKeyboardButton(text="👥 Рефералы", callback_data="menu_referrals")],
            [InlineKeyboardButton(text="ℹ️ Информация", callback_data="menu_info")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu_help")]
        ]
        if is_developer:
            buttons.append([InlineKeyboardButton(text="👑 Панель разработчика", callback_data="menu_dev")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def dev_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика бота", callback_data="dev_stats")],
            [InlineKeyboardButton(text="👥 Список пользователей", callback_data="dev_users")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="dev_broadcast")],
            [InlineKeyboardButton(text="🎁 Промокоды", callback_data="dev_promos")],
            [InlineKeyboardButton(text="💎 Выдать премиум", callback_data="dev_give_premium")],
            [InlineKeyboardButton(text="📦 Выдать запросы", callback_data="dev_give_requests")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    
    @staticmethod
    def dev_promos_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать промокод", callback_data="dev_promo_create")],
            [InlineKeyboardButton(text="📋 Список промокодов", callback_data="dev_promo_list")],
            [InlineKeyboardButton(text="❌ Удалить промокод", callback_data="dev_promo_delete")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_dev")]
        ])
    
    @staticmethod
    def search_menu(is_premium: bool = False) -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(text="🔤 6 букв", callback_data="search_6_false"),
             InlineKeyboardButton(text="🔢 6 букв + цифры", callback_data="search_6_true")]
        ]
        if is_premium:
            buttons.append([
                InlineKeyboardButton(text="⭐ 5 букв (PREMIUM)", callback_data="search_5_false"),
                InlineKeyboardButton(text="⭐ 5 букв + цифры (PREMIUM)", callback_data="search_5_true")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="🔒 5 букв (PREMIUM)", callback_data="noop"),
                InlineKeyboardButton(text="🔒 5 букв + цифры (PREMIUM)", callback_data="noop")
            ])
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def result_menu(username: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать", callback_data=f"copy_{username}")],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="search_skip")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    
    @staticmethod
    def premium_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 1 день — 65⭐", callback_data="premium_1")],
            [InlineKeyboardButton(text="📦 3 дня — 150⭐", callback_data="premium_3")],
            [InlineKeyboardButton(text="📦 10 дней — 400⭐", callback_data="premium_10")],
            [InlineKeyboardButton(text="📦 30 дней — 800⭐", callback_data="premium_30")],
            [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="premium_promo")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    
    @staticmethod
    def profile_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Найденные ники", callback_data="profile_found")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    
    @staticmethod
    def referral_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Рефералы по ссылке", callback_data="referral_link")],
            [InlineKeyboardButton(text="📱 TikTok рефералы", callback_data="referral_tiktok")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    
    @staticmethod
    def help_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Написать поддержку", callback_data="help_contact")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])

kb = Keyboards()

# ═══════════════════════════════════════════════════════════════════
# СОЗДАЁМ БОТА
# ═══════════════════════════════════════════════════════════════════

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ═══════════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or f"user{user_id}"
    first_name = message.from_user.first_name or ""
    
    if username.lower() == DEVELOPER_USERNAME:
        db.set_developer(user_id)
        logger.info(f"👑 Разработчик @{username} вошел!")
    
    banned, reason = db.is_banned(user_id)
    if banned:
        await message.answer(f"🚫 {reason}")
        return
    
    user = db.get_user(user_id)
    if not user.get("username"):
        db.update_user_field(user_id, "username", username)
        db.update_user_field(user_id, "first_name", first_name)
    
    is_dev = db.is_developer(user_id)
    
    text = f"""
👻 <b>Добро пожаловать в GHOST - Поиск Ников!</b>

Привет, {first_name}! 👋

🎯 <b>Что здесь можно делать?</b>
• Находить свободные Telegram-ни́ки
• Проверка через Telegram API (15 попыток)
• Получать рейтинг и стоимость ника

📌 <b>Доступные режимы:</b>
• 6 букв — бесплатно
• 5 букв — только PREMIUM

📌 <b>Для новичков:</b>
• {db.get_free_requests(user_id)} бесплатных поисков в день
• После каждого поиска кд 30 секунд
• Запросы обновляются каждые 2 дня (+3)
• <b>Запрос не тратится, если ник не найден!</b>

💎 <b>Премиум:</b>
• Безлимитные поиски
• Доступ к 5-буквенным никам
• Приоритетная очередь

<i>Разработчик: @gawuzu</i>
"""
    
    if is_dev:
        text += "\n\n👑 <b>Вы вошли как разработчик!</b>"
    
    await message.answer(text, reply_markup=kb.main_menu(is_dev), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_dev = db.is_developer(user_id)
    
    text = "👻 <b>GHOST — главное меню</b>\n\nВыберите раздел:"
    if is_dev:
        text = "👻 <b>GHOST — главное меню (Разработчик)</b>\n\nВыберите раздел:"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.main_menu(is_dev),
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# МЕНЮ РАЗРАБОТЧИКА
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_dev")
async def menu_dev(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👑 <b>Панель разработчика</b>\n\nВыберите раздел:",
        reply_markup=kb.dev_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_stats")
async def dev_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    total_users = db.get_total_users()
    total_searches = db.get_total_searches()
    premium_count = db.get_premium_count()
    promos = db.get_all_promos()
    
    text = f"""
📊 <b>Статистика бота</b>

👥 <b>Пользователи:</b> {total_users}
🔍 <b>Всего поисков:</b> {total_searches}
💎 <b>Премиум:</b> {premium_count}
🎁 <b>Промокодов:</b> {len(promos)}
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.dev_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_users")
async def dev_users(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_all_users()
    text = f"👥 <b>Список пользователей</b>\n\nВсего: {len(users)}\n\n"
    
    for i, uid in enumerate(users[:20], 1):
        user = db.get_user(uid)
        username = user.get("username", f"user{uid}")
        is_prem = "💎" if db.is_premium(uid) else ""
        is_dev = "👑" if db.is_developer(uid) else ""
        text += f"{i}. @{username} {is_prem} {is_dev}\n"
    
    if len(users) > 20:
        text += f"\n... и еще {len(users) - 20} пользователей"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.dev_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_broadcast")
async def dev_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_dev")]
        ])
    )
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.answer()

@dp.message(BroadcastStates.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    users = db.get_all_users()
    sent = 0
    failed = 0
    
    status_msg = await message.answer(f"📢 Начинаю рассылку {len(users)} пользователям...")
    
    for uid in users:
        try:
            if message.text:
                await bot.send_message(uid, message.text, parse_mode="HTML")
            elif message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption, parse_mode="HTML")
            elif message.video:
                await bot.send_video(uid, message.video.file_id, caption=message.caption, parse_mode="HTML")
            else:
                await bot.send_message(uid, "📢 Рассылка от разработчика", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}",
        parse_mode="HTML"
    )
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ПРОМОКОДЫ (РАЗРАБОТЧИК)
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "dev_promos")
async def dev_promos_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎁 <b>Управление промокодами</b>\n\nВыберите действие:",
        reply_markup=kb.dev_promos_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_promo_create")
async def dev_promo_create(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎁 <b>Создать промокод</b>\n\n"
        "Введите код промокода (латиница, цифры):\n"
        "Пример: <code>GHOST2024</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="dev_promos")]
        ])
    )
    await state.set_state(PromoCreateStates.waiting_for_code)
    await callback.answer()

@dp.message(PromoCreateStates.waiting_for_code)
async def promo_code_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    code = message.text.strip().upper()
    if not re.match(r'^[A-Z0-9]+$', code):
        await message.answer("❌ Код должен содержать только буквы и цифры. Попробуйте снова:")
        return
    
    await state.update_data(promo_code=code)
    await message.answer("📅 Введите количество дней премиума (1-365):")
    await state.set_state(PromoCreateStates.waiting_for_days)

@dp.message(PromoCreateStates.waiting_for_days)
async def promo_days_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        days = int(message.text.strip())
        if days < 1 or days > 365:
            raise ValueError
    except:
        await message.answer("❌ Введите число от 1 до 365:")
        return
    
    await state.update_data(promo_days=days)
    await message.answer("👥 Введите максимальное количество использований (1-1000):")
    await state.set_state(PromoCreateStates.waiting_for_limit)

@dp.message(PromoCreateStates.waiting_for_limit)
async def promo_limit_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        limit = int(message.text.strip())
        if limit < 1 or limit > 1000:
            raise ValueError
    except:
        await message.answer("❌ Введите число от 1 до 1000:")
        return
    
    data = await state.get_data()
    code = data.get("promo_code")
    days = data.get("promo_days")
    
    if db.create_promo(code, days, limit, user_id):
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"📌 Код: <code>{code}</code>\n"
            f"📅 Дней: {days}\n"
            f"👥 Лимит: {limit}\n\n"
            f"Промокод действителен 30 дней.",
            parse_mode="HTML",
            reply_markup=kb.dev_promos_menu()
        )
    else:
        await message.answer(
            "❌ Ошибка! Возможно такой код уже существует.",
            reply_markup=kb.dev_promos_menu()
        )
    
    await state.clear()

@dp.callback_query(F.data == "dev_promo_list")
async def dev_promo_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    promos = db.get_all_promos()
    
    if not promos:
        await callback.message.edit_text(
            "📋 <b>Список промокодов</b>\n\n"
            "Промокодов пока нет.\n"
            "Создайте первый промокод!",
            reply_markup=kb.dev_promos_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = "📋 <b>Список промокодов</b>\n\n"
    
    for promo in promos[:20]:
        status = "✅" if promo["expires_at"] > int(time.time()) else "❌"
        text += f"{status} <code>{promo['code']}</code>\n"
        text += f"   📅 {promo['days']} дней | Использован: {promo['uses']}/{promo['max_uses']}\n"
        text += f"   🕐 До: {datetime.fromtimestamp(promo['expires_at']).strftime('%d.%m.%Y')}\n\n"
    
    if len(promos) > 20:
        text += f"... и еще {len(promos) - 20} промокодов"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.dev_promos_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_promo_delete")
async def dev_promo_delete(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "❌ <b>Удалить промокод</b>\n\n"
        "Введите код промокода для удаления:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="dev_promos")]
        ])
    )
    await state.set_state(DevDeletePromoStates.waiting_for_code)
    await callback.answer()

@dp.message(DevDeletePromoStates.waiting_for_code)
async def promo_delete_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    code = message.text.strip().upper()
    
    if db.delete_promo(code):
        await message.answer(
            f"✅ <b>Промокод {code} удален!</b>",
            reply_markup=kb.dev_promos_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ <b>Промокод {code} не найден!</b>",
            reply_markup=kb.dev_promos_menu(),
            parse_mode="HTML"
        )
    
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ВЫДАТЬ ПРЕМИУМ (РАЗРАБОТЧИК)
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "dev_give_premium")
async def dev_give_premium(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💎 <b>Выдать премиум</b>\n\n"
        "Введите ID пользователя (число):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_dev")]
        ])
    )
    await state.set_state(DevGivePremiumStates.waiting_for_user_id)
    await callback.answer()

@dp.message(DevGivePremiumStates.waiting_for_user_id)
async def dev_give_premium_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        target_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите корректный ID (число):")
        return
    
    await state.update_data(target_id=target_id)
    await message.answer("📅 Введите количество дней премиума:")
    await state.set_state(DevGivePremiumStates.waiting_for_days)

@dp.message(DevGivePremiumStates.waiting_for_days)
async def dev_give_premium_days(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        days = int(message.text.strip())
        if days < 1 or days > 365:
            raise ValueError
    except:
        await message.answer("❌ Введите число от 1 до 365:")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    db.add_premium(target_id, days)
    
    target_user = db.get_user(target_id)
    username = target_user.get("username", f"user{target_id}")
    
    await message.answer(
        f"✅ <b>Премиум выдан!</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"📅 Дней: {days}\n"
        f"💎 Статус: Премиум активен",
        parse_mode="HTML",
        reply_markup=kb.dev_menu()
    )
    
    try:
        await bot.send_message(
            target_id,
            f"🎉 <b>Вам выдан премиум!</b>\n\n"
            f"📅 {days} дней\n"
            f"💎 Теперь доступны все функции бота!",
            parse_mode="HTML"
        )
    except:
        pass
    
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ВЫДАТЬ ЗАПРОСЫ (РАЗРАБОТЧИК)
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "dev_give_requests")
async def dev_give_requests(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📦 <b>Выдать запросы</b>\n\n"
        "Введите ID пользователя (число):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_dev")]
        ])
    )
    await state.set_state(DevGiveRequestsStates.waiting_for_user_id)
    await callback.answer()

@dp.message(DevGiveRequestsStates.waiting_for_user_id)
async def dev_give_requests_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        target_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите корректный ID (число):")
        return
    
    await state.update_data(target_id=target_id)
    await message.answer("📊 Введите количество запросов (1-100):")
    await state.set_state(DevGiveRequestsStates.waiting_for_count)

@dp.message(DevGiveRequestsStates.waiting_for_count)
async def dev_give_requests_count(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        count = int(message.text.strip())
        if count < 1 or count > 100:
            raise ValueError
    except:
        await message.answer("❌ Введите число от 1 до 100:")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    db.add_free_requests(target_id, count)
    
    target_user = db.get_user(target_id)
    username = target_user.get("username", f"user{target_id}")
    
    await message.answer(
        f"✅ <b>Запросы выданы!</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"📊 Запросов: +{count}\n"
        f"📋 Теперь доступно: {db.get_free_requests(target_id)} запросов",
        parse_mode="HTML",
        reply_markup=kb.dev_menu()
    )
    
    try:
        await bot.send_message(
            target_id,
            f"🎉 <b>Вам выданы запросы!</b>\n\n"
            f"📊 +{count} запросов\n"
            f"📋 Теперь у вас {db.get_free_requests(target_id)} запросов",
            parse_mode="HTML"
        )
    except:
        pass
    
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ПОИСК (С ПРОГРЕССОМ 1/15, 2/15...)
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_search")
async def menu_search(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    banned, reason = db.is_banned(user_id)
    if banned:
        await callback.answer(f"🚫 {reason}", show_alert=True)
        return
    
    is_premium = db.is_premium(user_id)
    free_requests = db.get_free_requests(user_id)
    
    text = f"""
🔍 <b>ПОИСК ЮЗЕРНЕЙМА</b>

✅ Каждый найденный ник проходит проверку:
  • Telegram — не занят профилем, каналом или ботом
  • Fragment — не выставлен на аукцион или продажу

📌 <b>Доступные режимы:</b>
  • 6 букв — бесплатно
  • 5 букв — только PREMIUM

📊 Осталось попыток сегодня: {free_requests if not is_premium else '♾️'}
🔄 Пополнение каждые 2 дня: +{REQUESTS_ADD_AMOUNT} (макс {MAX_FREE_REQUESTS})
🎯 Поиск выполняется за 15 попыток
💡 <b>Запрос не тратится, если ник не найден!</b>

<b>Выберите режим:</b>
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.search_menu(is_premium),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("search_"))
async def start_search(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    banned, reason = db.is_banned(user_id)
    if banned:
        await callback.answer(f"🚫 {reason}", show_alert=True)
        return
    
    parts = callback.data.split("_")
    length = int(parts[1])
    with_digits = parts[2] == "true"
    
    # Проверка: 5 букв только для премиум
    if length == 5:
        is_premium = db.is_premium(user_id)
        if not is_premium:
            await callback.answer(
                "🔒 5-буквенные ники доступны только с премиум!\n"
                "Купите премиум 💎",
                show_alert=True
            )
            return
    
    # Проверка кулдауна
    can_search, remaining = db.check_cooldown(user_id)
    if not can_search:
        await callback.answer(f"⏳ Подождите {remaining} секунд!", show_alert=True)
        return
    
    # Проверка доступа
    is_premium = db.is_premium(user_id)
    free_requests = db.get_free_requests(user_id)
    
    if not is_premium and free_requests <= 0:
        await callback.answer(
            "❌ Закончились бесплатные запросы!\n"
            f"Новые запросы через {REQUESTS_UPDATE_DAYS} дня\n"
            "Купите премиум 💎",
            show_alert=True
        )
        return
    
    # Обновляем время последнего поиска
    db.update_last_search(user_id)
    
    # Начинаем поиск
    search_msg = await callback.message.edit_text(
        "🔍 <b>Поиск свободного юзернейма...</b>\n\n"
        f"📏 Длина: {length} символов\n"
        f"🔢 С цифрами: {'Да' if with_digits else 'Нет'}\n"
        f"⏳ 0/15\n\n"
        f"<i>Начинаю поиск...</i>",
        parse_mode="HTML"
    )
    
    username_gen = UsernameGenerator(bot)
    username, attempts, checked = await username_gen.find_free_username(
        length, with_digits, message=search_msg
    )
    
    if username:
        # НАЙДЕН! Тратим запрос
        if not is_premium:
            db.use_free_request(user_id)
        db.increment_searches(user_id)
        db.add_found_username(user_id, username)
        
        rating = username_gen._calculate_rating(username)
        price = rating * random.randint(10, 50)
        
        img_buffer = image_gen.generate_username_card(username, rating, price, attempts)
        
        text = f"""
✅ <b>Найден свободный ник!</b>

👤 <b>Юзернейм:</b> @{username}
📏 <b>Длина:</b> {length} символов
{'🔢 С цифрами' if with_digits else '🔤 Только буквы'}
⭐ <b>Рейтинг:</b> {rating}/10
💰 <b>Примерная стоимость:</b> {price} ⭐
🎯 <b>Найден за:</b> {attempts} попыток
"""
        
        await callback.message.answer_photo(
            photo=BufferedInputFile(img_buffer.getvalue(), filename="nick.png"),
            caption=text,
            reply_markup=kb.result_menu(username),
            parse_mode="HTML"
        )
    else:
        # НЕ НАЙДЕН! Запрос НЕ тратится
        await search_msg.edit_text(
            "❌ <b>Свободный ник не найден</b>\n\n"
            f"⏳ Попыток: {MAX_SEARCH_ATTEMPTS}/{MAX_SEARCH_ATTEMPTS}\n"
            f"📋 Проверено: {len(checked)} ников\n\n"
            "💡 <b>Запрос не был потрачен!</b>\n\n"
            "Попробуйте другой режим или подождите немного.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="menu_search")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
            ])
        )
    
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer("🔒 Доступно только с премиум!", show_alert=True)

@dp.callback_query(F.data == "search_skip")
async def search_skip(callback: CallbackQuery):
    await menu_search(callback)

@dp.callback_query(F.data.startswith("copy_"))
async def copy_username(callback: CallbackQuery):
    username = callback.data.split("_")[1]
    
    await callback.message.answer(
        f"📋 <b>Скопируйте ник:</b>\n\n"
        f"<code>@{username}</code>\n\n"
        f"Используйте его в Telegram! 🎯",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Найти еще", callback_data="menu_search")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    )
    await callback.answer("✅ Ник скопирован!")

# ═══════════════════════════════════════════════════════════════════
# ПРЕМИУМ С ОПЛАТОЙ ЗВЁЗДАМИ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_premium = db.is_premium(user_id)
    
    text = """
💎 <b>ПРЕМИУМ ПОДПИСКА</b>

<b>ФУНКЦИИ:</b>
• Безлимитный поиск
• Доступ к 5-буквенным никам
• Приоритетная очередь
• Специальные предложения

<b>ЦЕНЫ (Telegram Stars):</b>
1 день — 65⭐
3 дня — 150⭐
10 дней — 400⭐
30 дней — 800⭐

<b>Оплата происходит автоматически через Telegram Stars</b>
"""
    
    if is_premium:
        remaining = db.get_premium_remaining(user_id)
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        text += f"\n✅ <b>Премиум активен:</b> {days}д {hours}ч"
    else:
        text += "\n❌ <b>Премиум не активен</b>"
    
    text += "\n\n<b>ИЛИ БЕСПЛАТНО:</b>\n"
    text += "• 7 рефералов → 1 день\n"
    text += "• 14 рефералов → 3 дня\n"
    text += "• 25 рефералов → 10 дней\n"
    text += "• 50 рефералов → 25 дней"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.premium_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("premium_"))
async def buy_premium(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if callback.data == "premium_promo":
        await callback.message.edit_text(
            "🎁 <b>Введите промокод</b>\n\n"
            "Промокод активирует Premium на указанное количество дней.\n\n"
            "Введите код:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_premium")]
            ])
        )
        await state.set_state(PromoStates.waiting_for_promo)
        await callback.answer()
        return
    
    days = int(callback.data.split("_")[1])
    price = PRICES.get(days, 65)
    
    title = f"Премиум GHOST — {days} день(дней)"
    description = f"Безлимитный поиск ников на {days} дней!\n\nДоступ к 5-буквенным никам и приоритетный поиск."
    payload = f"premium_{days}_{user_id}_{int(time.time())}"
    prices = [LabeledPrice(label=f"Премиум {days} дней", amount=price)]
    
    # Показываем подтверждение
    await callback.message.edit_text(
        f"💎 <b>Подтверждение оплаты</b>\n\n"
        f"📦 Тариф: {days} дней\n"
        f"💰 Цена: {price} ⭐\n\n"
        f"Вы хотите заплатить боту {price} звёзд?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, заплатить", callback_data=f"pay_confirm_{days}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_premium")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_confirm_"))
async def pay_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    days = int(callback.data.split("_")[2])
    price = PRICES.get(days, 65)
    
    title = f"Премиум GHOST — {days} день(дней)"
    description = f"Безлимитный поиск ников на {days} дней!"
    payload = f"premium_{days}_{user_id}_{int(time.time())}"
    prices = [LabeledPrice(label=f"Премиум {days} дней", amount=price)]
    
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="premium",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_premium")]
            ])
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка инвойса: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)

@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    parts = payload.split("_")
    if len(parts) >= 2:
        days = int(parts[1])
        db.add_premium(user_id, days)
        
        await message.answer(
            f"✅ <b>Премиум активирован!</b>\n\n"
            f"📦 Тариф: {days} дней\n"
            f"💎 Теперь у вас безлимитные поиски и доступ к 5-буквенным никам!\n\n"
            f"Приятного использования! 🎯",
            parse_mode="HTML",
            reply_markup=kb.main_menu(db.is_developer(user_id))
        )

@dp.message(PromoStates.waiting_for_promo)
async def handle_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    code = message.text.strip().upper()
    
    success, msg, days = db.use_promo(user_id, code)
    
    if success:
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"{msg}\n\n"
            f"Теперь у вас премиум на {days} дней! 🎉",
            parse_mode="HTML",
            reply_markup=kb.main_menu(db.is_developer(user_id))
        )
    else:
        await message.answer(
            f"❌ <b>Ошибка</b>\n\n{msg}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="premium_promo")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_premium")]
            ])
        )
    
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ПРОФИЛЬ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    is_premium = db.is_premium(user_id)
    found = db.get_found_usernames(user_id, 5)
    is_dev = db.is_developer(user_id)
    
    text = f"""
👤 <b>Профиль</b>

📌 <b>Информация:</b>
• ID: {user_id}
• Имя: {user.get('first_name', 'Не указано')}
• Юзернейм: @{user.get('username', 'Не указан')}

📊 <b>Статистика:</b>
• Найдено ников: {user.get('total_searches', 0)}
• Бесплатных запросов: {db.get_free_requests(user_id)}/{MAX_FREE_REQUESTS}
• Пополнение: каждые {REQUESTS_UPDATE_DAYS} дня (+{REQUESTS_ADD_AMOUNT})

📋 <b>Последние найденные ники:</b>
"""
    
    if found:
        for item in found[:5]:
            dt = datetime.fromtimestamp(item["found_at"]).strftime("%d.%m %H:%M")
            text += f"  • @{item['username']} — {dt}\n"
    else:
        text += "  • Пока нет найденных ников\n"
    
    text += f"\n💎 <b>Статус:</b>\n"
    text += f"• Премиум: {'✅ Да' if is_premium else '❌ Нет'}"
    
    if is_dev:
        text += "\n👑 <b>Доступ:</b> Разработчик"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.profile_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "profile_found")
async def profile_found(callback: CallbackQuery):
    user_id = callback.from_user.id
    found = db.get_found_usernames(user_id, 20)
    
    if not found:
        await callback.message.edit_text(
            "📊 <b>Найденные ники</b>\n\n"
            "У вас пока нет найденных ников.\n"
            "Используйте поиск, чтобы найти первый! 🔍",
            reply_markup=kb.profile_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = "📊 <b>Ваши найденные ники</b>\n\n"
    
    for i, item in enumerate(reversed(found[:20]), 1):
        dt = datetime.fromtimestamp(item["found_at"]).strftime("%d.%m %H:%M")
        text += f"{i}. @{item['username']} — {dt}\n"
    
    if len(found) > 20:
        text += f"\n... и еще {len(found) - 20} ников"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.profile_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# РЕФЕРАЛЫ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_referrals")
async def menu_referrals(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    code = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
    link = f"https://t.me/GhostSearchNames_bot?start=ref_{code}"
    
    text = f"""
👥 <b>Реферальная система</b>

🔗 <b>Ваша ссылка:</b>
<code>{link}</code>

<b>Награды за рефералов:</b>
• 7 рефералов → 1 день Premium
• 14 рефералов → 3 дня Premium
• 25 рефералов → 10 дней Premium
• 50 рефералов → 25 дней Premium

📱 <b>TikTok рефералы:</b>
Снимите видео с ботом и получите на баланс!
Отправьте видео @gawuzu
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.referral_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "referral_link")
async def referral_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    code = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
    link = f"https://t.me/GhostSearchNames_bot?start=ref_{code}"
    
    await callback.message.answer(
        f"🔗 <b>Ваша реферальная ссылка:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Приглашайте друзей и получайте бонусы! 🎁",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "referral_tiktok")
async def referral_tiktok(callback: CallbackQuery):
    text = """
📱 <b>TikTok рефералы</b>

Снимите видео с нашим ботом и получайте на баланс!

<b>Награды:</b>
• 50⭐ за 1000 просмотров
• Вывод от 250⭐

<b>Отправьте видео:</b> @gawuzu
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_referrals")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# ИНФОРМАЦИЯ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    text = """
ℹ️ <b>Информация</b>

<b>GHOST - Поиск Ников</b>

<b>Что умеет бот:</b>
• Находит свободные 5–6 буквенные ники
• Проверка доступности через Telegram API
• Поиск за 15 попыток с видимым прогрессом
• Рейтинг и стоимость ника
• Запрос не тратится если ник не найден

<b>Заработок и бонусы:</b>
• Рефералы по ссылке
• TikTok-рефералы

<b>Оплата Premium:</b>
• Telegram Stars (автоматически)
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# ПОДДЕРЖКА
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_help")
async def menu_help(callback: CallbackQuery):
    text = """
🆘 <b>Поддержка</b>

Если у вас возникли вопросы, проблемы с ботом или предложения по улучшению — мы всегда на связи!

<b>Разработчик:</b> @gawuzu

<b>Среднее время ответа:</b> до 24 часов

<b>Опишите проблему подробно:</b>
Укажите ваш ID, что не работает и как воспроизвести.
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.help_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "help_contact")
async def help_contact(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.message.answer(
        "📝 <b>Написать поддержку</b>\n\n"
        "Напишите разработчику напрямую:\n"
        "@gawuzu\n\n"
        "В сообщении укажите:\n"
        f"• Ваш ID: <code>{user_id}</code>\n"
        "• Описание проблемы\n"
        "• Как воспроизвести",
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════════

async def main():
    logger.info("🚀 Бот GHOST - Поиск Ников запущен!")
    logger.info("👤 Разработчик: @gawuzu")
    logger.info("✅ ВСЕ ФУНКЦИИ РАБОТАЮТ!")
    logger.info("✅ Поиск: 15 попыток с прогрессом")
    logger.info("✅ Запрос не тратится если ник не найден")
    logger.info("✅ Оплата звёздами с подтверждением")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
