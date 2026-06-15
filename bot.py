import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database import *

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("8263223680"))

async def check_membership(bot, user_id):
    channels = await get_channels()
    for channel_id, _ in channels:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id:
                referred_by = None
        except:
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
        for channel_id, channel_name in channels:
            if channel_id.startswith('@'):
                url = f"https://t.me/{channel_id[1:]}"
            else:
                url = f"https://t.me/{channel_id}"
            keyboard.append([InlineKeyboardButton(f"📢 {channel_name}", url=url)])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_membership")])

        await update.message.reply_text(
            "👋 سلام!\n\n"
            "برای استفاده از ربات، ابتدا در کانال ما عضو شو:\n\n"
            "بعد از عضویت روی دکمه «عضو شدم» کلیک کن ✅",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await show_main_menu(update, context)

async def show_main_menu(update, context):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🏆 لیدربورد", callback_data="leaderboard"),
         InlineKeyboardButton("👤 پروفایل من", callback_data="profile")],
        [InlineKeyboardButton("🎁 جایزه روزانه", callback_data="daily"),
         InlineKeyboardButton("🔗 لینک دعوت", callback_data="referral")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")]
    ]
    text = (f"سلام {user.first_name}! 👋\n\n"
            f"به ربات NightNote خوش اومدی 🌙\n"
            f"از منوی زیر انتخاب کن:")

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if query.data == "check_membership":
        is_member = await check_membership(context.bot, user.id)
        if is_member:
            await show_main_menu(update, context)
        else:
            await query.answer("❌ هنوز عضو نشدی!", show_alert=True)

    elif query.data == "leaderboard":
        top = await get_leaderboard()
        text = "🏆 برترین‌های NightNote:\n\n"
        for i, (name, username, score) in enumerate(top, 1):
            display = f"@{username}" if username else name
            text += f"{i}. {display} - {score} امتیاز\n"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "profile":
        db_user = await get_user(user.id)
        all_users = await get_all_users()
        all_scores = []
        async with __import__('aiosqlite').connect('nightnote.db') as db:
            async with db.execute('SELECT score FROM users ORDER BY score DESC') as cursor:
                all_scores = [row[0] for row in await cursor.fetchall()]
        rank = all_scores.index(db_user[3]) + 1 if db_user[3] in all_scores else "-"
        text = (f"👤 پروفایل {user.first_name}\n\n"
                f"🏆 بالاترین امتیاز: {db_user[3]}\n"
                f"📊 رتبه: {rank}\n"
                f"👥 دعوت‌شده‌ها: {db_user[4]}\n")
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        db_user = await get_user(user.id)
        if db_user[6] == today:
            await query.answer("⏰ جایزه روزانه‌ات رو قبلاً گرفتی! فردا برگرد.", show_alert=True)
        else:
            await set_daily(user.id, today)
            await query.answer("🎁 +۱۰ امتیاز جایزه روزانه گرفتی!", show_alert=True)

    elif query.data == "referral":
        link = f"https://t.me/{(await context.bot.get_me()).username}?start={user.id}"
        db_user = await get_user(user.id)
        text = (f"🔗 لینک دعوت اختصاصی تو:\n\n"
                f"`{link}`\n\n"
                f"👥 تعداد دعوت‌های موفق: {db_user[4]}\n"
                f"هر دعوت = ۱ امتیاز هدیه برای دوستت!")
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data == "support":
        text = "📞 برای پشتیبانی پیام بده:\n\n@NightNote_official"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "main_menu":
        await show_main_menu(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keyboard = [
        [InlineKeyboardButton("📊 آمار", callback_data="admin_stats"),
         InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ اضافه کردن کانال", callback_data="admin_add_channel"),
         InlineKeyboardButton("➖ حذف کانال", callback_data="admin_remove_channel")],
        [InlineKeyboardButton("🚫 بن کاربر", callback_data="admin_ban"),
         InlineKeyboardButton("✅ آنبن کاربر", callback_data="admin_unban")]
    ]
    await update.message.reply_text("🔧 پنل ادمین:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    if query.data == "admin_stats":
        total = await get_stats()
        await query.edit_message_text(f"📊 آمار ربات:\n\nکل کاربران: {total}")

    elif query.data == "admin_broadcast":
        context.user_data['waiting_for'] = 'broadcast'
        await query.edit_message_text("📢 پیام همگانی رو بنویس:")

    elif query.data == "admin_add_channel":
        context.user_data['waiting_for'] = 'add_channel'
        await query.edit_message_text("➕ آیدی کانال رو بنویس (مثلاً @channel):")

    elif query.data == "admin_remove_channel":
        context.user_data['waiting_for'] = 'remove_channel'
        await query.edit_message_text("➖ آیدی کانالی که میخوای حذف کنی رو بنویس:")

    elif query.data == "admin_ban":
        context.user_data['waiting_for'] = 'ban'
        await query.edit_message_text("🚫 آیدی عددی کاربر رو بنویس:")

    elif query.data == "admin_unban":
        context.user_data['waiting_for'] = 'unban'
        await query.edit_message_text("✅ آیدی عددی کاربر رو بنویس:")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    waiting = context.user_data.get('waiting_for')

    if waiting == 'broadcast':
        users = await get_all_users()
        sent = 0
        for (uid,) in users:
            try:
                await context.bot.send_message(uid, update.message.text)
                sent += 1
            except:
                pass
        await update.message.reply_text(f"✅ پیام به {sent} نفر ارسال شد.")
        context.user_data['waiting_for'] = None

    elif waiting == 'add_channel':
        channel_id = update.message.text.strip()
        await add_channel(channel_id, channel_id)
        await update.message.reply_text(f"✅ کانال {channel_id} اضافه شد.")
        context.user_data['waiting_for'] = None

    elif waiting == 'remove_channel':
        channel_id = update.message.text.strip()
        await remove_channel(channel_id)
        await update.message.reply_text(f"✅ کانال {channel_id} حذف شد.")
        context.user_data['waiting_for'] = None

    elif waiting == 'ban':
        try:
            uid = int(update.message.text.strip())
            await ban_user(uid)
            await update.message.reply_text(f"🚫 کاربر {uid} بن شد.")
        except:
            await update.message.reply_text("❌ آیدی اشتباهه.")
        context.user_data['waiting_for'] = None

    elif waiting == 'unban':
        try:
            uid = int(update.message.text.strip())
            await unban_user(uid)
            await update.message.reply_text(f"✅ کاربر {uid} آنبن شد.")
        except:
            await update.message.reply_text("❌ آیدی اشتباهه.")
        context.user_data['waiting_for'] = None

async def main():
    await init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    print("ربات روشنه! 🚀")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
