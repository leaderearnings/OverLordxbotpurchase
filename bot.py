import json
import os
import logging
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================== CONFIG ==================

BOT_TOKEN = "8758894480:AAHistGvGEtFW5aw7oqwxVo72j_mt6qVcWs"
ADMIN_ID = 6546821383
UPI_ID = "paytm.s18pxmm@pty"
SUPPORT = "@FRL77_BOT"
STOCK_FILE = "stock.json"
ORDERS_FILE = "orders.json"   # ✅ NEW: Order history file
QR_FILE = "qr.png"

# ================== ITEMS ==================

ITEMS = {
    "shein_500":     {"name": "SHEIN 1000 per 500 Code",       "price": "₹25", "manual_stock": 5},
    "shein_800":     {"name": "SHEIN 1000 per 800 Code",       "price": "₹25", "force_out_of_stock": True},
    "myntra":        {"name": "Myntra Code",                   "price": "₹40", "force_out_of_stock": True},
    "bigbasket":     {"name": "BigBasket Code",                "price": "₹8"},
    "lenskart_gold": {"name": "Lenskart Gold Membership 1YR",  "price": "₹99", "manual_stock": 1},
}

ITEM_TEXT_MAP = {
    "SHEIN 1000 per 500 Code - ₹25":              "shein_500",
    "SHEIN 1000 per 800 Code - Out of Stock":    "shein_800",
    "Myntra Code - Out of Stock":                "myntra",
    "BigBasket Code - ₹8":                       "bigbasket",
    "Lenskart Gold Membership 1YR - ₹99":        "lenskart_gold",
}

# ================== LOGGING ==================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== STOCK FUNCTIONS ==================

def load_stock() -> dict:
    if not os.path.exists(STOCK_FILE):
        empty = {k: [] for k in ITEMS}
        save_stock(empty)
        return empty
    with open(STOCK_FILE, "r") as f:
        data = json.load(f)
    # Ensure all keys exist
    for k in ITEMS:
        data.setdefault(k, [])
    return data


def save_stock(stock: dict) -> None:
    with open(STOCK_FILE, "w") as f:
        json.dump(stock, f, indent=2)

# ================== ORDER FUNCTIONS ==================

def load_orders() -> dict:
    """Load all orders. Format: { user_id_str: [ {order_dict}, ... ] }"""
    if not os.path.exists(ORDERS_FILE):
        save_orders({})
        return {}
    with open(ORDERS_FILE, "r") as f:
        return json.load(f)


def save_orders(orders: dict) -> None:
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


def add_order(user_id: int, item_key: str, status: str = "pending") -> str:
    """Create a new order entry and return order_id."""
    orders = load_orders()
    uid = str(user_id)
    orders.setdefault(uid, [])

    order_id = f"ORD{len(orders[uid]) + 1:04d}"
    now = datetime.now().strftime("%d-%m-%Y %H:%M")

    orders[uid].append({
        "order_id":  order_id,
        "item_key":  item_key,
        "item_name": ITEMS[item_key]["name"],
        "price":     ITEMS[item_key]["price"],
        "status":    status,          # pending / approved / rejected
        "code":      None,
        "time":      now,
    })

    save_orders(orders)
    return order_id


def update_order_status(user_id: int, item_key: str, status: str, code: str = None):
    """Update latest pending order of a user for given item."""
    orders = load_orders()
    uid = str(user_id)
    user_orders = orders.get(uid, [])

    # Find the latest pending order for this item (reverse search)
    for order in reversed(user_orders):
        if order["item_key"] == item_key and order["status"] == "pending":
            order["status"] = status
            if code:
                order["code"] = code
            break

    save_orders(orders)


def get_user_orders(user_id: int) -> list:
    orders = load_orders()
    return orders.get(str(user_id), [])

# ================== KEYBOARDS ==================

def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["🛍 Buy Codes", "📦 Stock"],
            ["🔎 My Orders", "⚠️ Disclaimer"],
            ["🆘 Help"],
        ],
        resize_keyboard=True,
    )


def items_menu():
    return ReplyKeyboardMarkup(
        [
            ["SHEIN 1000 per 500 Code - ₹25"],
            ["SHEIN 1000 per 800 Code - Out of Stock"],
            ["Myntra Code - Out of Stock"],
            ["BigBasket Code - ₹8"],
            ["Lenskart Gold Membership 1YR - ₹99"],
            ["⬅️ Back"],
        ],
        resize_keyboard=True,
    )


