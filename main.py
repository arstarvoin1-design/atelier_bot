import asyncio
import base64
import html
import json
import logging
import os
import random
import time
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp,
    FSInputFile,
    InputMediaPhoto,
)

# ================= НАСТРОЙКИ МАГАЗИНА =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
ADMIN_ID = 5100544808
SHOP_NAME = "ATELIER"

# Ссылка на твой сайт (уже подключена к кнопке «🛍 Открыть магазин»)
SITE_URL = "https://arstarvoin1-design.github.io/atelier-shop/"

# Репозиторий сайта, где хранится общая база товаров catalog.json и фото
GH_OWNER = "arstarvoin1-design"
GH_REPO = "atelier-shop"
GH_BRANCH = "main"
CATALOG_PATH = "catalog.json"

# Канал бренда для проверки подписки за промокод (например "@atelier_brand" или оставь "")
CHANNEL_USERNAME = ""
PROMO_CODE = "ATELIER10"

# Твоя прямая ссылка СБП и имя файла с QR-кодом
PAYMENT_URL = "https://t.tb.ru/c2c-qr-choose-bank?requisiteNumber=+79050090209&bankCode=100000000004"
QR_IMAGE_PATH = "qr.jpg"

# Твои реквизиты для оплаты:
PAYMENT_TEXT = (
    "💳 <b>Оплата через СБП (без комиссии):</b>\n\n"
    "• <b>Банк:</b> Т-Банк / Сбербанк\n"
    "• <b>Телефон (нажмите, чтобы скопировать):</b>\n"
    "<code>+79050090209</code>\n"
    "• <b>Получатель:</b> Арсен Е.\n\n"
    "📲 <i>Нажмите кнопку «Перейти к оплате (СБП)» ниже, отсканируйте QR-код или переведите по номеру телефона. После перевода отправьте скриншот чека в этот чат!</i>"
)

DELIVERY_TEXT = (
    "🚚 <b>Условия доставки и возврата:</b>\n\n"
    "• <b>СДЭК</b> (до пункта выдачи или курьером): 2–5 рабочих дней, от 350 ₽.\n"
    "• <b>Почта России</b>: 4–8 рабочих дней, от 300 ₽.\n"
    "• <b>Бесплатная доставка</b> при заказе от 5 000 ₽.\n\n"
    "🔄 <b>Возврат и обмен:</b> возможен в течение 14 дней с момента получения при сохранении товарного вида и бирок."
)

SIZE_GUIDE_TEXT = (
    "📏 <b>Размерная сетка ATELIER (см):</b>\n\n"
    "• <b>S</b> — грудь 54 / плечи 50 / длина 68 <i>(рост 160–170)</i>\n"
    "• <b>M</b> — грудь 57 / плечи 52 / длина 71 <i>(рост 170–178)</i>\n"
    "• <b>L</b> — грудь 60 / плечи 54 / длина 74 <i>(рост 178–185)</i>\n"
    "• <b>XL</b> — грудь 63 / плечи 56 / длина 76 <i>(рост 185+)</i>\n\n"
    "💡 <i>Вещи имеют свободный оверсайз-крой. Если сомневаетесь между двумя размерами — напишите свой рост и вес менеджеру, мы точно подскажем!</i>"
)

DEFAULT_CATALOG = [
    {
        "id": 1,
        "category": "hoodie",
        "name": "Худи ATELIER Heavyweight Black",
        "price": 5900,
        "fabric": "Футер 460 г/м²",
        "sizes": ["S", "M", "L", "XL"],
        "desc": "100% хлопок диагональ, двойной объемный капюшон и спущенное плечо.",
        "photos": ["https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=800&q=80"]
    },
    {
        "id": 2,
        "category": "tee",
        "name": "Футболка ATELIER Boxy Fit White",
        "price": 2900,
        "fabric": "Хлопок 260 г/м²",
        "sizes": ["S", "M", "L", "XL"],
        "desc": "Плотный джерси, не просвечивает, воротник-резинка держит форму после стирок.",
        "photos": ["https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=800&q=80"]
    },
    {
        "id": 3,
        "category": "sweatshirt",
        "name": "Свитшот ATELIER Graphite",
        "price": 4800,
        "fabric": "Футер 420 г/м²",
        "sizes": ["M", "L", "XL"],
        "desc": "Свободный крой, мягкий браш внутри, минималистичная вышивка в тон.",
        "photos": ["https://images.unsplash.com/photo-1614975059251-992f11792b9f?auto=format&fit=crop&w=800&q=80"]
    }
]
# ======================================================

USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"
LOCAL_CATALOG_FILE = "catalog.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

media_groups_buffer: dict[str, dict] = {}
admin_wait_photo_idx: int | None = None

