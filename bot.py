import os
import asyncio
import aiosqlite
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB_NAME = "nightnote.db"

# ==================== DATABASE ====================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            score INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            last_daily TEXT DEFAULT NULL,
            is_banned INTEGER DEFAULT 0
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            channel_name TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question_id INTEGER,
            date TEXT,
            correct INTEGER
        )''')
        await db.execute('''INSERT OR IGNORE INTO channels (channel_id, channel_name) 
            VALUES (?, ?)''', ('@NightNote_official', 'NightNote'))
        await db.commit()

async def add_user(user_id, first_name, username, referred_by=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''INSERT OR IGNORE INTO users 
            (user_id, first_name, username, referred_by) VALUES (?, ?, ?, ?)''',
            (user_id, first_name, username, referred_by))
        if referred_by:
            await db.execute('''UPDATE users SET referral_count = referral_count + 1,
                score = score + 5 WHERE user_id = ?''', (referred_by,))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as c:
            return await c.fetchone()

async def get_leaderboard():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''SELECT first_name, username, score 
            FROM users WHERE is_banned = 0 ORDER BY score DESC LIMIT 10''') as c:
            return await c.fetchall()

async def get_rank(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''SELECT COUNT(*) FROM users 
            WHERE score > (SELECT score FROM users WHERE user_id = ?) 
            AND is_banned = 0''', (user_id,)) as c:
            result = await c.fetchone()
            return result[0] + 1

async def get_total_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as c:
            return (await c.fetchone())[0]

async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT channel_id, channel_name FROM channels') as c:
            return await c.fetchall()

async def add_channel(channel_id, channel_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR IGNORE INTO channels (channel_id, channel_name) VALUES (?, ?)',
            (channel_id, channel_name))
        await db.commit()

async def remove_channel(channel_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
        await db.commit()

async def ban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def unban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        await db.commit()

async def set_daily(user_id, today):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET last_daily = ?, score = score + 10 WHERE user_id = ?',
            (today, user_id))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id FROM users WHERE is_banned = 0') as c:
            return await c.fetchall()

async def add_question(question, option_a, option_b, option_c, option_d, correct):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''INSERT INTO questions 
            (question, option_a, option_b, option_c, option_d, correct) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (question, option_a, option_b, option_c, option_d, correct))
        await db.commit()

async def get_random_questions(count=5):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM questions ORDER BY RANDOM() LIMIT ?', (count,)) as c:
            return await c.fetchall()

async def get_answered_today(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''SELECT question_id FROM quiz_answers 
            WHERE user_id = ? AND date = ?''', (user_id, today)) as c:
            return [row[0] for row in await c.fetchall()]

async def save_answer(user_id, question_id, is_correct):
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''INSERT INTO quiz_answers (user_id, question_id, date, correct)
            VALUES (?, ?, ?, ?)''', (user_id, question_id, today, is_correct))
        if is_correct:
            await db.execute('UPDATE users SET score = score + 20 WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_question_by_id(q_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM questions WHERE id = ?', (q_id,)) as c:
            return await c.fetchone()

async def count_questions():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT COUNT(*) FROM questions') as c:
            return (await c.fetchone())[0]

# ==================== HELPERS ====================

async def check_membership(bot, user_id):
    channels = await get_channels()
    for channel_id, _ in channels:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🏆 لیدربورد", callback_data="leaderboard"),
         InlineKeyboardButton("👤 پروفایل من", callback_data="profile")],
        [InlineKeyboardButton("🧠 کوییز روزانه", callback_data="quiz"),
         InlineKeyboardButton("🎁 جایزه روزانه", callback_data="daily")],
        [InlineKeyboardButton("🔗 لینک دعوت", callback_data="referral"),
         InlineKeyboardButton("📞 پشتیبانی", callback_data="support")]
    ]
    text = (f"سلام {user.first_name}! 👋\n\n"
            f"به ربات NightNote خوش اومدی 🌙\n"
            f"از منوی زیر انتخاب کن:")
    markup = InlineKeyboardMarkup(keyboard)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)

# ==================== QUIZ ====================