def payment_buttons():
    return ReplyKeyboardMarkup(
        [["✅ Done The Payment", "❌ Cancel"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_inline(user_id: int, item_key: str):
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Approve", callback_data=f"confirm:{user_id}:{item_key}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject:{user_id}:{item_key}"),
        ]]
    )

# ================== HELPERS ==================

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def get_uname(user) -> str:
    return f"@{user.username}" if user.username else "N/A"


def effective_stock_count(key: str, stock: dict) -> int:
    """Return stock count. manual_stock is used for items delivered manually by admin."""
    item = ITEMS.get(key, {})
    if item.get("force_out_of_stock", False):
        return 0
    if "manual_stock" in item:
        return int(item.get("manual_stock", 0))
    return len(stock.get(key, []))

# ================== START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🔥 *Welcome To OverLord X Shop* 🔥\n\n"
        "Choose option below 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ================== BUY CODES ==================

async def buy_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("selected_item", None)
    await update.message.reply_text(
        "🛍 *Select an item to buy:*",
        parse_mode="Markdown",
        reply_markup=items_menu(),
    )

# ================== STOCK (FIXED) ==================

async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stock = load_stock()

    lines = ["📦 *Current Stock Status*\n"]
    lines.append("┌─────────────────────────┐")

    for key, info in ITEMS.items():
        count = effective_stock_count(key, stock)
        status = "✅ Available" if count > 0 else "❌ Out of Stock"
        lines.append(f"│ *{info['name']}*")
        lines.append(f"│ Price: {info['price']}  |  Qty: `{count}` {status}")
        lines.append("│")

    lines.append("└─────────────────────────┘")
    lines.append("\n🛍 Use *Buy Codes* to purchase!")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ================== MY ORDERS (FIXED — SHOWS HISTORY) ==================

