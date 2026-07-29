"""
👻 GHOST - Поиск Ников
Версия: 33.0 - МУЛЬТИЯЗЫЧНАЯ
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
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, types, F, html
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    PreCheckoutQuery, SuccessfulPayment, LabeledPrice,
    BufferedInputFile, ContentType
)
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
import aiohttp
from aiohttp import web

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
BACKUP_DIR = "backups"
MAX_SEARCH_ATTEMPTS = 15
BOT_URL = "https://ghost-bot-7jbh.onrender.com"

os.makedirs(BACKUP_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# ЯЗЫКИ
# ═══════════════════════════════════════════════════════════════════

LANGUAGES = {
    "ru": {
        "name": "🇷🇺 Русский",
        "welcome": "👻 <b>Добро пожаловать в GHOST - Поиск Ников!</b>\n\nПривет, {name}! 👋\n\n🎯 <b>Что здесь можно делать?</b>\n• Находить свободные Telegram-ни́ки\n• Двойная проверка: API + Web\n• Получать рейтинг и стоимость ника\n\n📌 <b>Доступные режимы:</b>\n• 6 букв — бесплатно\n• 5 букв — только PREMIUM\n\n📌 <b>Для новичков:</b>\n• {requests} бесплатных поисков в день\n• После каждого поиска кд 30 секунд\n• Запросы обновляются каждые 2 дня (+3)\n• <b>Запрос не тратится, если ник не найден!</b>\n\n💎 <b>Премиум:</b>\n• Безлимитные поиски\n• Доступ к 5-буквенным никам\n\n<i>Разработчик: @gawuzu</i>",
        "search": "🔍 ПОИСК ЮЗЕРНЕЙМА",
        "search_desc": "✅ Двойная проверка:\n  • Telegram API — не занят профилем\n  • Web-страница — не на аукционе Fragment\n\n📌 Доступные режимы:\n  • 6 букв — бесплатно\n  • 5 букв — только PREMIUM\n\n📊 Осталось попыток: {requests}\n🎯 Поиск за 15 попыток\n💡 Запрос не тратится, если ник не найден!\n\n<b>Выберите режим:</b>",
        "premium": "💎 ПРЕМИУМ ПОДПИСКА\n\n<b>ФУНКЦИИ:</b>\n• Безлимитный поиск\n• Доступ к 5-буквенным никам\n\n<b>ЦЕНЫ:</b>\n1 день — 65⭐\n3 дня — 150⭐\n10 дней — 400⭐\n30 дней — 800⭐",
        "profile": "👤 ПРОФИЛЬ\n\n📌 ID: {id}\n📌 Имя: {name}\n📌 Юзернейм: @{username}\n\n📊 СТАТИСТИКА:\n• Найдено: {found}\n• Запросов: {requests}/{max}\n\n📋 Последние найденные:\n{nicks}\n\n💎 Премиум: {premium}",
        "referral": "👥 РЕФЕРАЛЫ\n\n🔗 Ссылка:\n<code>{link}</code>\n\n<b>Награды:</b>\n• 7 → 1 день\n• 14 → 3 дня\n• 25 → 10 дней\n• 50 → 25 дней",
        "info": "ℹ️ GHOST - Поиск Ников\n\n• Находит свободные ники 5-6 букв\n• Двойная проверка: API + Web\n• 15 попыток с прогрессом\n• Рейтинг и цена в $\n• Запрос не тратится если ник не найден\n• Оплата: Telegram Stars",
        "help": "🆘 ПОДДЕРЖКА\n\nРазработчик: @gawuzu",
        "found": "✅ Найден свободный ник!\n\n👤 Юзернейм: @{nick}\n📏 Длина: {length} символов\n{with_digits}⭐ Рейтинг: {rating}/10\n💰 Ценность: ${price}\n🎯 Найден за: {attempts} попыток",
        "not_found": "❌ Свободный ник не найден\n\n⏳ Попыток: 15/15\n📋 Проверено: {checked} ников\n\n💡 Запрос не был потрачен!",
        "copy": "📋 <code>@{nick}</code>\n\n✅ Ник скопирован! Используйте его в Telegram.",
        "premium_active": "\n✅ Активен: {days}д {hours}ч",
        "premium_inactive": "\n❌ Не активен",
        "dev_panel": "👑 ПАНЕЛЬ РАЗРАБОТЧИКА\n\nВыберите раздел:",
        "dev_stats": "📊 СТАТИСТИКА БОТА\n\n👥 Пользователи: {users}\n🔍 Всего поисков: {searches}\n💎 Премиум: {premium}",
        "dev_users": "👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ\n\nВсего: {total}\n\n{users}",
        "dev_broadcast": "📢 РАССЫЛКА\n\nОтправьте сообщение для рассылки:",
        "dev_promos": "🎁 УПРАВЛЕНИЕ ПРОМОКОДАМИ",
        "dev_promo_create": "🎁 СОЗДАТЬ ПРОМОКОД\n\nВведите код (буквы и цифры):",
        "dev_promo_list": "📋 СПИСОК ПРОМОКОДОВ",
        "dev_promo_delete": "❌ УДАЛИТЬ ПРОМОКОД\n\nВведите код:",
        "dev_give_premium": "💎 ВЫДАТЬ ПРЕМИУМ\n\nВведите ID пользователя:",
        "dev_give_requests": "📦 ВЫДАТЬ ЗАПРОСЫ\n\nВведите ID пользователя:",
        "premium_given": "✅ Премиум выдан!\n\n👤 @{username}\n📅 {days} дней\n🕐 До: {until}",
        "requests_given": "✅ Запросы выданы!\n\n👤 @{username}\n📊 +{count} запросов",
        "promo_created": "✅ Промокод создан!\n\n📌 Код: <code>{code}</code>\n📅 {days} дней\n👥 Лимит: {limit}",
        "promo_deleted": "✅ Промокод {code} удален!",
        "promo_not_found": "❌ Промокод {code} не найден!",
        "choose_language": "🌍 <b>Выберите язык / Choose language / Виберіть мову / Выберыце мову / 选择语言 / Wähle Sprache:</b>",
        "searching": "🔍 Поиск свободного ника...\n\n📏 Длина: {length} символов\n🔢 С цифрами: {digits}\n⏳ 0/{max}\n\n<i>Начинаю поиск...</i>",
        "search_progress": "🔍 Поиск свободного ника...\n\n📏 Длина: {length} символов\n🔢 С цифрами: {digits}\n⏳ <b>{attempt}/{max}</b>\n\n🔎 Проверяю: <code>@{nick}</code>\n📋 Проверено: {checked} ников\n\n<i>Ищу свободный ник...</i>",
        "search_found": "🎉 НАЙДЕН СВОБОДНЫЙ НИК!\n\n👤 <code>@{nick}</code>\n🎯 Найден на попытке {attempt}/{max}\n📋 Проверено: {checked} ников"
    },
    "en": {
        "name": "🇬🇧 English",
        "welcome": "👻 <b>Welcome to GHOST - Nick Finder!</b>\n\nHello, {name}! 👋\n\n🎯 <b>What can you do?</b>\n• Find free Telegram nicknames\n• Double check: API + Web\n• Get rating and price\n\n📌 <b>Available modes:</b>\n• 6 letters — free\n• 5 letters — only PREMIUM\n\n📌 <b>For beginners:</b>\n• {requests} free searches per day\n• 30 sec cooldown after each search\n• Requests reset every 2 days (+3)\n• <b>Request not wasted if not found!</b>\n\n💎 <b>Premium:</b>\n• Unlimited searches\n• Access to 5-letter nicks\n\n<i>Developer: @gawuzu</i>",
        "search": "🔍 SEARCH USERNAME",
        "search_desc": "✅ Double check:\n  • Telegram API — not occupied\n  • Web-page — not on Fragment auction\n\n📌 Available modes:\n  • 6 letters — free\n  • 5 letters — only PREMIUM\n\n📊 Remaining attempts: {requests}\n🎯 Search for 15 attempts\n💡 Request not wasted if not found!\n\n<b>Choose mode:</b>",
        "premium": "💎 PREMIUM SUBSCRIPTION\n\n<b>FEATURES:</b>\n• Unlimited search\n• Access to 5-letter nicks\n\n<b>PRICES:</b>\n1 day — 65⭐\n3 days — 150⭐\n10 days — 400⭐\n30 days — 800⭐",
        "profile": "👤 PROFILE\n\n📌 ID: {id}\n📌 Name: {name}\n📌 Username: @{username}\n\n📊 STATISTICS:\n• Found: {found}\n• Requests: {requests}/{max}\n\n📋 Last found:\n{nicks}\n\n💎 Premium: {premium}",
        "referral": "👥 REFERRALS\n\n🔗 Link:\n<code>{link}</code>\n\n<b>Rewards:</b>\n• 7 → 1 day\n• 14 → 3 days\n• 25 → 10 days\n• 50 → 25 days",
        "info": "ℹ️ GHOST - Nick Finder\n\n• Finds free 5-6 letter nicks\n• Double check: API + Web\n• 15 attempts with progress\n• Rating and price in $\n• Request not wasted if not found\n• Payment: Telegram Stars",
        "help": "🆘 SUPPORT\n\nDeveloper: @gawuzu",
        "found": "✅ Free nickname found!\n\n👤 Username: @{nick}\n📏 Length: {length} letters\n{with_digits}⭐ Rating: {rating}/10\n💰 Value: ${price}\n🎯 Found in: {attempts} attempts",
        "not_found": "❌ Free nickname not found\n\n⏳ Attempts: 15/15\n📋 Checked: {checked} nicks\n\n💡 Request was not wasted!",
        "copy": "📋 <code>@{nick}</code>\n\n✅ Nickname copied! Use it in Telegram.",
        "premium_active": "\n✅ Active: {days}d {hours}h",
        "premium_inactive": "\n❌ Not active",
        "dev_panel": "👑 DEVELOPER PANEL\n\nChoose section:",
        "dev_stats": "📊 BOT STATISTICS\n\n👥 Users: {users}\n🔍 Total searches: {searches}\n💎 Premium: {premium}",
        "dev_users": "👥 USERS LIST\n\nTotal: {total}\n\n{users}",
        "dev_broadcast": "📢 BROADCAST\n\nSend message for broadcast:",
        "dev_promos": "🎁 PROMO CODES MANAGEMENT",
        "dev_promo_create": "🎁 CREATE PROMO CODE\n\nEnter code (letters and numbers):",
        "dev_promo_list": "📋 PROMO CODES LIST",
        "dev_promo_delete": "❌ DELETE PROMO CODE\n\nEnter code:",
        "dev_give_premium": "💎 GIVE PREMIUM\n\nEnter user ID:",
        "dev_give_requests": "📦 GIVE REQUESTS\n\nEnter user ID:",
        "premium_given": "✅ Premium given!\n\n👤 @{username}\n📅 {days} days\n🕐 Until: {until}",
        "requests_given": "✅ Requests given!\n\n👤 @{username}\n📊 +{count} requests",
        "promo_created": "✅ Promo code created!\n\n📌 Code: <code>{code}</code>\n📅 {days} days\n👥 Limit: {limit}",
        "promo_deleted": "✅ Promo code {code} deleted!",
        "promo_not_found": "❌ Promo code {code} not found!",
        "choose_language": "🌍 <b>Choose language / Выберите язык / Виберіть мову / Выберыце мову / 选择语言 / Wähle Sprache:</b>",
        "searching": "🔍 Searching for free nickname...\n\n📏 Length: {length} letters\n🔢 With digits: {digits}\n⏳ 0/{max}\n\n<i>Starting search...</i>",
        "search_progress": "🔍 Searching for free nickname...\n\n📏 Length: {length} letters\n🔢 With digits: {digits}\n⏳ <b>{attempt}/{max}</b>\n\n🔎 Checking: <code>@{nick}</code>\n📋 Checked: {checked} nicks\n\n<i>Looking for free nickname...</i>",
        "search_found": "🎉 FREE NICKNAME FOUND!\n\n👤 <code>@{nick}</code>\n🎯 Found on attempt {attempt}/{max}\n📋 Checked: {checked} nicks"
    },
    "ua": {
        "name": "🇺🇦 Українська",
        "welcome": "👻 <b>Ласкаво просимо до GHOST - Пошук Ніків!</b>\n\nПривіт, {name}! 👋\n\n🎯 <b>Що тут можна робити?</b>\n• Знаходити вільні Telegram-ніки\n• Подвійна перевірка: API + Web\n• Отримувати рейтинг та вартість ніка\n\n📌 <b>Доступні режими:</b>\n• 6 букв — безкоштовно\n• 5 букв — тільки PREMIUM\n\n📌 <b>Для новачків:</b>\n• {requests} безкоштовних пошуків на день\n• Після кожного пошуку кд 30 секунд\n• Запити оновлюються кожні 2 дні (+3)\n• <b>Запит не витрачається, якщо нік не знайдено!</b>\n\n💎 <b>Преміум:</b>\n• Безлімітні пошуки\n• Доступ до 5-буквених ніків\n\n<i>Розробник: @gawuzu</i>",
        "search": "🔍 ПОШУК ЮЗЕРНЕЙМА",
        "search_desc": "✅ Подвійна перевірка:\n  • Telegram API — не зайнятий\n  • Web-сторінка — не на аукціоні Fragment\n\n📌 Доступні режими:\n  • 6 букв — безкоштовно\n  • 5 букв — тільки PREMIUM\n\n📊 Залишилось спроб: {requests}\n🎯 Пошук за 15 спроб\n💡 Запит не витрачається, якщо нік не знайдено!\n\n<b>Виберіть режим:</b>",
        "premium": "💎 ПРЕМІУМ ПІДПИСКА\n\n<b>ФУНКЦІЇ:</b>\n• Безлімітний пошук\n• Доступ до 5-буквених ніків\n\n<b>ЦІНИ:</b>\n1 день — 65⭐\n3 дні — 150⭐\n10 днів — 400⭐\n30 днів — 800⭐",
        "profile": "👤 ПРОФІЛЬ\n\n📌 ID: {id}\n📌 Ім'я: {name}\n📌 Юзернейм: @{username}\n\n📊 СТАТИСТИКА:\n• Знайдено: {found}\n• Запитів: {requests}/{max}\n\n📋 Останні знайдені:\n{nicks}\n\n💎 Преміум: {premium}",
        "referral": "👥 РЕФЕРАЛИ\n\n🔗 Посилання:\n<code>{link}</code>\n\n<b>Нагороди:</b>\n• 7 → 1 день\n• 14 → 3 дні\n• 25 → 10 днів\n• 50 → 25 днів",
        "info": "ℹ️ GHOST - Пошук Ніків\n\n• Знаходить вільні ніки 5-6 букв\n• Подвійна перевірка: API + Web\n• 15 спроб з прогресом\n• Рейтинг та ціна в $\n• Запит не витрачається якщо нік не знайдено\n• Оплата: Telegram Stars",
        "help": "🆘 ПІДТРИМКА\n\nРозробник: @gawuzu",
        "found": "✅ Знайдено вільний нік!\n\n👤 Юзернейм: @{nick}\n📏 Довжина: {length} символів\n{with_digits}⭐ Рейтинг: {rating}/10\n💰 Цінність: ${price}\n🎯 Знайдено за: {attempts} спроб",
        "not_found": "❌ Вільний нік не знайдено\n\n⏳ Спроб: 15/15\n📋 Перевірено: {checked} ніків\n\n💡 Запит не був витрачений!",
        "copy": "📋 <code>@{nick}</code>\n\n✅ Нік скопійовано! Використовуйте його в Telegram.",
        "premium_active": "\n✅ Активний: {days}д {hours}год",
        "premium_inactive": "\n❌ Не активний",
        "dev_panel": "👑 ПАНЕЛЬ РОЗРОБНИКА\n\nВиберіть розділ:",
        "dev_stats": "📊 СТАТИСТИКА БОТА\n\n👥 Користувачі: {users}\n🔍 Всього пошуків: {searches}\n💎 Преміум: {premium}",
        "dev_users": "👥 СПИСОК КОРИСТУВАЧІВ\n\nВсього: {total}\n\n{users}",
        "dev_broadcast": "📢 РОЗСИЛКА\n\nНадішліть повідомлення для розсилки:",
        "dev_promos": "🎁 УПРАВЛІННЯ ПРОМОКОДАМИ",
        "dev_promo_create": "🎁 СТВОРИТИ ПРОМОКОД\n\nВведіть код (букви та цифри):",
        "dev_promo_list": "📋 СПИСОК ПРОМОКОДІВ",
        "dev_promo_delete": "❌ ВИДАЛИТИ ПРОМОКОД\n\nВведіть код:",
        "dev_give_premium": "💎 ВИДАТИ ПРЕМІУМ\n\nВведіть ID користувача:",
        "dev_give_requests": "📦 ВИДАТИ ЗАПИТИ\n\nВведіть ID користувача:",
        "premium_given": "✅ Преміум видано!\n\n👤 @{username}\n📅 {days} днів\n🕐 До: {until}",
        "requests_given": "✅ Запити видано!\n\n👤 @{username}\n📊 +{count} запитів",
        "promo_created": "✅ Промокод створено!\n\n📌 Код: <code>{code}</code>\n📅 {days} днів\n👥 Ліміт: {limit}",
        "promo_deleted": "✅ Промокод {code} видалено!",
        "promo_not_found": "❌ Промокод {code} не знайдено!",
        "choose_language": "🌍 <b>Оберіть мову / Выберите язык / Choose language / Выберыце мову / 选择语言 / Wähle Sprache:</b>",
        "searching": "🔍 Пошук вільного ніка...\n\n📏 Довжина: {length} символів\n🔢 З цифрами: {digits}\n⏳ 0/{max}\n\n<i>Починаю пошук...</i>",
        "search_progress": "🔍 Пошук вільного ніка...\n\n📏 Довжина: {length} символів\n🔢 З цифрами: {digits}\n⏳ <b>{attempt}/{max}</b>\n\n🔎 Перевіряю: <code>@{nick}</code>\n📋 Перевірено: {checked} ніків\n\n<i>Шукаю вільний нік...</i>",
        "search_found": "🎉 ЗНАЙДЕНО ВІЛЬНИЙ НІК!\n\n👤 <code>@{nick}</code>\n🎯 Знайдено на спробі {attempt}/{max}\n📋 Перевірено: {checked} ніків"
    },
    "be": {
        "name": "🇧🇾 Беларуская",
        "welcome": "👻 <b>Сардэчна запрашаем у GHOST - Пошук Нікаў!</b>\n\nПрывітанне, {name}! 👋\n\n🎯 <b>Што тут можна рабіць?</b>\n• Знаходзіць вольныя Telegram-нікі\n• Падвойная праверка: API + Web\n• Атрымліваць рэйтынг і кошт ніка\n\n📌 <b>Даступныя рэжымы:</b>\n• 6 літар — бясплатна\n• 5 літар — толькі PREMIUM\n\n📌 <b>Для пачаткоўцаў:</b>\n• {requests} бясплатных пошукаў у дзень\n• Пасля кожнага пошуку кд 30 секунд\n• Запыты абнаўляюцца кожныя 2 дні (+3)\n• <b>Запыт не выдаткаваецца, калі нік не знойдзены!</b>\n\n💎 <b>Прэміум:</b>\n• Безлімітныя пошукі\n• Доступ да 5-літарных нікаў\n\n<i>Распрацоўшчык: @gawuzu</i>",
        "search": "🔍 ПОШУК ЮЗЕРНЕЙМА",
        "search_desc": "✅ Падвойная праверка:\n  • Telegram API — не заняты\n  • Web-старонка — не на аўкцыёне Fragment\n\n📌 Даступныя рэжымы:\n  • 6 літар — бясплатна\n  • 5 літар — толькі PREMIUM\n\n📊 Засталося спроб: {requests}\n🎯 Пошук за 15 спроб\n💡 Запыт не выдаткаваецца, калі нік не знойдзены!\n\n<b>Абярыце рэжым:</b>",
        "premium": "💎 ПРЭМІУМ ПАДПІСКА\n\n<b>ФУНКЦЫІ:</b>\n• Безлімітны пошук\n• Доступ да 5-літарных нікаў\n\n<b>ЦЭНЫ:</b>\n1 дзень — 65⭐\n3 дні — 150⭐\n10 дзён — 400⭐\n30 дзён — 800⭐",
        "profile": "👤 ПРОФІЛЬ\n\n📌 ID: {id}\n📌 Імя: {name}\n📌 Юзернейм: @{username}\n\n📊 СТАТЫСТЫКА:\n• Знойдзена: {found}\n• Запытаў: {requests}/{max}\n\n📋 Апошнія знойдзеныя:\n{nicks}\n\n💎 Прэміум: {premium}",
        "referral": "👥 РЭФЕРАЛЫ\n\n🔗 Спасылка:\n<code>{link}</code>\n\n<b>Узнагароды:</b>\n• 7 → 1 дзень\n• 14 → 3 дні\n• 25 → 10 дзён\n• 50 → 25 дзён",
        "info": "ℹ️ GHOST - Пошук Нікаў\n\n• Знаходзіць вольныя нікі 5-6 літар\n• Падвойная праверка: API + Web\n• 15 спроб з прагрэсам\n• Рэйтынг і кошт у $\n• Запыт не выдаткаваецца калі нік не знойдзены\n• Аплата: Telegram Stars",
        "help": "🆘 ПАДТРЫМКА\n\nРаспрацоўшчык: @gawuzu",
        "found": "✅ Знойдзены вольны нік!\n\n👤 Юзернейм: @{nick}\n📏 Даўжыня: {length} сімвалаў\n{with_digits}⭐ Рэйтынг: {rating}/10\n💰 Каштоўнасць: ${price}\n🎯 Знойдзена за: {attempts} спроб",
        "not_found": "❌ Вольны нік не знойдзены\n\n⏳ Спробаў: 15/15\n📋 Праверана: {checked} нікаў\n\n💡 Запыт не быў выдаткаваны!",
        "copy": "📋 <code>@{nick}</code>\n\n✅ Нік скапіяваны! Выкарыстоўвайце яго ў Telegram.",
        "premium_active": "\n✅ Актыўны: {days}д {hours}г",
        "premium_inactive": "\n❌ Не актыўны",
        "dev_panel": "👑 ПАНЭЛЬ РАСПРАЦОЎШЧЫКА\n\nАбярыце раздзел:",
        "dev_stats": "📊 СТАТЫСТЫКА БОТА\n\n👥 Карыстальнікі: {users}\n🔍 Усяго пошукаў: {searches}\n💎 Прэміум: {premium}",
        "dev_users": "👥 СПІС КАРЫСТАЛЬНІКАЎ\n\nУсяго: {total}\n\n{users}",
        "dev_broadcast": "📢 РАССЫЛКА\n\nАдпраўце паведамленне для рассылкі:",
        "dev_promos": "🎁 КІРАВАННЕ ПРОМАКОДАМІ",
        "dev_promo_create": "🎁 СТВАРЫЦЬ ПРОМАКОД\n\nУвядзіце код (літары і лічбы):",
        "dev_promo_list": "📋 СПІС ПРОМАКОДАЎ",
        "dev_promo_delete": "❌ ВЫДАЛІЦЬ ПРОМАКОД\n\nУвядзіце код:",
        "dev_give_premium": "💎 ВЫДАЦЬ ПРЭМІУМ\n\nУвядзіце ID карыстальніка:",
        "dev_give_requests": "📦 ВЫДАЦЬ ЗАПЫТЫ\n\nУвядзіце ID карыстальніка:",
        "premium_given": "✅ Прэміум выдадзены!\n\n👤 @{username}\n📅 {days} дзён\n🕐 Да: {until}",
        "requests_given": "✅ Запыты выдадзены!\n\n👤 @{username}\n📊 +{count} запытаў",
        "promo_created": "✅ Промаход створаны!\n\n📌 Код: <code>{code}</code>\n📅 {days} дзён\n👥 Ліміт: {limit}",
        "promo_deleted": "✅ Промаход {code} выдалены!",
        "promo_not_found": "❌ Промаход {code} не знойдзены!",
        "choose_language": "🌍 <b>Абярыце мову / Выберите язык / Choose language / Виберіть мову / 选择语言 / Wähle Sprache:</b>",
        "searching": "🔍 Пошук вольнага ніка...\n\n📏 Даўжыня: {length} сімвалаў\n🔢 З лічбамі: {digits}\n⏳ 0/{max}\n\n<i>Пачынаю пошук...</i>",
        "search_progress": "🔍 Пошук вольнага ніка...\n\n📏 Даўжыня: {length} сімвалаў\n🔢 З лічбамі: {digits}\n⏳ <b>{attempt}/{max}</b>\n\n🔎 Правяраю: <code>@{nick}</code>\n📋 Праверана: {checked} нікаў\n\n<i>Шукаю вольны нік...</i>",
        "search_found": "🎉 ЗНОЙДЗЕНЫ ВОЛЬНЫ НІК!\n\n👤 <code>@{nick}</code>\n🎯 Знойдзены на спробе {attempt}/{max}\n📋 Праверана: {checked} нікаў"
    },
    "zh": {
        "name": "🇨🇳 中文",
        "welcome": "👻 <b>欢迎来到 GHOST - 昵称查找器！</b>\n\n你好，{name}！👋\n\n🎯 <b>你可以做什么？</b>\n• 查找免费的 Telegram 昵称\n• 双重检查：API + Web\n• 获取评级和价格\n\n📌 <b>可用模式：</b>\n• 6 个字母 — 免费\n• 5 个字母 — 仅限 PREMIUM\n\n📌 <b>初学者：</b>\n• 每天 {requests} 次免费搜索\n• 每次搜索后冷却 30 秒\n• 每 2 天重置请求 (+3)\n• <b>如果未找到，请求不会浪费！</b>\n\n💎 <b>高级版：</b>\n• 无限搜索\n• 访问 5 个字母的昵称\n\n<i>开发者：@gawuzu</i>",
        "search": "🔍 搜索用户名",
        "search_desc": "✅ 双重检查：\n  • Telegram API — 未被占用\n  • 网页 — 不在 Fragment 拍卖中\n\n📌 可用模式：\n  • 6 个字母 — 免费\n  • 5 个字母 — 仅限 PREMIUM\n\n📊 剩余尝试次数：{requests}\n🎯 搜索 15 次\n💡 如果未找到，请求不会浪费！\n\n<b>选择模式：</b>",
        "premium": "💎 高级订阅\n\n<b>功能：</b>\n• 无限搜索\n• 访问 5 个字母的昵称\n\n<b>价格：</b>\n1 天 — 65⭐\n3 天 — 150⭐\n10 天 — 400⭐\n30 天 — 800⭐",
        "profile": "👤 个人资料\n\n📌 ID：{id}\n📌 姓名：{name}\n📌 用户名：@{username}\n\n📊 统计：\n• 找到：{found}\n• 请求：{requests}/{max}\n\n📋 最后找到：\n{nicks}\n\n💎 高级版：{premium}",
        "referral": "👥 推荐\n\n🔗 链接：\n<code>{link}</code>\n\n<b>奖励：</b>\n• 7 → 1 天\n• 14 → 3 天\n• 25 → 10 天\n• 50 → 25 天",
        "info": "ℹ️ GHOST - 昵称查找器\n\n• 查找免费的 5-6 字母昵称\n• 双重检查：API + Web\n• 15 次尝试带进度\n• 评级和价格（美元）\n• 如果未找到，请求不会浪费\n• 支付：Telegram Stars",
        "help": "🆘 支持\n\n开发者：@gawuzu",
        "found": "✅ 找到免费昵称！\n\n👤 用户名：@{nick}\n📏 长度：{length} 个字符\n{with_digits}⭐ 评级：{rating}/10\n💰 价值：${price}\n🎯 找到于：{attempts} 次尝试",
        "not_found": "❌ 未找到免费昵称\n\n⏳ 尝试次数：15/15\n📋 已检查：{checked} 个昵称\n\n💡 请求未被浪费！",
        "copy": "📋 <code>@{nick}</code>\n\n✅ 昵称已复制！在 Telegram 中使用它。",
        "premium_active": "\n✅ 有效：{days}天 {hours}小时",
        "premium_inactive": "\n❌ 无效",
        "dev_panel": "👑 开发者面板\n\n选择部分：",
        "dev_stats": "📊 机器人统计\n\n👥 用户：{users}\n🔍 总搜索次数：{searches}\n💎 高级版：{premium}",
        "dev_users": "👥 用户列表\n\n总计：{total}\n\n{users}",
        "dev_broadcast": "📢 广播\n\n发送消息进行广播：",
        "dev_promos": "🎁 促销代码管理",
        "dev_promo_create": "🎁 创建促销代码\n\n输入代码（字母和数字）：",
        "dev_promo_list": "📋 促销代码列表",
        "dev_promo_delete": "❌ 删除促销代码\n\n输入代码：",
        "dev_give_premium": "💎 给予高级版\n\n输入用户 ID：",
        "dev_give_requests": "📦 给予请求\n\n输入用户 ID：",
        "premium_given": "✅ 已给予高级版！\n\n👤 @{username}\n📅 {days} 天\n🕐 直到：{until}",
        "requests_given": "✅ 已给予请求！\n\n👤 @{username}\n📊 +{count} 请求",
        "promo_created": "✅ 促销代码已创建！\n\n📌 代码：<code>{code}</code>\n📅 {days} 天\n👥 限制：{limit}",
        "promo_deleted": "✅ 促销代码 {code} 已删除！",
        "promo_not_found": "❌ 促销代码 {code} 未找到！",
        "choose_language": "🌍 <b>选择语言 / Choose language / Выберите язык / Виберіть мову / Выберыце мову / 选择语言 / Wähle Sprache:</b>",
        "searching": "🔍 正在搜索免费昵称...\n\n📏 长度：{length} 个字符\n🔢 带数字：{digits}\n⏳ 0/{max}\n\n<i>开始搜索...</i>",
        "search_progress": "🔍 正在搜索免费昵称...\n\n📏 长度：{length} 个字符\n🔢 带数字：{digits}\n⏳ <b>{attempt}/{max}</b>\n\n🔎 检查：<code>@{nick}</code>\n📋 已检查：{checked} 个昵称\n\n<i>寻找免费昵称...</i>",
        "search_found": "🎉 找到免费昵称！\n\n👤 <code>@{nick}</code>\n🎯 找到于尝试 {attempt}/{max}\n📋 已检查：{checked} 个昵称"
    },
    "de": {
        "name": "🇩🇪 Deutsch",
        "welcome": "👻 <b>Willkommen bei GHOST - Nick Finder!</b>\n\nHallo, {name}! 👋\n\n🎯 <b>Was kann man hier machen?</b>\n• Kostenlose Telegram-Nicknames finden\n• Doppelte Prüfung: API + Web\n• Bewertung und Preis erhalten\n\n📌 <b>Verfügbare Modi:</b>\n• 6 Buchstaben — kostenlos\n• 5 Buchstaben — nur PREMIUM\n\n📌 <b>Für Anfänger:</b>\n• {requests} kostenlose Suchanfragen pro Tag\n• 30 Sekunden Abklingzeit nach jeder Suche\n• Anfragen werden alle 2 Tage zurückgesetzt (+3)\n• <b>Anfrage wird nicht verschwendet, wenn nicht gefunden!</b>\n\n💎 <b>Premium:</b>\n• Unbegrenzte Suchanfragen\n• Zugang zu 5-Buchstaben-Nicks\n\n<i>Entwickler: @gawuzu</i>",
        "search": "🔍 BENUTZERNAME SUCHEN",
        "search_desc": "✅ Doppelte Prüfung:\n  • Telegram API — nicht belegt\n  • Webseite — nicht auf Fragment-Auktion\n\n📌 Verfügbare Modi:\n  • 6 Buchstaben — kostenlos\n  • 5 Buchstaben — nur PREMIUM\n\n📊 Verbleibende Versuche: {requests}\n🎯 Suche nach 15 Versuchen\n💡 Anfrage wird nicht verschwendet, wenn nicht gefunden!\n\n<b>Wähle Modus:</b>",
        "premium": "💎 PREMIUM-ABONNEMENT\n\n<b>FUNKTIONEN:</b>\n• Unbegrenzte Suche\n• Zugang zu 5-Buchstaben-Nicks\n\n<b>PREISE:</b>\n1 Tag — 65⭐\n3 Tage — 150⭐\n10 Tage — 400⭐\n30 Tage — 800⭐",
        "profile": "👤 PROFIL\n\n📌 ID: {id}\n📌 Name: {name}\n📌 Benutzername: @{username}\n\n📊 STATISTIK:\n• Gefunden: {found}\n• Anfragen: {requests}/{max}\n\n📋 Letzte Funde:\n{nicks}\n\n💎 Premium: {premium}",
        "referral": "👥 EMPFEHLUNGEN\n\n🔗 Link:\n<code>{link}</code>\n\n<b>Belohnungen:</b>\n• 7 → 1 Tag\n• 14 → 3 Tage\n• 25 → 10 Tage\n• 50 → 25 Tage",
        "info": "ℹ️ GHOST - Nick Finder\n\n• Findet kostenlose 5-6 Buchstaben Nicks\n• Doppelte Prüfung: API + Web\n• 15 Versuche mit Fortschritt\n• Bewertung und Preis in $\n• Anfrage wird nicht verschwendet wenn nicht gefunden\n• Zahlung: Telegram Stars",
        "help": "🆘 UNTERSTÜTZUNG\n\nEntwickler: @gawuzu",
        "found": "✅ Kostenloser Nickname gefunden!\n\n👤 Benutzername: @{nick}\n📏 Länge: {length} Zeichen\n{with_digits}⭐ Bewertung: {rating}/10\n💰 Wert: ${price}\n🎯 Gefunden in: {attempts} Versuchen",
        "not_found": "❌ Kein kostenloser Nickname gefunden\n\n⏳ Versuche: 15/15\n📋 Geprüft: {checked} Nicks\n\n💡 Anfrage wurde nicht verschwendet!",
        "copy": "📋 <code>@{nick}</code>\n\n✅ Nickname kopiert! Verwenden Sie ihn in Telegram.",
        "premium_active": "\n✅ Aktiv: {days}T {hours}St",
        "premium_inactive": "\n❌ Nicht aktiv",
        "dev_panel": "👑 ENTWICKLER-PANEL\n\nWähle Bereich:",
        "dev_stats": "📊 BOT-STATISTIK\n\n👥 Benutzer: {users}\n🔍 Suchanfragen: {searches}\n💎 Premium: {premium}",
        "dev_users": "👥 BENUTZERLISTE\n\nInsgesamt: {total}\n\n{users}",
        "dev_broadcast": "📢 RUNDSENDUNG\n\nSende Nachricht für Rundsendung:",
        "dev_promos": "🎁 PROMO-CODE-VERWALTUNG",
        "dev_promo_create": "🎁 PROMO-CODE ERSTELLEN\n\nCode eingeben (Buchstaben und Zahlen):",
        "dev_promo_list": "📋 PROMO-CODE-LISTE",
        "dev_promo_delete": "❌ PROMO-CODE LÖSCHEN\n\nCode eingeben:",
        "dev_give_premium": "💎 PREMIUM GEBEN\n\nBenutzer-ID eingeben:",
        "dev_give_requests": "📦 ANFRAGEN GEBEN\n\nBenutzer-ID eingeben:",
        "premium_given": "✅ Premium gegeben!\n\n👤 @{username}\n📅 {days} Tage\n🕐 Bis: {until}",
        "requests_given": "✅ Anfragen gegeben!\n\n👤 @{username}\n📊 +{count} Anfragen",
        "promo_created": "✅ Promo-Code erstellt!\n\n📌 Code: <code>{code}</code>\n📅 {days} Tage\n👥 Limit: {limit}",
        "promo_deleted": "✅ Promo-Code {code} gelöscht!",
        "promo_not_found": "❌ Promo-Code {code} nicht gefunden!",
        "choose_language": "🌍 <b>Sprache wählen / Выберите язык / Choose language / Виберіть мову / Выберыце мову / 选择语言 / Wähle Sprache:</b>",
        "searching": "🔍 Suche nach kostenlosem Nick...\n\n📏 Länge: {length} Zeichen\n🔢 Mit Ziffern: {digits}\n⏳ 0/{max}\n\n<i>Suche startet...</i>",
        "search_progress": "🔍 Suche nach kostenlosem Nick...\n\n📏 Länge: {length} Zeichen\n🔢 Mit Ziffern: {digits}\n⏳ <b>{attempt}/{max}</b>\n\n🔎 Prüfe: <code>@{nick}</code>\n📋 Geprüft: {checked} Nicks\n\n<i>Suche nach kostenlosem Nick...</i>",
        "search_found": "🎉 KOSTENLOSER NICK GEFUNDEN!\n\n👤 <code>@{nick}</code>\n🎯 Gefunden bei Versuch {attempt}/{max}\n📋 Geprüft: {checked} Nicks"
    }
}

# ═══════════════════════════════════════════════════════════════════
# КЛАСС ДЛЯ РАБОТЫ С ЯЗЫКАМИ
# ═══════════════════════════════════════════════════════════════════

class LanguageManager:
    def __init__(self):
        self.user_lang = {}
    
    def get_lang(self, user_id: int) -> str:
        return self.user_lang.get(user_id, "ru")
    
    def set_lang(self, user_id: int, lang: str):
        self.user_lang[user_id] = lang
    
    def get_text(self, user_id: int, key: str, **kwargs) -> str:
        lang = self.get_lang(user_id)
        text = LANGUAGES.get(lang, LANGUAGES["ru"]).get(key, key)
        try:
            return text.format(**kwargs)
        except:
            return text

lang_manager = LanguageManager()

# ═══════════════════════════════════════════════════════════════════
# СОСТОЯНИЯ FSM
# ═══════════════════════════════════════════════════════════════════

class PromoStates(StatesGroup):
    waiting_for_promo = State()

class DevStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_days = State()
    waiting_for_count = State()
    waiting_for_promo_code = State()
    waiting_for_promo_days = State()
    waiting_for_promo_limit = State()
    waiting_for_broadcast = State()

class LangStates(StatesGroup):
    choosing_language = State()

# ═══════════════════════════════════════════════════════════════════
# БАЗА ДАННЫХ (SQLite)
# ═══════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
        self.backup_db()
        logger.info("✅ База данных SQLite подключена")
    
    def _connect(self):
        try:
            self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.cursor.execute('PRAGMA journal_mode=WAL')
            self.cursor.execute('PRAGMA synchronous=NORMAL')
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            self._restore_from_backup()
    
    def _restore_from_backup(self):
        try:
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
            if backups:
                latest = backups[-1]
                shutil.copy2(os.path.join(BACKUP_DIR, latest), DB_FILE)
                logger.info(f"✅ Восстановлена БД из {latest}")
                self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления: {e}")
    
    def backup_db(self):
        try:
            if os.path.exists(DB_FILE):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"users_{timestamp}.db"
                backup_path = os.path.join(BACKUP_DIR, backup_name)
                shutil.copy2(DB_FILE, backup_path)
                backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
                for old_backup in backups[:-5]:
                    os.remove(os.path.join(BACKUP_DIR, old_backup))
                logger.info(f"✅ Создан бекап: {backup_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка бекапа: {e}")
    
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
                is_developer INTEGER DEFAULT 0,
                language TEXT DEFAULT 'ru'
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
                "is_developer": bool(row[13]) if len(row) > 13 else False,
                "language": row[14] if len(row) > 14 else "ru"
            }
        else:
            current_time = int(time.time())
            is_dev = 1 if str(user_id) == str(ADMIN_ID) else 0
            self.cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, registered_at,
                    free_requests, free_requests_reset, free_requests_last_update,
                    premium_until, last_search, total_searches,
                    ban_status, ban_reason, referral_earnings, is_developer, language
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, "", "", current_time,
                MAX_FREE_REQUESTS, current_time + 86400, current_time,
                0, 0, 0, 0, "", 0, is_dev, "ru"
            ))
            self.conn.commit()
            self.backup_db()
            return self.get_user(user_id)
    
    def update_user_field(self, user_id: int, field: str, value):
        self.cursor.execute(f'UPDATE users SET {field} = ? WHERE user_id = ?', (value, user_id))
        self.conn.commit()
        self.backup_db()
    
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
        self.conn.commit()
        self.backup_db()
        logger.info(f"✅ Премиум сохранён: {user_id} -> {days} дней")
        return new_until
    
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
        self.backup_db()
    
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
    
    def get_all_users(self) -> List[int]:
        self.cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in self.cursor.fetchall()]
    
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
    
    def get_language(self, user_id: int) -> str:
        user = self.get_user(user_id)
        return user.get("language", "ru")
    
    def set_language(self, user_id: int, lang: str):
        self.update_user_field(user_id, "language", lang)
        lang_manager.set_lang(user_id, lang)
    
    def create_promo(self, code: str, days: int, max_uses: int, created_by: int) -> bool:
        try:
            self.cursor.execute('''
                INSERT INTO promo_codes (code, days, max_uses, created_at, expires_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (code.upper(), days, max_uses, int(time.time()), int(time.time()) + 86400 * 30, created_by))
            self.conn.commit()
            self.backup_db()
            return True
        except:
            return False
    
    def delete_promo(self, code: str) -> bool:
        try:
            self.cursor.execute('DELETE FROM promo_codes WHERE code = ?', (code.upper(),))
            self.conn.commit()
            self.backup_db()
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
        self.backup_db()
        return True, f"✅ Премиум на {days} дней активирован!", days

db = Database()

# ═══════════════════════════════════════════════════════════════════
# ГЕНЕРАТОР КРАСИВЫХ НИКОВ
# ═══════════════════════════════════════════════════════════════════

def generate_cool_username(length: int = None) -> str:
    """Генерирует красивые читаемые ники"""
    if length is None:
        length = random.choice([5, 6])
    
    vowels = "aeiouy"
    consonants = "bcdfghjklmnpqrstvwxz"
    
    # Стили генерации
    style = random.choice(['classic', 'with_underscore', 'short_prefix'])
    
    if style == 'classic':
        username = ""
        start_vowel = random.choice([True, False])
        for i in range(length):
            if (i % 2 == 0 and start_vowel) or (i % 2 != 0 and not start_vowel):
                username += random.choice(vowels)
            else:
                username += random.choice(consonants)
        return username
    elif style == 'with_underscore':
        part1 = "".join(random.choice(consonants if i%2==0 else vowels) for i in range(2))
        part2 = "".join(random.choice(vowels if i%2==0 else consonants) for i in range(2))
        return f"{part1}_{part2}"
    else:
        prefix = random.choice(['x', 'z', 'v', 'm', 'q', 'n', 'b'])
        body_len = length - 2
        body = "".join(random.choice(consonants if i%2==0 else vowels) for i in range(body_len))
        return f"{prefix}_{body}"

# ═══════════════════════════════════════════════════════════════════
# ГЕНЕРАТОР НИКОВ + ПОИСК (С ВЕБ-ПРОВЕРКОЙ)
# ═══════════════════════════════════════════════════════════════════

class NickGenerator:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.checked_cache = set()
        self.session = None
    
    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def check_available(self, nick: str) -> bool:
        """
        ДВОЙНАЯ ПРОВЕРКА:
        1. Через Telegram API (get_chat)
        2. Через веб-страницу t.me (проверка Fragment)
        """
        try:
            await self.bot.get_chat(f"@{nick}")
            logger.info(f"❌ @{nick} - ЗАНЯТ (API)")
            return False
        except TelegramBadRequest as e:
            if "chat not found" in str(e).lower():
                try:
                    session = await self.get_session()
                    url = f"https://t.me/{nick}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            html_text = await response.text()
                            if 'tgme_page_extra' in html_text or 'tgme_page_title' in html_text:
                                logger.info(f"❌ @{nick} - ЗАНЯТ (веб-страница)")
                                return False
                            if "fragment.com" in html_text.lower():
                                logger.info(f"❌ @{nick} - НА АУКЦИОНЕ")
                                return False
                            logger.info(f"✅ @{nick} - СВОБОДЕН!")
                            return True
                except Exception as e:
                    logger.info(f"⚠️ Веб-ошибка: {e}")
                    return True
            return False
        except Exception as e:
            logger.info(f"⚠️ @{nick} - Ошибка: {e}")
            return False
    
    async def search_free(self, length: int, with_digits: bool = False, 
                          message=None, lang="ru") -> Tuple[Optional[str], int, List[str]]:
        """Ищет свободный ник"""
        MAX_ATTEMPTS = 15
        attempts = 0
        checked = []
        found = None
        found_attempt = 0
        
        lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
        
        if message:
            await message.edit_text(
                lang_text["searching"].format(
                    length=length,
                    digits="Да" if with_digits else "Нет",
                    max=MAX_ATTEMPTS
                ),
                parse_mode="HTML"
            )
        
        while attempts < MAX_ATTEMPTS:
            attempts += 1
            
            if with_digits:
                nick = generate_cool_username(length) + str(random.randint(0, 9))
                if len(nick) > length:
                    nick = nick[:length]
            else:
                nick = generate_cool_username(length)
            
            if nick in self.checked_cache:
                continue
            
            self.checked_cache.add(nick)
            checked.append(nick)
            
            if message:
                await message.edit_text(
                    lang_text["search_progress"].format(
                        length=length,
                        digits="Да" if with_digits else "Нет",
                        attempt=attempts,
                        max=MAX_ATTEMPTS,
                        nick=nick,
                        checked=len(checked)
                    ),
                    parse_mode="HTML"
                )
            
            logger.info(f"🔄 Попытка {attempts}/{MAX_ATTEMPTS}: @{nick}")
            
            is_available = await self.check_available(nick)
            
            if is_available:
                found = nick
                found_attempt = attempts
                if message:
                    await message.edit_text(
                        lang_text["search_found"].format(
                            nick=nick,
                            attempt=attempts,
                            max=MAX_ATTEMPTS,
                            checked=len(checked)
                        ),
                        parse_mode="HTML"
                    )
                break
            
            await asyncio.sleep(1.2)
        
        if not found and message:
            await message.edit_text(
                lang_text["not_found"].format(
                    checked=len(checked)
                ),
                parse_mode="HTML"
            )
        
        return found, found_attempt, checked
    
    def calculate_rating(self, nick: str) -> int:
        """Рейтинг ника (1-10)"""
        rating = 5
        
        if len(nick) == 5:
            rating += 1
        elif len(nick) == 6:
            rating += 0.5
        
        unique_ratio = len(set(nick)) / len(nick)
        if unique_ratio > 0.7:
            rating += 1
        elif unique_ratio > 0.5:
            rating += 0.5
        
        vowels = sum(1 for c in nick if c in 'aeiouy')
        if 0.2 < vowels / len(nick) < 0.8:
            rating += 1
        
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
    
    def generate_card(self, nick: str, rating: int, price_usd: int, attempts: int) -> BytesIO:
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
        draw.text((width // 2, 180), f"@{nick}", font=self.fonts["large"], fill=(0,255,200), anchor="mm")
        
        stars = "⭐" * rating + "☆" * (10 - rating)
        draw.text((width // 2, 270), f"Рейтинг: {rating}/10", font=self.fonts["medium"], fill=(255,215,0), anchor="mm")
        draw.text((width // 2, 305), stars, font=self.fonts["small"], fill=(255,215,0), anchor="mm")
        draw.text((width // 2, 340), f"💰 Ценность: ${price_usd}", font=self.fonts["medium"], fill=(0,255,100), anchor="mm")
        draw.text((width // 2, 385), f"🎯 Найден за {attempts} попыток", font=self.fonts["small"], fill=(150,150,150), anchor="mm")
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
    def language_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
            ],
            [
                InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua"),
                InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_be")
            ],
            [
                InlineKeyboardButton(text="🇨🇳 中文", callback_data="lang_zh"),
                InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang_de")
            ]
        ])
    
    @staticmethod
    def main_menu(is_developer: bool = False) -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
            [InlineKeyboardButton(text="💎 Премиум", callback_data="menu_premium")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile")],
            [InlineKeyboardButton(text="👥 Рефералы", callback_data="menu_referrals")],
            [InlineKeyboardButton(text="🌍 Язык", callback_data="menu_language")],
            [InlineKeyboardButton(text="ℹ️ Информация", callback_data="menu_info")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu_help")]
        ]
        if is_developer:
            buttons.append([InlineKeyboardButton(text="👑 Панель разработчика", callback_data="menu_dev")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def dev_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="dev_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="dev_users")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="dev_broadcast")],
            [InlineKeyboardButton(text="🎁 Промокоды", callback_data="dev_promos")],
            [InlineKeyboardButton(text="💎 Выдать премиум", callback_data="dev_give_premium")],
            [InlineKeyboardButton(text="📦 Выдать запросы", callback_data="dev_give_requests")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
    
    @staticmethod
    def dev_promos_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать", callback_data="dev_promo_create")],
            [InlineKeyboardButton(text="📋 Список", callback_data="dev_promo_list")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data="dev_promo_delete")],
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
            [InlineKeyboardButton(text="🔗 Получить ссылку", callback_data="referral_link")],
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
    
    # Проверяем язык пользователя
    lang = db.get_language(user_id)
    lang_manager.set_lang(user_id, lang)
    
    is_dev = db.is_developer(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    text = lang_text["welcome"].format(
        name=first_name,
        requests=db.get_free_requests(user_id)
    )
    
    if is_dev:
        text += "\n\n👑 <b>Вы вошли как разработчик!</b>"
    
    await message.answer(text, reply_markup=kb.main_menu(is_dev), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════════
# ВЫБОР ЯЗЫКА
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_language")
async def menu_language(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.message.edit_text(
        LANGUAGES["ru"]["choose_language"],
        reply_markup=kb.language_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split("_")[1]
    
    db.set_language(user_id, lang)
    lang_manager.set_lang(user_id, lang)
    
    is_dev = db.is_developer(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    text = lang_text["welcome"].format(
        name=db.get_user(user_id).get("first_name", "User"),
        requests=db.get_free_requests(user_id)
    )
    
    if is_dev:
        text += "\n\n👑 <b>Вы вошли как разработчик!</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.main_menu(is_dev),
        parse_mode="HTML"
    )
    await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang]['name']}")

# ═══════════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_dev = db.is_developer(user_id)
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
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
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_panel"],
        reply_markup=kb.dev_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_stats")
async def dev_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    total_users = db.get_total_users()
    total_searches = db.get_total_searches()
    premium_count = db.get_premium_count()
    
    await callback.message.edit_text(
        lang_text["dev_stats"].format(
            users=total_users,
            searches=total_searches,
            premium=premium_count
        ),
        reply_markup=kb.dev_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_users")
async def dev_users(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_all_users()
    text = ""
    for i, uid in enumerate(users[:20], 1):
        user = db.get_user(uid)
        username = user.get("username", f"user{uid}")
        is_prem = "💎" if db.is_premium(uid) else ""
        is_dev = "👑" if db.is_developer(uid) else ""
        text += f"{i}. @{username} {is_prem} {is_dev}\n"
    
    if len(users) > 20:
        text += f"\n... и еще {len(users) - 20}"
    
    await callback.message.edit_text(
        lang_text["dev_users"].format(
            total=len(users),
            users=text
        ),
        reply_markup=kb.dev_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_broadcast")
async def dev_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_broadcast"],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_dev")]
        ])
    )
    await state.set_state(DevStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(DevStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    users = db.get_all_users()
    sent = 0
    failed = 0
    
    status_msg = await message.answer(f"📢 Рассылка {len(users)} пользователям...")
    
    for uid in users:
        try:
            if message.text:
                await bot.send_message(uid, message.text, parse_mode="HTML")
            elif message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption, parse_mode="HTML")
            else:
                await bot.send_message(uid, "📢 Рассылка от разработчика", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n📤 Отправлено: {sent}\n❌ Не доставлено: {failed}",
        parse_mode="HTML"
    )
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ПРОМОКОДЫ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "dev_promos")
async def dev_promos_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_promos"],
        reply_markup=kb.dev_promos_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_promo_create")
async def dev_promo_create(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_promo_create"],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="dev_promos")]
        ])
    )
    await state.set_state(DevStates.waiting_for_promo_code)
    await callback.answer()

@dp.message(DevStates.waiting_for_promo_code)
async def dev_promo_code_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    data = await state.get_data()
    delete_mode = data.get("delete_mode", False)
    
    if delete_mode:
        code = message.text.strip().upper()
        if db.delete_promo(code):
            await message.answer(
                lang_text["promo_deleted"].format(code=code),
                reply_markup=kb.dev_promos_menu(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                lang_text["promo_not_found"].format(code=code),
                reply_markup=kb.dev_promos_menu(),
                parse_mode="HTML"
            )
        await state.clear()
        return
    
    code = message.text.strip().upper()
    if not re.match(r'^[A-Z0-9]+$', code):
        await message.answer("❌ Только буквы и цифры:")
        return
    
    await state.update_data(promo_code=code)
    await message.answer("📅 Количество дней (1-365):")
    await state.set_state(DevStates.waiting_for_promo_days)

@dp.message(DevStates.waiting_for_promo_days)
async def dev_promo_days_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
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
    await message.answer("👥 Лимит использований (1-1000):")
    await state.set_state(DevStates.waiting_for_promo_limit)

@dp.message(DevStates.waiting_for_promo_limit)
async def dev_promo_limit_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
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
            lang_text["promo_created"].format(
                code=code,
                days=days,
                limit=limit
            ),
            parse_mode="HTML",
            reply_markup=kb.dev_promos_menu()
        )
    else:
        await message.answer(
            "❌ Ошибка! Код уже существует.",
            reply_markup=kb.dev_promos_menu()
        )
    
    await state.clear()

@dp.callback_query(F.data == "dev_promo_list")
async def dev_promo_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    promos = db.get_all_promos()
    
    if not promos:
        await callback.message.edit_text(
            "📋 Промокодов нет",
            reply_markup=kb.dev_promos_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = "📋 Список промокодов\n\n"
    for promo in promos[:20]:
        status = "✅" if promo["expires_at"] > int(time.time()) else "❌"
        text += f"{status} <code>{promo['code']}</code>\n"
        text += f"   📅 {promo['days']} дней | Исп: {promo['uses']}/{promo['max_uses']}\n"
        text += f"   🕐 До: {datetime.fromtimestamp(promo['expires_at']).strftime('%d.%m.%Y')}\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.dev_promos_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_promo_delete")
async def dev_promo_delete(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_promo_delete"],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="dev_promos")]
        ])
    )
    await state.set_state(DevStates.waiting_for_promo_code)
    await state.update_data(delete_mode=True)
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# ВЫДАТЬ ПРЕМИУМ/ЗАПРОСЫ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "dev_give_premium")
async def dev_give_premium(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_give_premium"],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_dev")]
        ])
    )
    await state.set_state(DevStates.waiting_for_user_id)
    await state.update_data(action="premium")
    await callback.answer()

@dp.callback_query(F.data == "dev_give_requests")
async def dev_give_requests(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if not db.is_developer(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        lang_text["dev_give_requests"],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_dev")]
        ])
    )
    await state.set_state(DevStates.waiting_for_user_id)
    await state.update_data(action="requests")
    await callback.answer()

@dp.message(DevStates.waiting_for_user_id)
async def dev_user_id_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
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
    data = await state.get_data()
    
    if data.get("action") == "premium":
        await message.answer("📅 Количество дней (1-365):")
        await state.set_state(DevStates.waiting_for_days)
    else:
        await message.answer("📊 Количество запросов (1-100):")
        await state.set_state(DevStates.waiting_for_count)

@dp.message(DevStates.waiting_for_days)
async def dev_premium_days_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
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
    
    new_until = db.add_premium(target_id, days)
    target_user = db.get_user(target_id)
    username = target_user.get("username", f"user{target_id}")
    
    await message.answer(
        lang_text["premium_given"].format(
            username=username,
            days=days,
            until=datetime.fromtimestamp(new_until).strftime('%d.%m.%Y %H:%M')
        ),
        parse_mode="HTML",
        reply_markup=kb.dev_menu()
    )
    
    try:
        await bot.send_message(
            target_id,
            f"🎉 <b>Вам выдан премиум!</b>\n\n📅 {days} дней\n💎 Доступны все функции!",
            parse_mode="HTML"
        )
    except:
        pass
    
    await state.clear()

@dp.message(DevStates.waiting_for_count)
async def dev_requests_count_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
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
        lang_text["requests_given"].format(
            username=username,
            count=count
        ),
        parse_mode="HTML",
        reply_markup=kb.dev_menu()
    )
    
    try:
        await bot.send_message(
            target_id,
            f"🎉 Вам выданы запросы!\n📊 +{count}",
            parse_mode="HTML"
        )
    except:
        pass
    
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# ПОИСК
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_search")
async def menu_search(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    banned, reason = db.is_banned(user_id)
    if banned:
        await callback.answer(f"🚫 {reason}", show_alert=True)
        return
    
    is_premium = db.is_premium(user_id)
    free_requests = db.get_free_requests(user_id)
    
    await callback.message.edit_text(
        lang_text["search_desc"].format(
            requests=free_requests if not is_premium else '♾️'
        ),
        reply_markup=kb.search_menu(is_premium),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("search_"))
async def start_search(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    banned, reason = db.is_banned(user_id)
    if banned:
        await callback.answer(f"🚫 {reason}", show_alert=True)
        return
    
    parts = callback.data.split("_")
    length = int(parts[1])
    with_digits = parts[2] == "true"
    
    if length == 5:
        is_premium = db.is_premium(user_id)
        if not is_premium:
            await callback.answer(
                "🔒 5-буквенные ники только с премиум! 💎",
                show_alert=True
            )
            return
    
    can_search, remaining = db.check_cooldown(user_id)
    if not can_search:
        await callback.answer(f"⏳ Подождите {remaining} секунд!", show_alert=True)
        return
    
    is_premium = db.is_premium(user_id)
    free_requests = db.get_free_requests(user_id)
    
    if not is_premium and free_requests <= 0:
        await callback.answer(
            "❌ Закончились бесплатные запросы!\nКупите премиум 💎",
            show_alert=True
        )
        return
    
    db.update_last_search(user_id)
    
    search_msg = await callback.message.edit_text(
        lang_text["searching"].format(
            length=length,
            digits="Да" if with_digits else "Нет",
            max=MAX_SEARCH_ATTEMPTS
        ),
        parse_mode="HTML"
    )
    
    generator = NickGenerator(bot)
    nick, attempts, checked = await generator.search_free(
        length, with_digits, message=search_msg, lang=lang
    )
    
    if nick:
        if not is_premium:
            db.use_free_request(user_id)
        db.increment_searches(user_id)
        db.add_found_username(user_id, nick)
        
        rating = generator.calculate_rating(nick)
        price_usd = random.randint(7, 11)
        
        img_buffer = image_gen.generate_card(nick, rating, price_usd, attempts)
        
        await callback.message.answer_photo(
            photo=BufferedInputFile(img_buffer.getvalue(), filename="nick.png"),
            caption=lang_text["found"].format(
                nick=nick,
                length=length,
                with_digits="🔢 С цифрами\n" if with_digits else "🔤 Только буквы\n",
                rating=rating,
                price=price_usd,
                attempts=attempts
            ),
            reply_markup=kb.result_menu(nick),
            parse_mode="HTML"
        )
    else:
        await search_msg.edit_text(
            lang_text["not_found"].format(
                checked=len(checked)
            ),
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
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    nick = callback.data.split("_")[1]
    
    await callback.answer(f"✅ @{nick} скопирован!", show_alert=True)
    await callback.message.answer(
        lang_text["copy"].format(nick=nick),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════════════════
# ПРЕМИУМ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    is_premium = db.is_premium(user_id)
    
    text = lang_text["premium"]
    
    if is_premium:
        remaining = db.get_premium_remaining(user_id)
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        text += lang_text["premium_active"].format(days=days, hours=hours)
    else:
        text += lang_text["premium_inactive"]
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.premium_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("premium_"))
async def buy_premium(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    if callback.data == "premium_promo":
        await callback.message.edit_text(
            "🎁 Введите промокод:",
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
    
    title = f"Премиум GHOST — {days} дней"
    description = f"Безлимитный поиск на {days} дней!"
    payload = f"premium_{days}_{user_id}_{int(time.time())}"
    prices = [LabeledPrice(label=f"{days} дней", amount=price)]
    
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="premium"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("❌ Ошибка платежа", show_alert=True)

@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message):
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    payload = payment_info.invoice_payload
    parts = payload.split("_")
    
    if len(parts) >= 2 and parts[0] == "premium":
        days = int(parts[1])
        new_until = db.add_premium(user_id, days)
        
        await message.answer(
            f"✅ <b>Премиум активирован!</b>\n\n"
            f"📦 {days} дней\n"
            f"💰 {payment_info.total_amount} ⭐\n"
            f"💎 Безлимитные поиски!\n"
            f"🕐 До: {datetime.fromtimestamp(new_until).strftime('%d.%m.%Y %H:%M')}",
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
            f"✅ {msg}\n\n🎉 Премиум на {days} дней!",
            parse_mode="HTML",
            reply_markup=kb.main_menu(db.is_developer(user_id))
        )
    else:
        await message.answer(
            f"❌ {msg}",
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
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    user = db.get_user(user_id)
    is_premium = db.is_premium(user_id)
    found = db.get_found_usernames(user_id, 5)
    is_dev = db.is_developer(user_id)
    
    nicks_text = ""
    if found:
        for item in found[:5]:
            dt = datetime.fromtimestamp(item["found_at"]).strftime("%d.%m %H:%M")
            nicks_text += f"  • @{item['username']} — {dt}\n"
    else:
        nicks_text += "  • Пока нет\n"
    
    premium_status = "✅" if is_premium else "❌"
    
    await callback.message.edit_text(
        lang_text["profile"].format(
            id=user_id,
            name=user.get('first_name', 'Не указано'),
            username=user.get('username', 'Не указан'),
            found=user.get('total_searches', 0),
            requests=db.get_free_requests(user_id),
            max=MAX_FREE_REQUESTS,
            nicks=nicks_text,
            premium=premium_status
        ),
        reply_markup=kb.profile_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "profile_found")
async def profile_found(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    found = db.get_found_usernames(user_id, 20)
    
    if not found:
        await callback.message.edit_text(
            "📊 Ников пока нет",
            reply_markup=kb.profile_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = "📊 <b>Найденные ники</b>\n\n"
    for i, item in enumerate(reversed(found[:20]), 1):
        dt = datetime.fromtimestamp(item["found_at"]).strftime("%d.%m %H:%M")
        text += f"{i}. @{item['username']} — {dt}\n"
    
    if len(found) > 20:
        text += f"\n... и еще {len(found) - 20}"
    
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
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    code = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
    link = f"https://t.me/GhostSearchNames_bot?start=ref_{code}"
    
    await callback.message.edit_text(
        lang_text["referral"].format(link=link),
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
        f"🔗 Ссылка:\n\n<code>{link}</code>",
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# ИНФОРМАЦИЯ
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    await callback.message.edit_text(
        lang_text["info"],
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
    user_id = callback.from_user.id
    lang = db.get_language(user_id)
    lang_text = LANGUAGES.get(lang, LANGUAGES["ru"])
    
    await callback.message.edit_text(
        lang_text["help"],
        reply_markup=kb.help_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "help_contact")
async def help_contact(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.message.answer(
        f"📝 Написать: @gawuzu\n\nВаш ID: <code>{user_id}</code>",
        parse_mode="HTML"
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════
# ВЕБ-СЕРВЕР + АВТОПИТАНИЕ
# ═══════════════════════════════════════════════════════════════════

async def health_check(request):
    return web.Response(text="OK", status=200)

async def keep_alive():
    while True:
        await asyncio.sleep(240)
        try:
            async with aiohttp.ClientSession() as session:
                await session.get(BOT_URL)
                logger.info("✅ Пинг")
        except:
            pass

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("✅ Веб-сервер запущен")

# ═══════════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════════

async def main():
    await start_web_server()
    asyncio.create_task(keep_alive())
    
    logger.info("🚀 GHOST запущен!")
    logger.info("👤 @gawuzu")
    logger.info("✅ Мультиязычный (6 языков)")
    logger.info("✅ Двойная проверка: API + Web")
    logger.info("✅ База данных сохраняется")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        db.backup_db()

if __name__ == "__main__":
    asyncio.run(main())