# Кэш синхронизированного каталога (обновляется каждые 8 сек или мгновенно при изменении)
_catalog_cache: list | None = None
_catalog_cache_ts: float = 0.0
_catalog_sha: str | None = None


def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_price_int(val) -> int:
    if isinstance(val, int):
        return val
    digits = "".join(ch for ch in str(val) if ch.isdigit())
    return int(digits) if digits else 0


def format_price_str(val) -> str:
    num = parse_price_int(val)
    return f"{num:,}".replace(",", " ") + " ₽" if num else str(val)


def detect_category(name: str) -> str:
    low = name.lower()
    if "худи" in low or "hoodie" in low:
        return "hoodie"
    if "футболк" in low or "tee" in low or "майк" in low:
        return "tee"
    if "свитшот" in low or "sweatshirt" in low or "лонгслив" in low:
        return "sweatshirt"
    if "штан" in low or "брюк" in low or "шорт" in low or "джоггер" in low:
        return "pants"
    return "other"


def normalize_items(items: list) -> list:
    result = []
    for i, item in enumerate(items):
        photos = item.get("photos")
        if photos is None:
            old_p = item.get("photo") or item.get("image") or ""
            photos = [old_p] if old_p else []
        result.append({
            "id": item.get("id", i + 1),
            "category": item.get("category") or detect_category(item.get("name", "")),
            "name": item.get("name", "Товар ATELIER"),
            "price": parse_price_int(item.get("price", 0)),
            "fabric": item.get("fabric", "100% хлопок"),
            "sizes": item.get("sizes") or ["S", "M", "L", "XL"],
            "desc": item.get("desc", ""),
            "photos": photos,
        })
    return result


# ================= СИНХРОНИЗАЦИЯ С GITHUB (САЙТ <-> БОТ) =================
async def fetch_synced_catalog(force: bool = False) -> list:
    global _catalog_cache, _catalog_cache_ts, _catalog_sha

    if not force and _catalog_cache is not None and (time.time() - _catalog_cache_ts < 8):
        return _catalog_cache

    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{CATALOG_PATH}?t={int(time.time())}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _catalog_sha = data.get("sha")
                    raw_bytes = base64.b64decode(data["content"])
                    items = normalize_items(json.loads(raw_bytes.decode("utf-8")))
                    _catalog_cache = items
                    _catalog_cache_ts = time.time()
                    save_json(LOCAL_CATALOG_FILE, items)
                    return items
    except Exception as e:
        logging.warning(f"Не удалось прочитать catalog.json с GitHub: {e}")

    local = load_json(LOCAL_CATALOG_FILE, DEFAULT_CATALOG)
    _catalog_cache = normalize_items(local)
    _catalog_cache_ts = time.time()
    return _catalog_cache