async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user = update.effective_user
    answered_ids = await get_answered_today(user.id)

    if len(answered_ids) >= 5:
        text = "✅ کوییز امروز رو تموم کردی!\nفردا دوباره بیا 😊"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        markup = InlineKeyboardMarkup(keyboard)
        if edit:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        else:
            await update.effective_message.reply_text(text, reply_markup=markup)
        return

    total = await count_questions()
    if total == 0:
        text = "❌ هنوز سوالی اضافه نشده!\nبزودی سوالا آماده میشن 🔧"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        markup = InlineKeyboardMarkup(keyboard)
        if edit:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        else:
            await update.effective_message.reply_text(text, reply_markup=markup)
        return

    all_questions = await get_random_questions(20)
    remaining = [q for q in all_questions if q[0] not in answered_ids]

    if not remaining:
        text = "✅ کوییز امروز رو تموم کردی!\nفردا دوباره بیا 😊"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        markup = InlineKeyboardMarkup(keyboard)
        if edit:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        else:
            await update.effective_message.reply_text(text, reply_markup=markup)
        return

    question = remaining[0]
    q_id, q_text, a, b, c, d, correct = question
    num = len(answered_ids) + 1

    keyboard = [
        [InlineKeyboardButton(f"🅰️ {a}", callback_data=f"qa_{q_id}_A")],
        [InlineKeyboardButton(f"🅱️ {b}", callback_data=f"qa_{q_id}_B")],
        [InlineKeyboardButton(f"🆎 {c}", callback_data=f"qa_{q_id}_C")],
        [InlineKeyboardButton(f"🆗 {d}", callback_data=f"qa_{q_id}_D")]
    ]
    text = f"🧠 سوال {num} از 5:\n\n❓ {q_text}"
    markup = InlineKeyboardMarkup(keyboard)

    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    parts = query.data.split("_")
    q_id = int(parts[1])
    user_answer = parts[2]

    question = await get_question_by_id(q_id)
    if not question:
        return

    _, q_text, a, b, c, d, correct = question
    is_correct = user_answer == correct
    await save_answer(user.id, q_id, is_correct)

    answered_ids = await get_answered_today(user.id)
    count = len(answered_ids)

    options = {"A": a, "B": b, "C": c, "D": d}
    if is_correct:
        result = f"✅ آفرین! جواب درسته! +۲۰ امتیاز 🎉"
    else:
        result = f"❌ اشتباه!\nجواب درست: {correct} - {options.get(correct, '')}"

    if count >= 5:
        db_user = await get_user(user.id)
        keyboard = [[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]
        await query.edit_message_text(
            f"{result}\n\n🏁 کوییز امروز تموم شد!\n⭐ امتیاز کل: {db_user[3]}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("➡️ سوال بعدی", callback_data="quiz_next")]]
        await query.edit_message_text(
            f"{result}\n\n📊 {count} از 5 سوال جواب دادی",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        try:
            ref = int(context.args[0])
            if ref != user.id:
                referred_by = ref
        except Exception:
            pass

    await add_user(user.id, user.first_name, user.username, referred_by)
    db_user = await get_user(user.id)

    if db_user and db_user[7] == 1:
        await update.message.reply_text("❌ شما از ربات مسدود شده‌اید.")
        return

    is_member = await check_membership(context.bot, user.id)
    if not is_member:
        channels = await get_channels()
        keyboard = []
        for ch_id, ch_name in channels:
            url = f"https://t.me/{ch_id[1:]}" if ch_id.startswith('@') else f"https://t.me/{ch_id}"
            keyboard.append([InlineKeyboardButton(f"📢 {ch_name}", url=url)])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
        await update.message.reply_text(
            "👋 سلام!\n\nبرای استفاده از ربات، اول عضو کانال ما شو 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await send_main_menu(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data

    if data == "check_join":
        if await check_membership(context.bot, user.id):
            await send_main_menu(update, context, edit=True)
        else:
            await query.answer("❌ هنوز عضو نشدی!", show_alert=True)

    elif data == "main_menu":
        await send_main_menu(update, context, edit=True)

    elif data == "leaderboard":
        top = await get_leaderboard()
        text = "🏆 برترین‌های NightNote:\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (name, username, score) in enumerate(top, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            display = f"@{username}" if username else name
            text += f"{medal} {display} — {score} امتیاز\n"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "profile":
        db_user = await get_user(user.id)
        rank = await get_rank(user.id)
        text = (f"👤 پروفایل {user.first_name}\n\n"
                f"🏆 امتیاز: {db_user[3]}\n"
                f"📊 رتبه: {rank}\n"
                f"👥 دعوت‌های موفق: {db_user[4]}\n")
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "quiz":
        await send_quiz(update, context, edit=True)

    elif data == "quiz_next":
        await send_quiz(update, context, edit=True)

    elif data.startswith("qa_"):
        await handle_quiz_answer(update, context)

    elif data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        db_user = await get_user(user.id)
        if db_user[6] == today:
            await query.answer("⏰ جایزه روزانه رو قبلاً گرفتی! فردا برگرد.", show_alert=True)
        else:
            await set_daily(user.id, today)
            await query.answer("🎁 +۱۰ امتیاز جایزه روزانه گرفتی!", show_alert=True)

    elif data == "referral":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user.id}"
        db_user = await get_user(user.id)
        text = (f"🔗 لینک دعوت اختصاصی تو:\n\n"
                f"`{link}`\n\n"
                f"👥 دعوت‌های موفق: {db_user[4]}\n"
                f"💡 هر دعوت = ۵ امتیاز برای تو!")
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard),
                                      parse_mode='Markdown')

    elif data == "support":
        text = "📞 برای پشتیبانی پیام بده:\n\n@NightNote_official"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_stats":
        total = await get_total_users()
        q_count = await count_questions()
        text = (f"📊 آمار ربات:\n\n"
                f"👥 کل کاربران: {total}\n"
                f"🧠 تعداد سوالات: {q_count}")
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_broadcast":
        context.user_data['waiting'] = 'broadcast'
        await query.edit_message_text("📢 پیام همگانی رو بنویس:")

    elif data == "admin_add_ch":
        context.user_data['waiting'] = 'add_ch'
        await query.edit_message_text("➕ آیدی کانال رو بنویس (مثلاً @channel):")

    elif data == "admin_remove_ch":
        context.user_data['waiting'] = 'remove_ch'
        await query.edit_message_text("➖ آیدی کانالی که میخوای حذف کنی:")

    elif data == "admin_ban":
        context.user_data['waiting'] = 'ban'
        await query.edit_message_text("🚫 آیدی عددی کاربر رو بنویس:")

    elif data == "admin_unban":
        context.user_data['waiting'] = 'unban'
        await query.edit_message_text("✅ آیدی عددی کاربر رو بنویس:")

    elif data == "admin_add_q":
        context.user_data['waiting'] = 'add_question'
        await query.edit_message_text(
            "➕ سوال رو به این فرمت بنویس:\n\n"
            "سوال|گزینه A|گزینه B|گزینه C|گزینه D|جواب درست\n\n"
            "مثال:\n"
            "پایتخت ایران کجاست؟|تهران|اصفهان|شیراز|تبریز|A"
        )

    elif data == "admin_menu":
        await show_admin_panel(update, context, edit=True)

async def show_admin_panel(update, context, edit=False):
    keyboard = [
        [InlineKeyboardButton("📊 آمار", callback_data="admin_stats"),
         InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ اضافه کانال", callback_data="admin_add_ch"),
         InlineKeyboardButton("➖ حذف کانال", callback_data="admin_remove_ch")],
        [InlineKeyboardButton("🚫 بن کاربر", callback_data="admin_ban"),
         InlineKeyboardButton("✅ آنبن کاربر", callback_data="admin_unban")],
        [InlineKeyboardButton("🧠 اضافه کردن سوال", callback_data="admin_add_q")]
    ]
    text = "🔧 پنل ادمین NightNote:"
    markup = InlineKeyboardMarkup(keyboard)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await show_admin_panel(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    waiting = context.user_data.get('waiting')
    if not waiting:
        return
    text = update.message.text.strip()
    context.user_data['waiting'] = None

    if waiting == 'broadcast':
        users = await get_all_users()
        sent = 0
        for (uid,) in users:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await update.message.reply_text(f"✅ پیام به {sent} نفر ارسال شد.")

    elif waiting == 'add_ch':
        await add_channel(text, text)
        await update.message.reply_text(f"✅ کانال {text} اضافه شد.")

    elif waiting == 'remove_ch':
        await remove_channel(text)
        await update.message.reply_text(f"✅ کانال {text} حذف شد.")

    elif waiting == 'ban':
        try:
            await ban_user(int(text))
            await update.message.reply_text(f"🚫 کاربر {text} بن شد.")
        except Exception:
            await update.message.reply_text("❌ آیدی اشتباهه.")

    elif waiting == 'unban':
        try:
            await unban_user(int(text))
            await update.message.reply_text(f"✅ کاربر {text} آنبن شد.")
        except Exception:
            await update.message.reply_text("❌ آیدی اشتباهه.")

    elif waiting == 'add_question':
        parts = text.split('|')
        if len(parts) != 6:
            await update.message.reply_text(
                "❌ فرمت اشتباهه!\n\n"
                "باید دقیقاً ۶ بخش با | جدا باشن:\n"
                "سوال|A|B|C|D|جواب\n\n"
                "مثال:\n"
                "پایتخت ایران؟|تهران|اصفهان|شیراز|تبریز|A"
            )
            context.user_data['waiting'] = 'add_question'
            return
        try:
            await add_question(parts[0].strip(), parts[1].strip(), parts[2].strip(),
                             parts[3].strip(), parts[4].strip(), parts[5].strip().upper())
            await update.message.reply_text(
                f"✅ سوال اضافه شد!\n\n"
                f"❓ {parts[0]}\n"
                f"A: {parts[1]}\n"
                f"B: {parts[2]}\n"
                f"C: {parts[3]}\n"
                f"D: {parts[4]}\n"
                f"✔️ جواب: {parts[5].upper()}\n\n"
                f"برای اضافه کردن سوال بعدی دوباره بفرست."
            )
            context.user_data['waiting'] = 'add_question'
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")

# ==================== MAIN ====================

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init_db())
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🌙 NightNote Bot is running!")
    app.run_polling(drop_pending_updates=True)