async def my_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    orders = get_user_orders(user_id)

    if not orders:
        await update.message.reply_text(
            "🔎 *My Orders*\n\n"
            "❌ Aapka koi bhi order nahi mila.\n\n"
            "🛍 *Buy Codes* se pehla order karo!",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    # Show last 5 orders (newest first)
    recent = list(reversed(orders))[:5]

    lines = ["🔎 *My Order History* (Last 5)\n"]

    STATUS_EMOJI = {
        "pending":  "⏳ Pending",
        "approved": "✅ Approved",
        "rejected": "❌ Rejected",
    }

    for i, o in enumerate(recent, 1):
        status_text = STATUS_EMOJI.get(o["status"], o["status"])
        lines.append(f"*Order #{i}* — `{o['order_id']}`")
        lines.append(f"🛒 Item : {o['item_name']}")
        lines.append(f"💰 Price: {o['price']}")
        lines.append(f"📅 Time : {o['time']}")
        lines.append(f"📌 Status: {status_text}")
        if o.get("code"):
            lines.append(f"🎁 Code : `{o['code']}`")
        lines.append("─────────────────")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ================== DISCLAIMER ==================

async def disclaimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ *Disclaimer*\n\n"
        "• Buy only if you understand the offer.\n"
        "• Codes once sold are non-refundable.\n"
        "• Payment screenshot is required.\n"
        "• Admin verification required before delivery.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ================== HELP ==================

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆘 *Support*\n\n"
        f"Contact: {SUPPORT}\n\n"
        "*How to buy:*\n"
        "1. Click 🛍 Buy Codes\n"
        "2. Select item\n"
        "3. Pay using QR/UPI\n"
        "4. Click ✅ Done The Payment\n"
        "5. Send payment screenshot\n"
        "6. Wait for admin approval\n\n"
        "*Check your orders:*\n"
        "Click 🔎 My Orders anytime!",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ================== ITEM SELECTION WITH QR ==================

async def item_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = ITEM_TEXT_MAP.get(update.message.text)
    if not key:
        return

    # Check stock first
    stock = load_stock()
    count = effective_stock_count(key, stock)
    if count == 0:
        await update.message.reply_text(
            f"❌ *{ITEMS[key]['name']}* abhi out of stock hai.\n\n"
            "Baad mein try karo ya admin se contact karo.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    context.user_data["selected_item"] = key
    context.user_data["state"] = "awaiting_payment_confirm"

    item = ITEMS[key]
    caption = (
        f"✅ *Selected Item:*\n"
        f"{item['name']}\n\n"
        f"💰 *Price:* {item['price']}\n"
        f"📊 *Stock:* `{count}` codes available\n\n"
        f"📲 *UPI ID:* `{UPI_ID}`\n\n"
        "📸 Scan QR and pay.\n\n"
        "After payment, click ✅ Done The Payment.\n"
        "To cancel, click ❌ Cancel."
    )

    try:
        with open(QR_FILE, "rb") as qr:
            await update.message.reply_photo(
                photo=qr,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=payment_buttons(),
            )
    except FileNotFoundError:
        await update.message.reply_text(
            caption + "\n\n⚠️ QR image not found. Please add `qr.png` in same folder.",
            parse_mode="Markdown",
            reply_markup=payment_buttons(),
        )

# ================== DONE PAYMENT ==================

async def done_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("selected_item")

    if not key:
        await update.message.reply_text(
            "⚠️ Please select an item first from 🛍 Buy Codes.",
            reply_markup=main_menu(),
        )
        return

    context.user_data["state"] = "awaiting_proof"
    item = ITEMS[key]

    await update.message.reply_text(
        "✅ *Payment step confirmed.*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        f"📸 *Send Payment Proof*\n\n"
        f"🛒 *Item:* {item['name']} — {item['price']}\n\n"
        "Please send your payment screenshot/proof now.",
        parse_mode="Markdown",
    )

# ================== CANCEL PAYMENT ==================

async def cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ *Payment cancelled.*\n\nBack to main menu 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ================== PAYMENT PROOF RECEIVED ==================

async def handle_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if state != "awaiting_proof":
        await update.message.reply_text(
            "⚠️ Please select an item first from 🛍 Buy Codes.",
            reply_markup=main_menu(),
        )
        return

    key = context.user_data.get("selected_item")
    item = ITEMS.get(key)
    user = update.message.from_user

    if not item:
        await update.message.reply_text(
            "⚠️ No item selected. Start again with 🛍 Buy Codes.",
            reply_markup=main_menu(),
        )
        return

    # ✅ Save order to history
    order_id = add_order(user.id, key, status="pending")
    context.user_data["order_id"] = order_id

    await update.message.reply_text(
        f"✅ *Payment proof received!*\n\n"
        f"🆔 Order ID: `{order_id}`\n\n"
        "Please wait for admin approval.\n"
        "Check status anytime via 🔎 My Orders.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    context.user_data["state"] = "pending_approval"

    caption = (
        "📸 *New Payment Proof Received*\n\n"
        f"👤 *User:* {user.full_name}\n"
        f"🆔 *User ID:* `{user.id}`\n"
        f"🔗 *Username:* {get_uname(user)}\n"
        f"🛒 *Item:* {item['name']} — {item['price']}\n"
        f"📋 *Order ID:* `{order_id}`\n\n"
        "Choose action below 👇"
    )

    markup = admin_inline(user.id, key)

    try:
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=update.message.photo[-1].file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=markup,
            )
        elif update.message.document:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=update.message.document.file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=markup,
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=caption + "\n\n⚠️ User ne photo nahi bheja.",
                parse_mode="Markdown",
                reply_markup=markup,
            )
    except Exception as e:
        logger.error(f"Proof forward error: {e}")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption + f"\n\n⚠️ Proof forward failed.\nError: `{e}`",
            parse_mode="Markdown",
            reply_markup=markup,
        )

# ================== ADMIN CALLBACK ==================

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("❌ You are not admin.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    action, uid_str, item_key = parts
    user_id = int(uid_str)
    item = ITEMS.get(item_key)

    if not item:
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "confirm":
        # ✅ Update order status to approved
        update_order_status(user_id, item_key, "approved")

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ *Payment Approved!*\n\n"
                    f"🛒 *Item:* {item['name']}\n\n"
                    "🎁 Your code will be sent shortly.\n"
                    "Please wait ✅"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Approve message error: {e}")

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "✅ *Order Approved!*\n\n"
                f"🛒 *Item:* {item['name']}\n"
                f"🆔 *User ID:* `{user_id}`\n\n"
                "➡️ *Ab sirf code type karke bhejo.*\n"
                "Bot user tak automatically code bhej dega."
            ),
            parse_mode="Markdown",
        )

        context.bot_data[f"code_pending:{ADMIN_ID}"] = {
            "user_id":  user_id,
            "item_key": item_key,
        }

    elif action == "reject":
        # ✅ Update order status to rejected
        update_order_status(user_id, item_key, "rejected")

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ *Payment Rejected*\n\n"
                    f"🛒 *Item:* {item['name']}\n\n"
                    "Your payment proof was not approved.\n"
                    f"Contact support: {SUPPORT}"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Reject message error: {e}")

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="❌ *Order rejected successfully.*",
            parse_mode="Markdown",
        )