async def save_synced_catalog(items: list, commit_msg: str = "Update catalog from Telegram bot") -> bool:
    global _catalog_cache, _catalog_cache_ts, _catalog_sha

    normalized = normalize_items(items)
    save_json(LOCAL_CATALOG_FILE, normalized)
    _catalog_cache = normalized
    _catalog_cache_ts = time.time()

    if not GITHUB_TOKEN:
        return False

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{CATALOG_PATH}"

    try:
        async with aiohttp.ClientSession() as session:
            # Уточняем свежий sha файла перед записью
            async with session.get(f"{url}?t={int(time.time())}", headers=headers, timeout=10) as get_resp:
                if get_resp.status == 200:
                    meta = await get_resp.json()
                    _catalog_sha = meta.get("sha")

            encoded = base64.b64encode(
                json.dumps(normalized, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("utf-8")

            payload = {
                "message": commit_msg,
                "content": encoded,
                "branch": GH_BRANCH,
            }
            if _catalog_sha:
                payload["sha"] = _catalog_sha

            async with session.put(url, headers=headers, json=payload, timeout=15) as put_resp:
                if put_resp.status in (200, 201):
                    res_data = await put_resp.json()
                    _catalog_sha = res_data["content"]["sha"]
                    return True
                else:
                    err_text = await put_resp.text()
                    logging.error(f"GitHub PUT catalog error: {err_text}")
    except Exception as e:
        logging.error(f"Ошибка записи catalog.json в GitHub: {e}")
    return False


async def upload_tg_photo_to_github(file_id: str, index: int = 0) -> str:
    """Скачивает фото из Telegram и загружает его в GitHub, возвращая публичную HTTPS-ссылку для сайта и бота."""
    if not GITHUB_TOKEN:
        return file_id

    try:
        tg_file = await bot.get_file(file_id)
        buf = await bot.download_file(tg_file.file_path)
        img_bytes = buf.read()

        filename = f"images/tg_{int(time.time())}_{index}.jpg"
        url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{filename}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "message": f"Upload {filename} from Telegram bot",
            "content": base64.b64encode(img_bytes).decode("utf-8"),
            "branch": GH_BRANCH,
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload, timeout=20) as resp:
                if resp.status in (200, 201):
                    return f"https://raw.githubusercontent.com/{GH_OWNER}/{GH_REPO}/{GH_BRANCH}/{filename}"
    except Exception as e:
        logging.error(f"Ошибка загрузки фото в GitHub: {e}")

    return file_id
# ========================================================================


def register_user(user_id: int):
    users = load_json(USERS_FILE, [])
    if user_id not in users:
        users.append(user_id)
        save_json(USERS_FILE, users)


def link_order_to_client(order_id: str, client_id: int):
    orders = load_json(ORDERS_FILE, {})
    orders[str(order_id)] = client_id
    save_json(ORDERS_FILE, orders)


def get_order_client(order_id: str):
    orders = load_json(ORDERS_FILE, {})
    return orders.get(str(order_id))


def get_main_keyboard() -> ReplyKeyboardMarkup:
    rows = []
    if SITE_URL.startswith("https://"):
        rows.append([KeyboardButton(text="🛍 Открыть магазин", web_app=WebAppInfo(url=SITE_URL))])
    rows.extend([
        [KeyboardButton(text="👕 Каталог"), KeyboardButton(text="📏 Таблица размеров")],
        [KeyboardButton(text="💳 Оплата СБП"), KeyboardButton(text="🚚 Доставка и возврат")],
        [KeyboardButton(text="🎁 Промокод"), KeyboardButton(text="💬 Написать менеджеру")],
    ])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def get_payment_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    if PAYMENT_URL:
        buttons.append([InlineKeyboardButton(text="💸 Перейти к оплате (СБП)", url=PAYMENT_URL)])
    buttons.append([InlineKeyboardButton(text="📎 Я оплатил (отправить чек)", callback_data="send_receipt")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_catalog_keyboard(index: int, total: int, photo_idx: int = 0, photos_count: int = 0, is_admin: bool = False) -> InlineKeyboardMarkup:
    prev_idx = (index - 1) % total
    next_idx = (index + 1) % total
    buttons = []

    if photos_count > 1:
        next_photo = (photo_idx + 1) % photos_count
        buttons.append([
            InlineKeyboardButton(
                text=f"📸 Фото {photo_idx + 1}/{photos_count} • Следующее фото ➡️",
                callback_data=f"cat_pic:{index}:{next_photo}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🛒 Заказать эту вещь", callback_data=f"cat_buy:{index}")])

    if total > 1:
        buttons.append([
            InlineKeyboardButton(text="⬅️", callback_data=f"cat_nav:{prev_idx}"),
            InlineKeyboardButton(text=f"Товар {index + 1} / {total}", callback_data="noop"),
            InlineKeyboardButton(text="➡️", callback_data=f"cat_nav:{next_idx}"),
        ])

    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="📸 + Фото", callback_data=f"cat_addpic:{index}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"cat_del:{index}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_order_admin_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Реквизиты", callback_data=f"ord:pay:{order_id}"),
            InlineKeyboardButton(text="✅ Оплачено", callback_data=f"ord:paid:{order_id}"),
        ],
        [
            InlineKeyboardButton(text="📦 Отправлено", callback_data=f"ord:ship:{order_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"ord:canc:{order_id}"),
        ]
    ])


async def send_sbp_payment(chat_id: int, prefix_text: str = ""):
    full_text = f"{prefix_text}\n\n{PAYMENT_TEXT}".strip()
    kb = get_payment_keyboard()

    if QR_IMAGE_PATH and os.path.exists(QR_IMAGE_PATH):
        try:
            photo = FSInputFile(QR_IMAGE_PATH)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=full_text,
                parse_mode="HTML",
                reply_markup=kb
            )
            return
        except Exception as e:
            logging.warning(f"Не удалось отправить QR-фото: {e}")

    await bot.send_message(
        chat_id=chat_id,
        text=full_text,
        parse_mode="HTML",
        reply_markup=kb
    )


