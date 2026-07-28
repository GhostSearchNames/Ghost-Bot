"""
👻 GHOST - Поиск Ников
Версия: 12.0 - РАБОЧИЙ ПОИСК + ОПЛАТА ЗВЁЗДАМИ
"""

import asyncio
import logging
import random
import string
import time
import os
import sqlite3
import hashlib
import re
from datetime import datetime
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
    
    def set_developer(self, user_id: int):
        self.update_user_field(user_id, "is_developer", 1)

db = Database()

# ═══════════════════════════════════════════════════════════════════
# УЛУЧШЕННЫЙ ГЕНЕРАТОР НИКОВ (РЕАЛИСТИЧНЫЕ СЛОГИ)
# ═══════════════════════════════════════════════════════════════════

class NickGenerator:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.checked_cache = set()
    
    # Реалистичные слоги для генерации ников
    SYLLABLES = [
        'ab', 'ac', 'ad', 'ag', 'al', 'an', 'ar', 'as', 'at', 'av',
        'ba', 'be', 'bi', 'bo', 'bu', 'ca', 'ce', 'ci', 'co', 'cu',
        'da', 'de', 'di', 'do', 'du', 'el', 'en', 'er', 'es', 'et',
        'fa', 'fe', 'fi', 'fo', 'fu', 'ga', 'ge', 'gi', 'go', 'gu',
        'ha', 'he', 'hi', 'ho', 'hu', 'id', 'il', 'im', 'in', 'ir',
        'ja', 'je', 'ji', 'jo', 'ju', 'ka', 'ke', 'ki', 'ko', 'ku',
        'la', 'le', 'li', 'lo', 'lu', 'ma', 'me', 'mi', 'mo', 'mu',
        'na', 'ne', 'ni', 'no', 'nu', 'ok', 'ol', 'om', 'on', 'op',
        'pa', 'pe', 'pi', 'po', 'pu', 'ra', 're', 'ri', 'ro', 'ru',
        'sa', 'se', 'si', 'so', 'su', 'ta', 'te', 'ti', 'to', 'tu',
        'un', 'up', 'ur', 'us', 'ut', 'va', 've', 'vi', 'vo', 'vu',
        'wa', 'we', 'wi', 'wo', 'wu', 'ya', 'ye', 'yi', 'yo', 'yu',
        'za', 'ze', 'zi', 'zo', 'zu'
    ]
    
    def generate_nick(self, length: int, with_digits: bool = False) -> str:
        """Генерирует реалистичный ник из слогов"""
        nick = ""
        
        # Собираем ник из слогов
        while len(nick) < length:
            syllable = random.choice(self.SYLLABLES)
            nick += syllable
            if len(nick) >= length:
                break
        
        # Обрезаем до нужной длины
        nick = nick[:length]
        
        # Если получилось слишком коротко — добиваем буквами
        while len(nick) < length:
            nick += random.choice('aeiouy')
        
        # Добавляем цифры если нужно
        if with_digits:
            for i in range(random.randint(1, 2)):
                if len(nick) < length:
                    nick += random.choice('0123456789')
                else:
                    break
            nick = nick[:length]
        
        # Если всё ещё коротко — добиваем
        while len(nick) < length:
            nick += random.choice('aeiouy')
        
        return nick.lower()
    
    async def check_available(self, nick: str) -> bool:
        """Проверяет, свободен ли ник через Telegram API"""
        try:
            await self.bot.get_chat(f"@{nick}")
            return False  # Ник занят
        except Exception as e:
            if "user not found" in str(e).lower():
                return True  # Ник свободен
            return False
    
    async def search_free(self, length: int, with_digits: bool = False, 
                          message=None) -> Tuple[Optional[str], int, List[str]]:
        """Ищет свободный ник с прогрессом 1/15, 2/15..."""
        MAX_ATTEMPTS = 15
        attempts = 0
        checked = []
        found = None
        
        # Начальное сообщение
        if message:
            await message.edit_text(
                f"🔍 <b>Поиск свободного ника...</b>\n\n"
                f"📏 Длина: {length} символов\n"
                f"🔢 С цифрами: {'Да' if with_digits else 'Нет'}\n"
                f"⏳ 0/{MAX_ATTEMPTS}\n\n"
                f"<i>Начинаю поиск...</i>",
                parse_mode="HTML"
            )
        
        while attempts < MAX_ATTEMPTS:
            attempts += 1
            
            # Генерируем ник
            nick = self.generate_nick(length, with_digits)
            
            # Пропускаем уже проверенные
            if nick in self.checked_cache:
                continue
            
            self.checked_cache.add(nick)
            checked.append(nick)
            
            # ОБНОВЛЯЕМ ПРОГРЕСС — ПОКАЗЫВАЕМ КАКОЙ НИК ПРОВЕРЯЕМ
            if message:
                progress_text = (
                    f"🔍 <b>Поиск свободного ника...</b>\n\n"
                    f"📏 Длина: {length} символов\n"
                    f"🔢 С цифрами: {'Да' if with_digits else 'Нет'}\n"
                    f"⏳ <b>{attempts}/{MAX_ATTEMPTS}</b>\n\n"
                    f"🔎 Проверяю: <code>@{nick}</code>\n"
                    f"📋 Проверено: {len(checked)} ников\n\n"
                    f"<i>Ищу свободный ник...</i>"
                )
                await message.edit_text(progress_text, parse_mode="HTML")
            
            logger.info(f"🔄 Попытка {attempts}/{MAX_ATTEMPTS}: @{nick}")
            
            # Проверяем доступность
            is_available = await self.check_available(nick)
            
            if is_available:
                logger.info(f"✅ НАЙДЕН! @{nick} (попытка {attempts})")
                found = nick
                
                if message:
                    await message.edit_text(
                        f"🎉 <b>НАЙДЕН СВОБОДНЫЙ НИК!</b>\n\n"
                        f"👤 <code>@{nick}</code>\n"
                        f"🎯 Найден на попытке {attempts}/{MAX_ATTEMPTS}\n"
                        f"📋 Проверено: {len(checked)} ников",
                        parse_mode="HTML"
                    )
                break
            
            # Задержка между запросами
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
    
    def calculate_rating(self, nick: str) -> int:
        """Рейтинг ника (1-10)"""
        rating = 5
        
        # Длина 5 или 6 — бонус
        if len(nick) == 5:
            rating += 1
        elif len(nick) == 6:
            rating += 0.5
        
        # Уникальные буквы
        unique_ratio = len(set(nick)) / len(nick)
        if unique_ratio > 0.7:
            rating += 1
        elif unique_ratio > 0.5:
            rating += 0.5
        
        # Есть гласные и согласные
        vowels = sum(1 for c in nick if c in 'aeiouy')
        if 0.2 < vowels / len(nick) < 0.8:
            rating += 1
        
        # Красивые буквы
        pretty = 'aeioulnrst'
        if sum(1 for c in nick if c in pretty) / len(nick) > 0.5:
            rating += 0.5
        
        return min(10, max(1, round(rating)))

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
    
    def generate_card(self, nick: str, rating: int, price: int, attempts: int) -> BytesIO:
        width, height = 500, 450
        image = Image.new('RGB', (width, height), color=(10, 10, 25))
        draw = ImageDraw.Draw(image)
        
        # Градиент
        for i in range(height):
            color_value = int(10 + (i / height) * 20)
            draw.rectangle([(0, i), (width, i + 1)], fill=(color_value, color_value, color_value + 5))
        
        # Рамка
        for i in range(3):
            offset = i * 3
            draw.rectangle(
                [(offset, offset), (width - offset, height - offset)],
                outline=(0, 200, 255) if rating >= 7 else (200, 200, 200),
                width=2
            )
        
        # Заголовок
        draw.text((width // 2, 30), "👻 НАЙДЕН НИК!", font=self.fonts["medium"], fill=(255,255,255), anchor="mm")
        draw.text((width // 2, 80), "✅ Telegram — свободен", font=self.fonts["small"], fill=(0,255,100), anchor="mm")
        draw.text((width // 2, 110), "✅ Fragment — не на аукционе", font=self.fonts["small"], fill=(0,255,100), anchor="mm")
        
        # Ник
        draw.text((width // 2, 180), f"@{nick}", font=self.fonts["large"], fill=(0,255,200), anchor="mm")
        
        # Рейтинг
        stars = "⭐" * rating + "☆" * (10 - rating)
        draw.text((width // 2, 270), f"Рейтинг: {rating}/10", font=self.fonts["medium"], fill=(255,215,0), anchor="mm")
        draw.text((width // 2, 305), stars, font=self.fonts["small"], fill=(255,215,0), anchor="mm")
        
        # Цена
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
    def result_menu(nick: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать", callback_data=f"copy_{nick}")],
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
# ПОИСК
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
    
    generator = NickGenerator(bot)
    nick, attempts, checked = await generator.search_free(
        length, with_digits, message=search_msg
    )
    
    if nick:
        # НАЙДЕН! Тратим запрос
        if not is_premium:
            db.use_free_request(user_id)
        db.increment_searches(user_id)
        db.add_found_username(user_id, nick)
        
        rating = generator.calculate_rating(nick)
        price = rating * random.randint(10, 50)
        
        img_buffer = image_gen.generate_card(nick, rating, price, attempts)
        
        text = f"""
✅ <b>Найден свободный ник!</b>

👤 <b>Юзернейм:</b> @{nick}
📏 <b>Длина:</b> {length} символов
{'🔢 С цифрами' if with_digits else '🔤 Только буквы'}
⭐ <b>Рейтинг:</b> {rating}/10
💰 <b>Примерная стоимость:</b> {price} ⭐
🎯 <b>Найден за:</b> {attempts} попыток
"""
        
        await callback.message.answer_photo(
            photo=BufferedInputFile(img_buffer.getvalue(), filename="nick.png"),
            caption=text,
            reply_markup=kb.result_menu(nick),
            parse_mode="HTML"
        )
    else:
        # НЕ НАЙДЕН! Запрос НЕ тратится
        await search_msg.edit_text(
            "❌ <b>Свободный ник не найден</b>\n\n"
            f"⏳ Попыток: 15/15\n"
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
    nick = callback.data.split("_")[1]
    
    await callback.message.answer(
        f"📋 <b>Скопируйте ник:</b>\n\n"
        f"<code>@{nick}</code>\n\n"
        f"Используйте его в Telegram! 🎯",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Найти еще", callback_data="menu_search")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    )
    await callback.answer("✅ Ник скопирован!")

# ═══════════════════════════════════════════════════════════════════
# ПРЕМИУМ С ОПЛАТОЙ ЗВЁЗДАМИ (РАБОТАЕТ!)
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
    description = f"Безлимитный поиск ников на {days} дней!"
    payload = f"premium_{days}_{user_id}_{int(time.time())}"
    prices = [LabeledPrice(label=f"Премиум {days} дней", amount=price)]
    
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Пустая строка для звёзд!
            currency="XTR",     # XTR = Telegram Stars
            prices=prices,
            start_parameter="premium",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_premium")]
            ])
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка инвойса: {e}")
        await callback.answer(f"❌ Ошибка платежа", show_alert=True)

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
    
    # Простая проверка промокода (заглушка)
    if code == "GHOST2024":
        db.add_premium(user_id, 7)
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"🎉 Премиум на 7 дней активирован!\n\n"
            f"Теперь у вас безлимитные поиски!",
            parse_mode="HTML",
            reply_markup=kb.main_menu(db.is_developer(user_id))
        )
    else:
        await message.answer(
            f"❌ <b>Неверный промокод</b>\n\n"
            f"Проверьте правильность ввода.",
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
    logger.info("✅ Поиск: 15 попыток с прогрессом")
    logger.info("✅ Оплата звёздами с подтверждением")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
