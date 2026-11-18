import asyncio
import html
import json
import logging
import os
import random
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
)

# ================= НАСТРОЙКИ МАГАЗИНА =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5100544808
SHOP_NAME = "ATELIER"

# Ссылка на сайт (оставь "", пока не выложим сайт; потом впишешь https://...)
SITE_URL = ""

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

# Мини-каталог товаров в боте
CATALOG = [
    {
        "name": "Худи ATELIER Heavyweight Black",
        "price": "5 900 ₽",
        "sizes": ["S", "M", "L", "XL"],
        "desc": "Плотный футер 460 г/м², 100% хлопок, объемный капюшон и спущенное плечо.",
        "photo": ""
    },
    {
        "name": "Футболка ATELIER Boxy Fit White",
        "price": "2 900 ₽",
        "sizes": ["S", "M", "L", "XL"],
        "desc": "Плотный хлопок 260 г/м², не просвечивает, держит форму после стирок.",
        "photo": ""
    },
    {
        "name": "Свитшот ATELIER Graphite",
        "price": "4 800 ₽",
        "sizes": ["M", "L", "XL"],
        "desc": "Свободный крой, мягкий начес внутри, минималистичная вышивка в тон.",
        "photo": ""
    }
]
# ======================================================

USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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


def get_catalog_keyboard(index: int) -> InlineKeyboardMarkup:
    total = len(CATALOG)
    prev_idx = (index - 1) % total
    next_idx = (index + 1) % total
    buttons = [
        [InlineKeyboardButton(text="🛒 Заказать эту вещь", callback_data=f"cat_buy:{index}")],
    ]
    if total > 1:
        buttons.append([
            InlineKeyboardButton(text="⬅️", callback_data=f"cat_nav:{prev_idx}"),
            InlineKeyboardButton(text=f"{index + 1} / {total}", callback_data="noop"),
            InlineKeyboardButton(text="➡️", callback_data=f"cat_nav:{next_idx}"),
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


# Отправка QR-кода, ссылки СБП и реквизитов
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


# 1. Команда /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    register_user(user_id)

    if user_id == ADMIN_ID:
        await message.answer(
            f"👋 Привет, Арсен! Бот магазина <b>{SHOP_NAME}</b> работает в облаке 24/7.\n\n"
            "<b>Твои команды владельца:</b>\n"
            "• <code>/stats</code> — статистика клиентов и заказов\n"
            "• <code>/send текст</code> — рассылка всем пользователям (или ответь <code>/send</code> на фото)\n"
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
            "Здесь можно посмотреть каталог, подобрать размер, оплатить заказ по СБП или задать вопрос менеджеру 👇",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )


# 2. Админ-команды
@dp.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def cmd_stats(message: types.Message):
    users = load_json(USERS_FILE, [])
    orders = load_json(ORDERS_FILE, {})
    await message.answer(
        f"📊 <b>Статистика {SHOP_NAME}:</b>\n\n"
        f"• Пользователей в боте: <b>{len(users)}</b>\n"
        f"• Привязанных заказов: <b>{len(orders)}</b>",
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


# 3. Кнопки меню покупателя
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


# 4. Промокод за подписку
@dp.message(F.text == "🎁 Промокод")
async def send_promo(message: types.Message):
    if not CHANNEL_USERNAME:
        await message.answer(
            f"🎁 Ваш персональный промокод на первый заказ: <code>{PROMO_CODE}</code>\n\n"
            "Укажите его в комментарии к заказу или напишите менеджеру для активации скидки!",
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


# 5. Мини-каталог в боте
def format_product_caption(item: dict) -> str:
    sizes_str = ", ".join(item["sizes"])
    return (
        f"👕 <b>{html.escape(item['name'])}</b>\n\n"
        f"💰 Цена: <b>{html.escape(item['price'])}</b>\n"
        f"📐 Размеры в наличии: <b>{html.escape(sizes_str)}</b>\n\n"
        f"{html.escape(item['desc'])}"
    )


@dp.message(F.text == "👕 Каталог")
async def show_catalog(message: types.Message):
    if not CATALOG:
        await message.answer("Каталог скоро обновится!")
        return
    item = CATALOG[0]
    caption = format_product_caption(item)
    kb = get_catalog_keyboard(0)

    if item.get("photo"):
        try:
            await message.answer_photo(photo=item["photo"], caption=caption, parse_mode="HTML", reply_markup=kb)
            return
        except Exception:
            pass
    await message.answer(caption, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "noop")
async def callback_noop(callback: types.CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_nav:"))
async def callback_catalog_nav(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    item = CATALOG[idx]
    caption = format_product_caption(item)
    kb = get_catalog_keyboard(idx)

    if callback.message.photo:
        await callback.message.delete()
        if item.get("photo"):
            try:
                await callback.message.answer_photo(photo=item["photo"], caption=caption, parse_mode="HTML", reply_markup=kb)
                await callback.answer()
                return
            except Exception:
                pass
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=kb)
    else:
        if item.get("photo"):
            await callback.message.delete()
            try:
                await callback.message.answer_photo(photo=item["photo"], caption=caption, parse_mode="HTML", reply_markup=kb)
                await callback.answer()
                return
            except Exception:
                pass
        await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_buy:"))
async def callback_catalog_buy(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    item = CATALOG[idx]
    size_buttons = [
        InlineKeyboardButton(text=size, callback_data=f"cat_size:{idx}:{size}")
        for size in item["sizes"]
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
    item = CATALOG[int(idx_str)]
    order_id = str(random.randint(1000, 9999))
    user = callback.from_user

    link_order_to_client(order_id, user.id)
    username = f"@{user.username}" if user.username else "скрыт"

    await bot.send_message(
        ADMIN_ID,
        f"🛍 <b>НОВЫЙ ЗАКАЗ ИЗ БОТА #{order_id}</b>\n\n"
        f"• Товар: <b>{html.escape(item['name'])}</b>\n"
        f"• Размер: <b>{html.escape(size)}</b>\n"
        f"• Сумма: <b>{html.escape(item['price'])}</b>\n\n"
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
            f"Сумма к оплате (нажмите, чтобы скопировать): <code>{html.escape(item['price'])}</code>",
            parse_mode="HTML"
        )

    await send_sbp_payment(user.id)
    await callback.answer("Заказ оформлен!")


# 6. Ответ админа клиенту через Reply
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


# 7. Пересылка сообщений и чеков от покупателей админу
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


# 8. Управление статусом заказа + авто-уведомление покупателю
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