async def create_product_from_raw(target_message: types.Message, raw_text: str, tg_file_ids: list[str]):
    payload = raw_text.partition(" ")[2].strip()
    if not payload:
        await target_message.answer(
            "➕ <b>Как добавить товар в каталог (появится и в боте, и на сайте):</b>\n\n"
            "Отправь <b>1 фото или целый альбом</b> и в подписи напиши:\n"
            "<code>/add Худи ATELIER Black | 5 900 ₽ | S, M, L, XL | Плотный футер 460 г/м²</code>",
            parse_mode="HTML"
        )
        return

    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await target_message.answer(
            "⚠️ Укажи минимум <b>название</b> и <b>цену</b> через символ <code>|</code>.\n"
            "Пример: <code>/add Футболка White | 2 900 ₽ | S, M, L | Хлопок 260 г/м²</code>",
            parse_mode="HTML"
        )
        return

    name = parts[0]
    price_num = parse_price_int(parts[1])
    sizes = [s.strip() for s in parts[2].split(",") if s.strip()] if len(parts) > 2 and parts[2] else ["S", "M", "L", "XL"]
    desc = parts[3] if len(parts) > 3 else ""

    status_msg = await target_message.answer("⏳ Загружаем фото и синхронизируем с сайтом...")

    uploaded_photos = []
    for idx, fid in enumerate(tg_file_ids):
        uploaded_photos.append(await upload_tg_photo_to_github(fid, idx))

    catalog = await fetch_synced_catalog(force=True)
    catalog.append({
        "id": int(time.time() * 1000),
        "category": detect_category(name),
        "name": name,
        "price": price_num,
        "fabric": "100% хлопок",
        "sizes": sizes,
        "desc": desc,
        "photos": uploaded_photos
    })
    synced = await save_synced_catalog(catalog, f"Add product from bot: {name}")

    sync_note = "синхронизировано с сайтом ✅" if synced else "сохранено локально (добавь GITHUB_TOKEN в Bothost для синхронизации с сайтом)"
    await status_msg.edit_text(
        f"✅ <b>Товар добавлен ({sync_note})!</b>\n\n"
        f"• Название: <b>{html.escape(name)}</b>\n"
        f"• Цена: <b>{format_price_str(price_num)}</b>\n"
        f"• Размеры: <b>{html.escape(', '.join(sizes))}</b>\n"
        f"• Фото: <b>{len(uploaded_photos)} шт.</b>",
        parse_mode="HTML"
    )


async def append_photos_to_product(target_message: types.Message, idx: int, tg_file_ids: list[str]):
    global admin_wait_photo_idx
    catalog = await fetch_synced_catalog(force=True)
    if 0 <= idx < len(catalog):
        status_msg = await target_message.answer("⏳ Загружаем новые фото на сайт и в бот...")
        new_urls = []
        for i, fid in enumerate(tg_file_ids):
            new_urls.append(await upload_tg_photo_to_github(fid, i))

        catalog[idx].setdefault("photos", []).extend(new_urls)
        await save_synced_catalog(catalog, f"Add photos to {catalog[idx]['name']}")
        total_pics = len(catalog[idx]["photos"])
        item_name = html.escape(catalog[idx]["name"])
        admin_wait_photo_idx = None
        await status_msg.edit_text(
            f"✅ Добавлено фото: <b>{len(new_urls)} шт.</b>\n"
            f"Теперь у товара <b>«{item_name}»</b> всего <b>{total_pics} фото</b> (обновилось и на сайте, и в боте)!",
            parse_mode="HTML"
        )
    else:
        admin_wait_photo_idx = None
        await target_message.answer("⚠️ Товар не найден, режим добавления фото сброшен.")


