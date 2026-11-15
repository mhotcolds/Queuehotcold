import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ChatMemberUpdated
from aiogram.enums import ChatMemberStatus

# ==================== تنظیمات ====================
BOT_TOKEN = "8971917249:AAHdb_9RzkbkbZlPelsbjlb2CSXkRzhESUM"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# متغیرهای سراسری
media_queue = asyncio.Queue()
current_prefix = ""
interval_seconds = 60
target_channel_id = None

# ==================== FSM ====================
class AdminStates(StatesGroup):
    waiting_for_prefix = State()
    waiting_for_interval = State()

# ==================== کیبورد ====================
def get_control_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(text="⚙️ تنظیم پیشوند کپشن", callback_data="set_prefix"),
            InlineKeyboardButton(text="⏱️ تنظیم فاصله زمانی", callback_data="set_interval")
        ],
        [
            InlineKeyboardButton(text="📊 وضعیت صف", callback_data="queue_status"),
            InlineKeyboardButton(text="🗑️ پاک کردن کل صف", callback_data="clear_queue")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== تنظیم منوی دستورات ====================
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="شروع ربات و نمایش پنل"),
        BotCommand(command="panel", description="پنل کنترل"),
        BotCommand(command="setting", description="تنظیمات"),
        BotCommand(command="status", description="وضعیت صف"),
        BotCommand(command="help", description="راهنما"),
    ]
    await bot.set_my_commands(commands)