# ================== ADMIN CODE INPUT ==================

async def admin_send_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_key = f"code_pending:{ADMIN_ID}"
    pending = context.bot_data.get(pending_key)

    if not pending:
        return

    code = update.message.text.strip()
    user_id = pending["user_id"]
    item_key = pending["item_key"]
    item = ITEMS.get(item_key, {})

    if not code:
        await update.message.reply_text("❌ Please send valid code.")
        return

    # ✅ Update order with actual code
    update_order_status(user_id, item_key, "approved", code=code)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "🎁 *Your Code Received!*\n\n"
                f"🛒 Item: *{item.get('name', '')}*\n\n"
                f"`{code}`\n\n"
                "Thank you for buying ✅\n"
                "Check 🔎 My Orders to see your code anytime!"
            ),
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            f"✅ *Code sent successfully!*\n\n"
            f"🛒 Item: {item.get('name', '')}\n"
            f"🆔 User: `{user_id}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Code send karne me error:\n`{e}`\n\nUser ID: `{user_id}`",
            parse_mode="Markdown",
        )

    del context.bot_data[pending_key]

# ================== ADMIN COMMANDS ==================

async def cmd_sendcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ You are not admin.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/sendcode USER_ID CODE`\n\n"
            "Example:\n`/sendcode 123456789 MYNTRA-XYZ-123`",
            parse_mode="Markdown",
        )
        return

    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid User ID. Numeric ID daalo.")
        return

    code = " ".join(context.args[1:])

    try:
        await context.bot.send_message(
            chat_id=target,
            text=(
                "🎁 *Your Code Received!*\n\n"
                f"`{code}`\n\n"
                "Thank you for buying ✅"
            ),
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            f"✅ Code sent to `{target}` successfully!",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


async def cmd_addcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add code to stock: /addcode <item> <code>"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ You are not admin.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/addcode <item> <code>`\n\n"
            "Items: `shein_500` `shein_800` `myntra` `bigbasket` `lenskart_gold`\n\n"
            "Note: `shein_800` and `myntra` are currently set to Out of Stock in the bot menu.\n\n"
            "Example:\n`/addcode shein_500 SHEIN-ABC-123`",
            parse_mode="Markdown",
        )
        return

    key = context.args[0].lower()
    if key not in ITEMS:
        await update.message.reply_text(
            f"❌ Unknown item: `{key}`\nValid: `shein_500`, `shein_800`, `myntra`, `bigbasket`",
            parse_mode="Markdown",
        )
        return

    code = " ".join(context.args[1:])
    stock = load_stock()
    stock.setdefault(key, []).append(code)
    save_stock(stock)

    await update.message.reply_text(
        f"✅ Code added to *{ITEMS[key]['name']}*\n"
        f"📦 Total now: `{len(stock[key])}` codes",
        parse_mode="Markdown",
    )