# 1. Команда /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    register_user(user_id)

    if user_id == ADMIN_ID:
        sync_status = "подключена ✅" if GITHUB_TOKEN else "не настроена (добавь GITHUB_TOKEN в Bothost)"
        await message.answer(
            f"👋 Привет, Арсен! Бот магазина <b>{SHOP_NAME}</b> работает в облаке 24/7.\n"
            f"🔄 Синхронизация каталога с сайтом: <b>{sync_status}</b>\n\n"
            "<b>Твои команды владельца:</b>\n"
            "• <code>/add Название | Цена | Размеры | Описание</code> — добавить товар (с фото или альбомом)\n"
            "• <b>👕 Каталог</b> → кнопки <b>📸 + Фото</b> и <b>🗑 Удалить</b>\n"
            "• <code>/stats</code> — статистика клиентов и заказов\n"
            "• <code>/send текст</code> — рассылка всем пользователям\n"
            "• <b>Ответить (Reply)</b> на карточку клиента — написать покупателю от имени магазина.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return

    args = command.args
    if args and args.startswith("order_"):
        order_num = html.escape(args.split("_")[1])
        link_order_to_client(order_num, user_id)
        await message.answer(
            f"👋 Добро пожаловать в <b>{SHOP_NAME}</b>!\n"
            f"Мы привязали ваш <b>Заказ #{order_num}</b> к этому чату.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        await send_sbp_payment(user_id)

        username = f"@{message.from_user.username}" if message.from_user.username else html.escape(message.from_user.full_name)
        await bot.send_message(
            ADMIN_ID,
            f"👀 Клиент {username} (<code>{user_id}</code>) перешел в бот по <b>Заказу #{order_num}</b>.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👋 Добро пожаловать в официальный бот магазина <b>{SHOP_NAME}</b>!\n\n"
            "Откройте витрину магазина кнопкой <b>«🛍 Открыть магазин»</b> или выберите раздел ниже 👇",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )


# 2. Обработка альбомов от админа
async def finalize_media_group(mg_id: str):
    await asyncio.sleep(0.9)
    data = media_groups_buffer.pop(mg_id, None)
    if not data:
        return

    caption = data["caption"].strip()
    photos = data["photos"]
    msg = data["message"]

    if caption.startswith("/add"):
        await create_product_from_raw(msg, caption, photos)
    elif admin_wait_photo_idx is not None:
        await append_photos_to_product(msg, admin_wait_photo_idx, photos)


@dp.message(F.from_user.id == ADMIN_ID, F.media_group_id, F.photo)
async def handle_admin_album(message: types.Message):
    mg_id = message.media_group_id
    if mg_id not in media_groups_buffer:
        media_groups_buffer[mg_id] = {
            "photos": [],
            "caption": "",
            "message": message,
        }
        asyncio.create_task(finalize_media_group(mg_id))

    media_groups_buffer[mg_id]["photos"].append(message.photo[-1].file_id)
    if message.caption:
        media_groups_buffer[mg_id]["caption"] = message.caption
        media_groups_buffer[mg_id]["message"] = message


# 3. Админ-команды
@dp.message(Command("cancel"), F.from_user.id == ADMIN_ID)
async def cmd_cancel_admin(message: types.Message):
    global admin_wait_photo_idx
    admin_wait_photo_idx = None
    await message.answer("👌 Режим ожидания фото отменен.")


@dp.message(Command("add"), F.from_user.id == ADMIN_ID)
async def cmd_add_product(message: types.Message):
    raw_text = (message.text or message.caption or "").strip()
    photo_ids = []
    if message.photo:
        photo_ids.append(message.photo[-1].file_id)
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_ids.append(message.reply_to_message.photo[-1].file_id)

    await create_product_from_raw(message, raw_text, photo_ids)


@dp.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def cmd_stats(message: types.Message):
    users = load_json(USERS_FILE, [])
    orders = load_json(ORDERS_FILE, {})
    catalog = await fetch_synced_catalog(force=True)
    await message.answer(
        f"📊 <b>Статистика {SHOP_NAME}:</b>\n\n"
        f"• Пользователей в боте: <b>{len(users)}</b>\n"
        f"• Привязанных заказов: <b>{len(orders)}</b>\n"
        f"• Товаров в общем каталоге: <b>{len(catalog)}</b>",
        parse_mode="HTML"
    )


@dp.message(Command("send"), F.from_user.id == ADMIN_ID)
async def cmd_broadcast(message: types.Message):
    users = load_json(USERS_FILE, [])
    if not users:
        await message.answer("Пока нет пользователей для рассылки.")
        return

    text_to_send = message.text.partition(" ")[2].strip()
    replied = message.reply_to_message

    if not text_to_send and not replied:
        await message.answer(
            "ℹ️ Чтобы сделать рассылку, напиши:\n"
            "<code>/send Новая коллекция уже в наличии!</code>\n\n"
            "Или отправь фото с текстом в этот чат, а затем ответь (Reply) на него командой <code>/send</code>.",
            parse_mode="HTML"
        )
        return

    sent_count = 0
    for uid in users:
        if uid == ADMIN_ID:
            continue
        try:
            if replied:
                await bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=replied.message_id)
            else:
                await bot.send_message(chat_id=uid, text=text_to_send)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Рассылка завершена! Доставлено покупателям: <b>{sent_count}</b>.", parse_mode="HTML")


# 4. Кнопки меню покупателя
@dp.message(F.text.in_({"💳 Оплата СБП", "💳 Реквизиты для оплаты"}))
async def send_payment_info(message: types.Message):
    await send_sbp_payment(message.chat.id)


@dp.callback_query(F.data == "send_receipt")
async def callback_send_receipt(callback: types.CallbackQuery):
    await callback.message.answer(
        "📸 <b>Отправьте скриншот или PDF-чек об оплате прямо в этот чат.</b>\n\n"
        "Мы сразу проверим поступление и передадим ваш заказ на сборку!",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(F.text == "🚚 Доставка и возврат")
async def send_delivery_info(message: types.Message):
    await message.answer(DELIVERY_TEXT, parse_mode="HTML")


@dp.message(F.text == "📏 Таблица размеров")
async def send_size_guide(message: types.Message):
    await message.answer(SIZE_GUIDE_TEXT, parse_mode="HTML")


@dp.message(F.text == "💬 Написать менеджеру")
async def contact_manager(message: types.Message):
    await message.answer(
        "✍️ Напишите ваш вопрос прямо в этот чат (можно прикрепить фото). Менеджер ответит вам в ближайшее время!"
    )


# 5. Промокод за подписку
@dp.message(F.text == "🎁 Промокод")
async def send_promo(message: types.Message):
    if not CHANNEL_USERNAME:
        await message.answer(
            f"🎁 Ваш персональный промокод на первый заказ: <code>{PROMO_CODE}</code>\n\n"
            "Укажите его на сайте в корзине или напишите менеджеру для активации скидки!",
            parse_mode="HTML"
        )
        return

    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, message.from_user.id)
        if member.status in ("member", "administrator", "creator"):
            await message.answer(
                f"🎉 Спасибо за подписку! Ваш промокод: <code>{PROMO_CODE}</code>",
                parse_mode="HTML"
            )
            return
    except Exception:
        pass

    clean_channel = CHANNEL_USERNAME.lstrip("@")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{clean_channel}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
    ])
    await message.answer(
        f"🎁 Подпишитесь на наш Telegram-канал {CHANNEL_USERNAME}, чтобы получить промокод на скидку!",
        reply_markup=kb
    )