# ==================== وقتی ربات ادمین کانال می‌شود ====================
@dp.my_chat_member()
async def on_bot_status_changed(event: ChatMemberUpdated):
    global target_channel_id

    # فقط کانال‌ها را در نظر بگیر
    if event.chat.type != "channel":
        return

    new_status = event.new_chat_member.status

    if new_status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        target_channel_id = event.chat.id
        logging.info(f"کانال مقصد تنظیم شد → {target_channel_id} | {event.chat.title}")

        # سعی می‌کنیم به کسی که ربات را ادمین کرده پیام بدهیم
        try:
            await bot.send_message(
                chat_id=event.from_user.id,
                text=(
                    f"✅ ربات با موفقیت در کانال **{event.chat.title}** ادمین شد.\n\n"
                    f"از این به بعد فایل‌ها به این کانال ارسال می‌شوند."
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif new_status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
        if target_channel_id == event.chat.id:
            target_channel_id = None
            logging.info("ربات از کانال حذف شد. کانال مقصد پاک شد.")

# ==================== دستورات ====================
@dp.message(Command("start", "panel", "setting"))
async def cmd_start(message: types.Message):
    channel_text = f"`{target_channel_id}`" if target_channel_id else "هنوز تنظیم نشده (ربات را ادمین کانال کنید)"

    text = (
        f"🤖 **به ربات مدیریت صف ارسال خوش آمدید!**\n\n"
        f"• هر نوع فایل، عکس، ویدیو یا سند را بفرستید تا به صف اضافه شود.\n"
        f"• پیشوند فعلی: `{current_prefix if current_prefix else 'تنظیم نشده'}`\n"
        f"• فاصله زمانی: `{interval_seconds} ثانیه`\n"
        f"• کانال مقصد: {channel_text}\n"
        f"• تعداد فایل در صف: `{media_queue.qsize()}`"
    )
    await message.answer(text, reply_markup=get_control_keyboard(), parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    channel_text = f"`{target_channel_id}`" if target_channel_id else "تنظیم نشده"
    await message.answer(
        f"📊 **وضعیت فعلی:**\n\n"
        f"• فایل‌های در صف: `{media_queue.qsize()}`\n"
        f"• فاصله زمانی: `{interval_seconds}` ثانیه\n"
        f"• کانال مقصد: {channel_text}",
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📖 **راهنما:**\n\n"
        "۱. ربات را به کانال خود اضافه کنید و آن را **ادمین** کنید.\n"
        "۲. فایل‌ها را برای ربات بفرستید تا وارد صف شوند.\n"
        "۳. از دکمه‌های پنل برای تنظیم پیشوند و زمان استفاده کنید.\n\n"
        "**دستورات:**\n"
        "/start - نمایش پنل\n"
        "/status - وضعیت صف و کانال\n"
        "/help - راهنما"
    )
    await message.answer(text)

# ==================== دکمه‌ها ====================
@dp.callback_query(F.data.in_(["set_prefix", "set_interval", "queue_status", "clear_queue"]))
async def handle_callbacks(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data

    if action == "set_prefix":
        await callback.message.answer("لطفاً پیشوند مورد نظر را ارسال کنید:")
        await state.set_state(AdminStates.waiting_for_prefix)
        await callback.answer()

    elif action == "set_interval":
        await callback.message.answer("⏱️ فاصله زمانی را به **ثانیه** وارد کنید (حداقل ۱۰):")
        await state.set_state(AdminStates.waiting_for_interval)
        await callback.answer()

    elif action == "queue_status":
        await callback.answer(f"تعداد فایل در صف: {media_queue.qsize()}", show_alert=True)

    elif action == "clear_queue":
        while not media_queue.empty():
            try:
                media_queue.get_nowait()
                media_queue.task_done()
            except asyncio.QueueEmpty:
                break
        await callback.message.answer("🗑️ صف کاملاً پاک شد.", reply_markup=get_control_keyboard())
        await callback.answer()

# ==================== ذخیره پیشوند ====================
@dp.message(AdminStates.waiting_for_prefix)
async def save_prefix(message: types.Message, state: FSMContext):
    global current_prefix
    current_prefix = message.text.strip()
    await state.clear()
    await message.answer(
        f"✅ پیشوند ثبت شد:\n`{current_prefix}`",
        reply_markup=get_control_keyboard(),
        parse_mode="Markdown"
    )

# ==================== ذخیره فاصله زمانی ====================
@dp.message(AdminStates.waiting_for_interval)
async def save_interval(message: types.Message, state: FSMContext):
    global interval_seconds
    try:
        val = int(message.text.strip())
        if val < 10:
            await message.answer("❌ حداقل ۱۰ ثانیه مجاز است. دوباره وارد کنید:")
            return
        interval_seconds = val
        await state.clear()
        await message.answer(
            f"⏱️ فاصله زمانی تنظیم شد: `{interval_seconds} ثانیه`",
            reply_markup=get_control_keyboard(),
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ فقط عدد وارد کنید:")

# ==================== دریافت فایل‌ها ====================
@dp.message(F.content_type.in_({"photo", "video", "document", "animation", "audio", "voice", "video_note"}))
async def handle_media(message: types.Message):
    if target_channel_id is None:
        await message.reply(
            "❌ کانال مقصد هنوز تنظیم نشده.\n\n"
            "لطفاً ربات را به کانال اضافه کنید و آن را **ادمین** کنید."
        )
        return

    file_id = None
    media_type = "document"

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.document:
        file_id = message.document.file_id
        media_type = "document"
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "document"
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "document"
    elif message.voice:
        file_id = message.voice.file_id
        media_type = "document"
    elif message.video_note:
        file_id = message.video_note.file_id
        media_type = "document"

    if not file_id:
        await message.reply("❌ فایل شناسایی نشد.")
        return

    await media_queue.put({
        "type": media_type,
        "file_id": file_id,
        "caption": message.caption or "",
        "chat_id": message.chat.id,
        "message_id": message.message_id
    })

    await message.reply(
        f"✅ به صف اضافه شد\n"
        f"نوع: `{media_type}` | تعداد در صف: `{media_queue.qsize()}`",
        parse_mode="Markdown"
    )

# ==================== Worker ====================
async def queue_worker():
    global interval_seconds, current_prefix, target_channel_id

    while True:
        try:
            item = await media_queue.get()

            if target_channel_id is None:
                media_queue.task_done()
                continue

            caption = item["caption"]
            if current_prefix:
                final_caption = f"{current_prefix}\n\n{caption}" if caption else current_prefix
            else:
                final_caption = caption

            if item["type"] == "photo":
                await bot.send_photo(target_channel_id, item["file_id"], caption=final_caption)
            elif item["type"] == "video":
                await bot.send_video(target_channel_id, item["file_id"], caption=final_caption)
            else:
                await bot.send_document(target_channel_id, item["file_id"], caption=final_caption)

            # حذف پیام کاربر
            try:
                await bot.delete_message(item["chat_id"], item["message_id"])
            except Exception:
                pass

            media_queue.task_done()
            await asyncio.sleep(interval_seconds)

        except Exception as e:
            logging.error(f"خطا در ارسال: {e}")
            await asyncio.sleep(5)

# ==================== شروع ====================
async def main():
    await set_bot_commands()
    asyncio.create_task(queue_worker())
    logging.info("ربات آماده است...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
