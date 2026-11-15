import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ==================== تنظیمات ====================
BOT_TOKEN = "TOKEN_BOT_خود_را_اینجا_قرار_دهید"
CHANNEL_ID = "@آیدی_کانال_شما_یا_شناسه_عددی"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

media_queue = asyncio.Queue()
current_prefix = ""
interval_seconds = 60

class AdminStates(StatesGroup):
    waiting_for_prefix = State()
    waiting_for_interval = State()

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

@dp.message(Command("start", "panel"))
async def cmd_start(message: types.Message):
    welcome_text = (
        f"🤖 **به ربات مدیریت صف ارسال خوش آمدید!**\n\n"
        f"• هر نوع فایل، عکس، ویدیو یا سند (مثل wmv) را بفرستید تا به صف اضافه شود.\n"
        f"• پیشوند فعلی: `{current_prefix if current_prefix else 'تنظیم نشده'}`\n"
        f"• فاصله زمانی فعلی: `{interval_seconds} ثانیه`\n"
        f"• تعداد فایل‌های موجود در صف: `{media_queue.qsize()}`"
    )
    await message.answer(welcome_text, reply_markup=get_control_keyboard(), parse_mode="Markdown")

# ==================== هندلر اصلی + دیباگ ====================
@dp.message()
async def debug_and_handle_media(message: types.Message):
    logging.info("=" * 50)
    logging.info(f"پیام جدید دریافت شد از کاربر: {message.from_user.id}")
    logging.info(f"content_type = {message.content_type}")
    logging.info(f"دارای photo? {bool(message.photo)}")
    logging.info(f"دارای video? {bool(message.video)}")
    logging.info(f"دارای document? {bool(message.document)}")
    logging.info(f"دارای animation? {bool(message.animation)}")
    logging.info(f"دارای audio? {bool(message.audio)}")
    logging.info(f"دارای voice? {bool(message.voice)}")
    logging.info(f"دارای video_note? {bool(message.video_note)}")
    logging.info(f"کپشن: {message.caption}")
    if message.document:
        logging.info(f"نام فایل: {message.document.file_name}")
        logging.info(f"mime_type: {message.document.mime_type}")
        logging.info(f"file_size: {message.document.file_size}")
    logging.info("=" * 50)

    if message.content_type == "text":
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
        await message.reply("❌ نتوانستم فایل را شناسایی کنم.")
        return

    caption = message.caption or ""

    await media_queue.put({
        "type": media_type,
        "file_id": file_id,
        "caption": caption,
        "chat_id": message.chat.id,
        "message_id": message.message_id
    })

    await message.reply(
        f"✅ فایل به صف اضافه شد.\n"
        f"نوع: `{media_type}`\n"
        f"تعداد در صف: `{media_queue.qsize()}`",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.in_(["set_prefix", "set_interval", "queue_status", "clear_queue"]))
async def handle_callbacks(callback: types.CallbackQuery, state: FSMContext):
    global current_prefix, interval_seconds

    action = callback.data

    if action == "set_prefix":
        await callback.message.answer("لطفاً پیشوند جدیدی که می‌خواهید به تمام کپشن‌ها اضافه شود را بفرستید:")
        await state.set_state(AdminStates.waiting_for_prefix)
        await callback.answer()

    elif action == "set_interval":
        await callback.message.answer("⏱️ لطفاً فاصله زمانی ارسال فایل‌ها را بر حسب **ثانیه** وارد کنید:")
        await state.set_state(AdminStates.waiting_for_interval)
        await callback.answer()

    elif action == "queue_status":
        await callback.answer(f"تعداد فایل‌های باقی‌مانده در صف: {media_queue.qsize()}", show_alert=True)

    elif action == "clear_queue":
        while not media_queue.empty():
            try:
                media_queue.get_nowait()
                media_queue.task_done()
            except asyncio.QueueEmpty:
                break
        await callback.message.answer("🗑️ صف ارسال کاملاً پاک شد.", reply_markup=get_control_keyboard())
        await callback.answer()

@dp.message(AdminStates.waiting_for_prefix)
async def save_prefix(message: types.Message, state: FSMContext):
    global current_prefix
    current_prefix = message.text
    await state.clear()
    await message.answer(f"✅ پیشوند جدید ثبت شد:\n`{current_prefix}`", reply_markup=get_control_keyboard(), parse_mode="Markdown")

@dp.message(AdminStates.waiting_for_interval)
async def save_interval(message: types.Message, state: FSMContext):
    global interval_seconds
    try:
        val = int(message.text)
        if val < 10:
            await message.answer("❌ حداقل زمان مجاز ۱۰ ثانیه است.")
            return
        interval_seconds = val
        await state.clear()
        await message.answer(f"⏱️ فاصله زمانی تنظیم شد روی: `{interval_seconds} ثانیه`", reply_markup=get_control_keyboard(), parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ لطفاً فقط یک عدد صحیح وارد کنید.")

async def queue_worker():
    global interval_seconds, current_prefix
    while True:
        try:
            item = await media_queue.get()

            original_caption = item.get("caption", "")
            if current_prefix:
                final_caption = f"{current_prefix}\n\n{original_caption}" if original_caption else current_prefix
            else:
                final_caption = original_caption

            if item["type"] == "photo":
                await bot.send_photo(chat_id=CHANNEL_ID, photo=item["file_id"], caption=final_caption)
            elif item["type"] == "video":
                await bot.send_video(chat_id=CHANNEL_ID, video=item["file_id"], caption=final_caption)
            else:
                await bot.send_document(chat_id=CHANNEL_ID, document=item["file_id"], caption=final_caption)

            try:
                await bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
            except Exception as e:
                logging.warning(f"نتوانست پیام را حذف کند: {e}")

            media_queue.task_done()
            await asyncio.sleep(interval_seconds)

        except Exception as e:
            logging.error(f"خطا در worker: {e}")
            await asyncio.sleep(5)

async def main():
    asyncio.create_task(queue_worker())
    logging.info("ربات با حالت دیباگ شروع شد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