@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, callback.from_user.id)
        if member.status in ("member", "administrator", "creator"):
            await callback.message.edit_text(
                f"🎉 Подписка подтверждена! Ваш промокод: <code>{PROMO_CODE}</code>",
                parse_mode="HTML"
            )
            await callback.answer("Промокод активирован!")
            return
    except Exception:
        pass
    await callback.answer("Вы пока не подписались на канал 😔", show_alert=True)


# 6. Синхронизированный каталог в боте
def format_product_caption(item: dict) -> str:
    sizes_str = ", ".join(item.get("sizes", []))
    desc_block = f"\n\n{html.escape(item['desc'])}" if item.get("desc") else ""
    return (
        f"👕 <b>{html.escape(item['name'])}</b>\n\n"
        f"💰 Цена: <b>{format_price_str(item['price'])}</b>\n"
        f"📐 Размеры в наличии: <b>{html.escape(sizes_str)}</b>"
        f"{desc_block}"
    )


async def render_catalog_item(
    target_message: types.Message,
    idx: int,
    is_admin: bool,
    replace: bool = False,
    photo_idx: int = 0,
    force_refresh: bool = False
):
    catalog = await fetch_synced_catalog(force=force_refresh)
    if not catalog:
        empty_text = "🛍 Каталог пока пуст. Новые позиции скоро появятся!"
        if is_admin:
            empty_text += "\n\n<i>Добавь первый товар командой:</i>\n<code>/add Название | Цена | Размеры | Описание</code>"
        if replace:
            try:
                await target_message.delete()
            except Exception:
                pass
        await target_message.answer(empty_text, parse_mode="HTML")
        return

    idx = idx % len(catalog)
    item = catalog[idx]
    photos = item.get("photos", [])
    photo_idx = photo_idx % len(photos) if photos else 0
    current_photo = photos[photo_idx] if photos else None

    caption = format_product_caption(item)
    kb = get_catalog_keyboard(
        idx,
        len(catalog),
        photo_idx=photo_idx,
        photos_count=len(photos),
        is_admin=is_admin
    )

    if replace:
        if target_message.photo and current_photo:
            try:
                await target_message.edit_media(
                    media=InputMediaPhoto(media=current_photo, caption=caption, parse_mode="HTML"),
                    reply_markup=kb
                )
                return
            except Exception:
                pass

        if target_message.photo or current_photo:
            try:
                await target_message.delete()
            except Exception:
                pass
            if current_photo:
                try:
                    await target_message.answer_photo(photo=current_photo, caption=caption, parse_mode="HTML", reply_markup=kb)
                    return
                except Exception:
                    pass
            await target_message.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            await target_message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
    else:
        if current_photo:
            try:
                await target_message.answer_photo(photo=current_photo, caption=caption, parse_mode="HTML", reply_markup=kb)
                return
            except Exception:
                pass
        await target_message.answer(caption, parse_mode="HTML", reply_markup=kb)


@dp.message(F.text == "👕 Каталог")
async def show_catalog(message: types.Message):
    is_admin = (message.from_user.id == ADMIN_ID)
    await render_catalog_item(message, 0, is_admin=is_admin, replace=False, photo_idx=0, force_refresh=True)