async def cmd_stockadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin full stock view with all codes listed"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ You are not admin.")
        return

    stock = load_stock()
    lines = ["📦 *Admin Stock View*\n"]

    for key, info in ITEMS.items():
        codes = stock.get(key, [])
        display_count = effective_stock_count(key, stock)
        lines.append(f"*{info['name']}* — {display_count} stock")
        if codes:
            for i, c in enumerate(codes, 1):
                lines.append(f"  {i}. `{c}`")
        else:
            lines.append("  _(empty)_")
        lines.append("")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: view all orders or specific user /orders [user_id]"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ You are not admin.")
        return

    orders_data = load_orders()

    if context.args:
        # Filter by user id
        uid = context.args[0]
        user_orders = orders_data.get(uid, [])
        if not user_orders:
            await update.message.reply_text(f"❌ User `{uid}` ka koi order nahi mila.", parse_mode="Markdown")
            return

        lines = [f"📋 *Orders for User* `{uid}`\n"]
        for o in reversed(user_orders):
            lines.append(f"• `{o['order_id']}` | {o['item_name']} | {o['price']} | *{o['status']}* | {o['time']}")
            if o.get("code"):
                lines.append(f"  Code: `{o['code']}`")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    else:
        # Summary of all orders
        total = sum(len(v) for v in orders_data.values())
        pending  = sum(1 for v in orders_data.values() for o in v if o["status"] == "pending")
        approved = sum(1 for v in orders_data.values() for o in v if o["status"] == "approved")
        rejected = sum(1 for v in orders_data.values() for o in v if o["status"] == "rejected")

        lines = [
            "📋 *All Orders Summary*\n",
            f"👥 Total Users: `{len(orders_data)}`",
            f"📦 Total Orders: `{total}`",
            f"⏳ Pending:  `{pending}`",
            f"✅ Approved: `{approved}`",
            f"❌ Rejected: `{rejected}`",
            "\n_Use /orders USER_ID to see specific user orders_",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_delcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: remove a specific code from stock /delcode <item> <code>"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ You are not admin.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/delcode <item> <code>`\n\nExample:\n`/delcode myntra MYNTRA-ABC-123`",
            parse_mode="Markdown",
        )
        return

    key = context.args[0].lower()
    if key not in ITEMS:
        await update.message.reply_text(f"❌ Unknown item: `{key}`", parse_mode="Markdown")
        return

    code = " ".join(context.args[1:])
    stock = load_stock()

    if code in stock.get(key, []):
        stock[key].remove(code)
        save_stock(stock)
        await update.message.reply_text(
            f"✅ Code removed from *{ITEMS[key]['name']}*\nRemaining: `{len(stock[key])}` codes",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(f"❌ Code not found in `{key}` stock.", parse_mode="Markdown")

# ================== TEXT ROUTER ==================

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    uid  = update.message.from_user.id

    if is_admin(uid) and f"code_pending:{ADMIN_ID}" in context.bot_data:
        await admin_send_code(update, context)
        return

    if text == "🛍 Buy Codes":
        await buy_codes(update, context)
    elif text == "📦 Stock":
        await show_stock(update, context)
    elif text == "🔎 My Orders":
        await my_order(update, context)
    elif text == "⚠️ Disclaimer":
        await disclaimer(update, context)
    elif text == "🆘 Help":
        await help_cmd(update, context)
    elif text == "⬅️ Back":
        context.user_data.clear()
        await update.message.reply_text("🔙 Main menu 👇", reply_markup=main_menu())
    elif text == "✅ Done The Payment":
        await done_payment(update, context)
    elif text == "❌ Cancel":
        await cancel_payment(update, context)
    elif text in ITEM_TEXT_MAP:
        await item_select(update, context)
    elif context.user_data.get("state") == "awaiting_proof":
        await update.message.reply_text(
            "📸 Please send a *photo/screenshot* as payment proof, not text.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "Please use the buttons below 👇",
            reply_markup=main_menu(),
        )

# ================== MEDIA HANDLER ==================

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "awaiting_proof":
        await handle_proof(update, context)
    else:
        await update.message.reply_text(
            "⚠️ Please select an item first from 🛍 Buy Codes before sending proof.",
            reply_markup=main_menu(),
        )

# ================== ERROR HANDLER ==================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)

# ================== MAIN ==================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))

    # Admin commands
    app.add_handler(CommandHandler("sendcode",   cmd_sendcode))
    app.add_handler(CommandHandler("addcode",    cmd_addcode))
    app.add_handler(CommandHandler("delcode",    cmd_delcode))
    app.add_handler(CommandHandler("stockadmin", cmd_stockadmin))
    app.add_handler(CommandHandler("orders",     cmd_orders))

    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_error_handler(error_handler)

    print("=" * 55)
    print("  ✅  OverLord X Shop Bot is running!")
    print(f"  Admin ID  : {ADMIN_ID}")
    print(f"  UPI       : {UPI_ID}")
    print(f"  Support   : {SUPPORT}")
    print(f"  Stock     : {STOCK_FILE}")
    print(f"  Orders DB : {ORDERS_FILE}")
    print("=" * 55)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
