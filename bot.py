import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# تنظیمات اولیه (توکن ربات و آیدی کانال مقصد را اینجا وارد کنید)
BOT_TOKEN = "8971917249:AAHdb_9RzkbkbZlPelsbjlb2CSXkRzhESUM"
CHANNEL_ID = "-1004331075101"

# پیکربندی لاگ‌ها
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# متغیرهای سراسری برای صف و تنظیمات
media_queue = asyncio.Queue()
current_prefix = ""
interval_seconds = 60  # پیش‌فرض: ۶۰ ثانیه

# حالت‌های FSM برای دریافت پیشوند یا زمان از کاربر
class AdminStates(StatesGroup):
    waiting_for_prefix = State()
    waiting_for_interval = State()

# دکمه‌های پنل کنترل ربات
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

# دستور شروع و نمایش پنل
@dp.message(Command("start", "panel"))
async def cmd_start(message: types.Message):
    welcome_text = (
        f"🤖 **به ربات مدیریت صف ارسال خوش آمدید!**\n\n"
        f"• عکس، ویدیو یا فایل‌های خود (مثل wmv) را بفرستید تا به صف اضافه شوند.\n"
        f"• پیشوند فعلی: `{current_prefix if current_prefix else 'تنظیم نشده'}`\n"
        f"• فاصله زمانی فعلی: `{interval_seconds} ثانیه`\n"
        f"• تعداد فایل‌های موجود در صف: `{media_queue.qsize()}`"
    )
    await message.answer(welcome_text, reply_markup=get_control_keyboard(), parse_mode="Markdown")

# دریافت عکس و افزودن به صف
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    await media_queue.put({
        "type": "photo", 
        "file_id": file_id, 
        "caption": caption,
        "chat_id": message.chat.id,
        "message_id": message.message_id
    })
    await message.reply(f"✅ عکس به صف اضافه شد. (تعداد در صف: {media_queue.qsize()})")

# دریافت ویدیو یا اسناد (شامل فرمت‌های ویدیویی مثل wmv که به عنوان فایل ارسال می‌شوند)
@dp.message(F.video | F.document)
async def handle_media(message: types.Message):
    file_id = None
    media_type = "video"
    
    if message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.document:
        file_id = message.document.file_id
        media_type = "document"
    
    if not file_id:
        return

    caption = message.caption or ""
    
    await media_queue.put({
        "type": media_type, 
        "file_id": file_id, 
        "caption": caption,
        "chat_id": message.chat.id,
        "message_id": message.message_id
    })
    
    await message.reply(f"✅ فایل/ویدیو به صف اضافه شد. (تعداد در صف: {media_queue.qsize()})")

# مدیریت کلیک دکمه‌های شیشه‌ای (Inline)
@dp.callback_query(F.data.in_(["set_prefix", "set_interval", "queue_status", "clear_queue"]))
async def handle_callbacks(callback: types.CallbackQuery, state: FSMContext):
    global current_prefix, interval_seconds, media_queue
    action = callback.data

    if action == "set_prefix":
        await callback.message.answer("لطفاً پیشوند جدیدی که می‌خواهید به تمام کپشن‌ها اضافه شود را بفرستید:")
        await state.set_state(AdminStates.waiting_for_prefix)
        await callback.answer()

    elif action == "set_interval":
        await callback.message.answer("⏱️ لطفاً فاصله زمانی ارسال فایل‌ها را بر حسب **ثانیه** وارد کنید:\n(مثلاً برای ۱۰ ثانیه بنویسید `10` و برای ۱ ساعت بنویسید `3600`)")
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
        await callback.message.answer("🗑️ صف ارسال کاملاً پاک شد و تمامی فایل‌ها لغو شدند.", reply_markup=get_control_keyboard())
        await callback.answer()

# دریافت متون مربوط به تنظیم پیشوند
@dp.message(AdminStates.waiting_for_prefix)
async def save_prefix(message: types.Message, state: FSMContext):
    global current_prefix
    current_prefix = message.text
    await state.clear()
    await message.answer(f"✅ پیشوند جدید با موفقیت ثبت شد:\n`{current_prefix}`", reply_markup=get_control_keyboard(), parse_mode="Markdown")

# دریافت متون مربوط به تنظیم زمان
@dp.message(AdminStates.waiting_for_interval)
async def save_interval(message: types.Message, state: FSMContext):
    global interval_seconds
    try:
        val = int(message.text)
        if val < 10:
            await message.answer("❌ حداقل زمان مجاز ۱۰ ثانیه است. لطفاً عدد بزرگتری وارد کنید:")
            return
        if val > 86400:
            await message.answer("❌ حداکثر زمان مجاز ۸۶۴۰۰ ثانیه (۲۴ ساعت) است. لطفاً عدد کوچکتری وارد کنید:")
            return
        
        interval_seconds = val
        await state.clear()
        await message.answer(f"⏱️ فاصله زمانی جدید تنظیم شد روی: `{interval_seconds} ثانیه`", reply_markup=get_control_keyboard(), parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ لطفاً فقط یک عدد صحیح (ثانیه) وارد کنید:")

# تسک پس‌زمینه برای ارسال خودکار فایل‌ها به کانال و حذف از چت ربات
async def queue_worker():
    global interval_seconds, current_prefix
    while True:
        try:
            item = await media_queue.get()
            
            original_caption = item["caption"]
            if current_prefix:
                final_caption = f"{current_prefix}\n\n{original_caption}" if original_caption else current_prefix
            else:
                final_caption = original_caption

            # ارسال بر اساس نوع فایل ذخیره شده در صف
            if item["type"] == "photo":
                await bot.send_photo(chat_id=CHANNEL_ID, photo=item["file_id"], caption=final_caption)
            elif item["type"] == "video":
                await bot.send_video(chat_id=CHANNEL_ID, video=item["file_id"], caption=final_caption)
            elif item["type"] == "document":
                await bot.send_document(chat_id=CHANNEL_ID, document=item["file_id"], caption=final_caption)

            try:
                await bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
            except Exception as del_err:
                logging.warning(f"امکان حذف پیام وجود نداشت: {del_err}")

            media_queue.task_done()
            await asyncio.sleep(interval_seconds)

        except Exception as e:
            logging.error(f"خطا در پردازش صف ارسال: {e}")
            await asyncio.sleep(5)

async def main():
    asyncio.create_task(queue_worker())
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