@dp.callback_query(F.data == "noop")
async def callback_noop(callback: types.CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_nav:"))
async def callback_catalog_nav(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    is_admin = (callback.from_user.id == ADMIN_ID)
    await render_catalog_item(callback.message, idx, is_admin=is_admin, replace=True, photo_idx=0)
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_pic:"))
async def callback_catalog_pic(callback: types.CallbackQuery):
    _, idx_str, pic_str = callback.data.split(":")
    is_admin = (callback.from_user.id == ADMIN_ID)
    await render_catalog_item(
        callback.message,
        int(idx_str),
        is_admin=is_admin,
        replace=True,
        photo_idx=int(pic_str)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_addpic:"))
async def callback_catalog_addpic(callback: types.CallbackQuery):
    global admin_wait_photo_idx
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    idx = int(callback.data.split(":")[1])
    catalog = await fetch_synced_catalog(force=True)
    if 0 <= idx < len(catalog):
        admin_wait_photo_idx = idx
        item_name = html.escape(catalog[idx]["name"])
        await callback.message.answer(
            f"📸 Отправь в этот чат <b>1 фото или целый альбом</b> для товара <b>«{item_name}»</b> (подпись не нужна).\n\n"
            "<i>Для отмены нажми /cancel</i>",
            parse_mode="HTML"
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_del:"))
async def callback_catalog_delete(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    idx = int(callback.data.split(":")[1])
    catalog = await fetch_synced_catalog(force=True)
    if 0 <= idx < len(catalog):
        removed = catalog.pop(idx)
        await save_synced_catalog(catalog, f"Delete product from bot: {removed['name']}")
        await callback.answer(f"🗑 Удалено на сайте и в боте: {removed['name']}")
    else:
        await callback.answer("Товар уже удален")

    await render_catalog_item(callback.message, idx, is_admin=True, replace=True, photo_idx=0)


@dp.callback_query(F.data.startswith("cat_buy:"))
async def callback_catalog_buy(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    catalog = await fetch_synced_catalog()
    if not catalog or idx >= len(catalog):
        await callback.answer("Товар больше не доступен", show_alert=True)
        return

    item = catalog[idx]
    size_buttons = [
        InlineKeyboardButton(text=size, callback_data=f"cat_size:{idx}:{size}")
        for size in item.get("sizes", ["S", "M", "L"])
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        size_buttons,
        [InlineKeyboardButton(text="⬅️ Назад к товару", callback_data=f"cat_nav:{idx}")]
    ])
    text = f"📐 Выберите размер для <b>{html.escape(item['name'])}</b>:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
    else:
        await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_size:"))
async def callback_catalog_size(callback: types.CallbackQuery):
    _, idx_str, size = callback.data.split(":")
    idx = int(idx_str)
    catalog = await fetch_synced_catalog()
    if not catalog or idx >= len(catalog):
        await callback.answer("Товар больше не доступен", show_alert=True)
        return

    item = catalog[idx]
    price_str = format_price_str(item["price"])
    order_id = str(random.randint(1000, 9999))
    user = callback.from_user

    link_order_to_client(order_id, user.id)
    username = f"@{user.username}" if user.username else "скрыт"

    await bot.send_message(
        ADMIN_ID,
        f"🛍 <b>НОВЫЙ ЗАКАЗ ИЗ БОТА #{order_id}</b>\n\n"
        f"• Товар: <b>{html.escape(item['name'])}</b>\n"
        f"• Размер: <b>{html.escape(size)}</b>\n"
        f"• Сумма: <b>{price_str}</b>\n\n"
        f"👤 Покупатель: {html.escape(user.full_name)} ({username})\n"
        f"ID клиента: <code>{user.id}</code>",
        parse_mode="HTML",
        reply_markup=get_order_admin_keyboard(order_id)
    )

    if callback.message.photo:
        await callback.message.delete()
    else:
        await callback.message.edit_text(
            f"✅ <b>Заказ #{order_id} оформлен!</b>\n"
            f"Товар: {html.escape(item['name'])} (размер <b>{html.escape(size)}</b>)\n"
            f"Сумма к оплате (нажмите, чтобы скопировать): <code>{price_str}</code>",
            parse_mode="HTML"
        )

    await send_sbp_payment(user.id)
    await callback.answer("Заказ оформлен!")


# 7. Ответ админа клиенту через Reply + прием одиночного фото при нажатии "📸 + Фото"
@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def reply_to_client(message: types.Message):
    replied = message.reply_to_message
    client_id = None

    if replied.forward_from:
        client_id = replied.forward_from.id
    elif replied.text and "ID клиента:" in replied.text:
        try:
            client_id = int(replied.text.split("ID клиента:")[1].strip().split()[0])
        except Exception:
            pass

    if client_id:
        try:
            await bot.copy_message(
                chat_id=client_id,
                from_chat_id=ADMIN_ID,
                message_id=message.message_id
            )
            await message.reply("✅ Ответ отправлен покупателю.")
        except Exception as e:
            await message.reply(f"⚠️ Не удалось отправить сообщение клиенту: {e}")
    else:
        await message.reply(
            "⚠️ Чтобы ответить покупателю, нажми <b>Ответить (Reply)</b> именно на карточку с его <code>ID клиента</code>.",
            parse_mode="HTML"
        )


@dp.message(F.from_user.id == ADMIN_ID, F.photo)
async def handle_admin_single_photo(message: types.Message):
    if admin_wait_photo_idx is not None:
        await append_photos_to_product(message, admin_wait_photo_idx, [message.photo[-1].file_id])
    else:
        await message.answer(
            "ℹ️ Если хочешь создать новый товар с этим фото — ответь на него командой:\n"
            "<code>/add Название | Цена | S, M, L | Описание</code>\n\n"
            "А если хочешь добавить фото к существующей вещи — открой <b>👕 Каталог</b> и нажми <b>📸 + Фото</b>.",
            parse_mode="HTML"
        )


# 8. Пересылка сообщений и чеков от покупателей админу
@dp.message(F.from_user.id != ADMIN_ID)
async def forward_client_message(message: types.Message):
    user = message.from_user
    register_user(user.id)
    safe_name = html.escape(user.full_name)
    username = f"@{user.username}" if user.username else "скрыт"

    await bot.send_message(
        ADMIN_ID,
        f"📩 <b>Новое сообщение / Чек от покупателя</b>\n"
        f"Имя: {safe_name} ({username})\n"
        f"ID клиента: <code>{user.id}</code>\n"
        f"<i>(Чтобы ответить, сделай Reply на это сообщение)</i>",
        parse_mode="HTML"
    )
    await message.forward(ADMIN_ID)

    await message.answer(
        "✅ Сообщение передано менеджеру! Если это чек об оплате — мы проверим его и скоро подтвердим заказ."
    )


# 9. Управление статусом заказа + авто-уведомление покупателю
@dp.callback_query(F.data.startswith(("ord:", "order_")))
async def handle_order_status(callback: types.CallbackQuery):
    if ":" in callback.data:
        _, action, order_id = callback.data.split(":")
    else:
        parts = callback.data.split("_")
        action = parts[1]
        order_id = parts[2] if len(parts) > 2 else ""

    original_text = callback.message.text or ""
    lines = [line for line in original_text.split("\n") if not line.startswith("📌 СТАТУС:")]
    clean_text = "\n".join(lines)

    if action == "pay":
        await callback.message.reply(
            f"📋 <b>Реквизиты для заказа #{html.escape(order_id)}:</b>\n\n{PAYMENT_TEXT}",
            parse_mode="HTML",
            reply_markup=get_payment_keyboard()
        )
        await callback.answer("Реквизиты отправлены в чат")
        return

    status_map = {
        "paid": ("✅ ОПЛАЧЕНО (В сборке)", f"🎉 <b>Оплата по заказу #{html.escape(order_id)} подтверждена!</b>\nМы уже передали ваш заказ на сборку. Скоро сообщим об отправке!"),
        "ship": ("📦 ОТПРАВЛЕНО КЛИЕНТУ", f"📦 <b>Ваш заказ #{html.escape(order_id)} отправлен!</b>\nСпасибо за покупку в <b>{SHOP_NAME}</b>. Если понадобится трек-номер — напишите в этот чат."),
        "shipped": ("📦 ОТПРАВЛЕНО КЛИЕНТУ", f"📦 <b>Ваш заказ #{html.escape(order_id)} отправлен!</b>\nСпасибо за покупку в <b>{SHOP_NAME}</b>."),
        "canc": ("❌ ОТМЕНЕН", f"❌ <b>Ваш заказ #{html.escape(order_id)} был отменен.</b>\nЕсли это произошло по ошибке или у вас есть вопросы — напишите нам в этот чат."),
        "cancel": ("❌ ОТМЕНЕН", f"❌ <b>Ваш заказ #{html.escape(order_id)} был отменен.</b>"),
    }

    admin_label, client_notice = status_map.get(action, ("ОБНОВЛЕН", None))
    updated_text = f"{clean_text}\n\n📌 СТАТУС: {admin_label}"

    await callback.message.edit_text(
        updated_text,
        reply_markup=callback.message.reply_markup
    )

    client_id = get_order_client(order_id)
    if client_id and client_notice:
        try:
            await bot.send_message(client_id, client_notice, parse_mode="HTML")
            await callback.answer("Статус обновлен, клиент уведомлен!")
            return
        except Exception:
            pass

    await callback.answer(f"Статус изменен: {admin_label}")


async def main():
    if SITE_URL.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🛍 Магазин", web_app=WebAppInfo(url=SITE_URL))
        )
    print(f"🚀 Бот магазина {SHOP_NAME} успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())