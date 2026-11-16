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
BOT_TOKEN = "8971917249:AAGhpfWlnhQ9OYWkvSS9Qmd4AUBiVBrjk84"
ADMIN_IDS = [6405899841]  # آیدی عددی خودت

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

media_queue = asyncio.Queue()
current_prefix = ""
interval_seconds = 60
target_channel_id = None

class AdminStates(StatesGroup):
    waiting_for_prefix = State()
    waiting_for_interval = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_control_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(text="⚙️ تنظیم پیشوند", callback_data="set_prefix"),
            InlineKeyboardButton(text="⏱️ تنظیم فاصله", callback_data="set_interval")
        ],
        [
            InlineKeyboardButton(text="📊 وضعیت صف", callback_data="queue_status"),
            InlineKeyboardButton(text="🗑️ پاک کردن صف", callback_data="clear_queue")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_preview_keyboard(item_id: str):
    keyboard = [
        [
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"delete:{item_id}"),
            InlineKeyboardButton(text="🚀 ارسال فوری", callback_data=f"post_now:{item_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="شروع و پنل"),
        BotCommand(command="panel", description="پنل کنترل"),
        BotCommand(command="status", description="وضعیت صف"),
        BotCommand(command="help", description="راهنما"),
    ]
    await bot.set_my_commands(commands)

# ==================== وقتی ربات ادمین کانال می‌شود ====================
@dp.my_chat_member()
async def on_bot_status_changed(event: ChatMemberUpdated):
    global target_channel_id

    if event.chat.type != "channel":
        return

    if event.new_chat_member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        target_channel_id = event.chat.id
        logging.info(f"کانال تنظیم شد: {target_channel_id}")
        try:
            await bot.send_message(event.from_user.id, f"✅ ربات در کانال **{event.chat.title}** ادمین شد.", parse_mode="Markdown")
        except:
            pass
    elif event.new_chat_member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
        if target_channel_id == event.chat.id:
            target_channel_id = None

# ==================== دستورات ====================
@dp.message(Command("start", "panel"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی ندارید.")
        return

    channel_text = f"`{target_channel_id}`" if target_channel_id else "تنظیم نشده"
    text = (
        f"🤖 **پنل مدیریت صف**\n\n"
        f"• پیشوند: `{current_prefix or 'تنظیم نشده'}`\n"
        f"• فاصله زمانی: `{interval_seconds} ثانیه`\n"
        f"• کانال: {channel_text}\n"
        f"• تعداد در صف: `{media_queue.qsize()}`"
    )
    await message.answer(text, reply_markup=get_control_keyboard(), parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    channel_text = f"`{target_channel_id}`" if target_channel_id else "تنظیم نشده"
    await message.answer(f"📊 فایل در صف: `{media_queue.qsize()}`\nکانال: {channel_text}", parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("فایل یا متن بفرستید. ربات آن را پیش‌نمایش می‌کند و دکمه‌های حذف / ارسال فوری می‌گذارد.")

# ==================== دکمه‌های پنل ====================
@dp.callback_query(F.data.in_(["set_prefix", "set_interval", "queue_status", "clear_queue"]))
async def handle_panel_callbacks(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید", show_alert=True)
        return

    if callback.data == "set_prefix":
        await callback.message.answer("پیشوند جدید را بفرستید:")
        await state.set_state(AdminStates.waiting_for_prefix)
    elif callback.data == "set_interval":
        await callback.message.answer("فاصله زمانی (ثانیه - حداقل ۱۰):")
        await state.set_state(AdminStates.waiting_for_interval)
    elif callback.data == "queue_status":
        await callback.answer(f"تعداد در صف: {media_queue.qsize()}", show_alert=True)
    elif callback.data == "clear_queue":
        while not media_queue.empty():
            try:
                media_queue.get_nowait()
                media_queue.task_done()
            except:
                break
        await callback.message.answer("🗑️ صف پاک شد.", reply_markup=get_control_keyboard())
    await callback.answer()

@dp.message(AdminStates.waiting_for_prefix)
async def save_prefix(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global current_prefix
    current_prefix = message.text.strip()
    await state.clear()
    await message.answer(f"✅ پیشوند ثبت شد:\n`{current_prefix}`", reply_markup=get_control_keyboard(), parse_mode="Markdown")

@dp.message(AdminStates.waiting_for_interval)
async def save_interval(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global interval_seconds
    try:
        val = int(message.text.strip())
        if val < 10:
            await message.answer("❌ حداقل ۱۰ ثانیه.")
            return
        interval_seconds = val
        await state.clear()
        await message.answer(f"⏱️ فاصله زمانی: `{interval_seconds} ثانیه`", reply_markup=get_control_keyboard(), parse_mode="Markdown")
    except:
        await message.answer("❌ فقط عدد وارد کنید.")

# ==================== دریافت فایل و متن + پیش‌نمایش ====================
@dp.message(F.content_type.in_({"photo", "video", "document", "animation", "audio", "voice", "video_note", "text"}))
async def handle_content(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی ندارید.")
        return

    if target_channel_id is None:
        await message.reply("❌ ابتدا ربات را ادمین کانال کنید.")
        return

    if message.content_type == "text" and message.text.startswith("/"):
        return

    # پاک کردن پیام اصلی کاربر
    try:
        await message.delete()
    except:
        pass

    item_id = str(message.message_id)
    prefix = current_prefix

    # ساخت پیش‌نمایش و ارسال مجدد
    if message.content_type == "text":
        text = message.text
        final_text = f"{prefix}\n\n{text}" if prefix else text
        preview = await message.answer(
            final_text,
            reply_markup=get_preview_keyboard(item_id)
        )
        queue_item = {
            "type": "text",
            "text": text,
            "prefix": prefix,
            "chat_id": message.chat.id,
            "preview_message_id": preview.message_id,
            "item_id": item_id
        }
    else:
        file_id = None
        media_type = "document"
        caption = message.caption or ""

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

        final_caption = f"{prefix}\n\n{caption}" if prefix and caption else (prefix or caption)

        if media_type == "photo":
            preview = await message.answer_photo(file_id, caption=final_caption, reply_markup=get_preview_keyboard(item_id))
        elif media_type == "video":
            preview = await message.answer_video(file_id, caption=final_caption, reply_markup=get_preview_keyboard(item_id))
        else:
            preview = await message.answer_document(file_id, caption=final_caption, reply_markup=get_preview_keyboard(item_id))

        queue_item = {
            "type": media_type,
            "file_id": file_id,
            "caption": caption,
            "prefix": prefix,
            "chat_id": message.chat.id,
            "preview_message_id": preview.message_id,
            "item_id": item_id
        }

    await media_queue.put(queue_item)

# ==================== دکمه‌های پیش‌نمایش ====================
@dp.callback_query(F.data.startswith("delete:"))
async def delete_preview(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید", show_alert=True)
        return

    try:
        await callback.message.delete()
        await callback.answer("حذف شد")
    except:
        await callback.answer("خطا در حذف", show_alert=True)

@dp.callback_query(F.data.startswith("post_now:"))
async def post_now(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید", show_alert=True)
        return

    if target_channel_id is None:
        await callback.answer("کانال تنظیم نشده", show_alert=True)
        return

    # پیدا کردن آیتم در صف (ساده شده - در نسخه پیشرفته‌تر می‌توان دیکشنری جدا نگه داشت)
    await callback.answer("در حال ارسال...")
    # برای سادگی، پیام فعلی را مستقیم ارسال می‌کنیم
    try:
        if callback.message.photo:
            await bot.send_photo(target_channel_id, callback.message.photo[-1].file_id, caption=callback.message.caption)
        elif callback.message.video:
            await bot.send_video(target_channel_id, callback.message.video.file_id, caption=callback.message.caption)
        elif callback.message.document:
            await bot.send_document(target_channel_id, callback.message.document.file_id, caption=callback.message.caption)
        elif callback.message.text:
            await bot.send_message(target_channel_id, callback.message.text)
        
        await callback.message.delete()
        await callback.answer("ارسال شد ✅")
    except Exception as e:
        await callback.answer(f"خطا: {e}", show_alert=True)

# ==================== Worker ====================
async def queue_worker():
    global interval_seconds, target_channel_id

    while True:
        try:
            item = await media_queue.get()

            if target_channel_id is None:
                media_queue.task_done()
                continue

            prefix = item.get("prefix", "")
            item_type = item["type"]

            if item_type == "text":
                text = item.get("text", "")
                final_text = f"{prefix}\n\n{text}" if prefix else text
                await bot.send_message(target_channel_id, final_text)
            else:
                caption = item.get("caption", "")
                final_caption = f"{prefix}\n\n{caption}" if prefix and caption else (prefix or caption)

                if item_type == "photo":
                    await bot.send_photo(target_channel_id, item["file_id"], caption=final_caption)
                elif item_type == "video":
                    await bot.send_video(target_channel_id, item["file_id"], caption=final_caption)
                else:
                    await bot.send_document(target_channel_id, item["file_id"], caption=final_caption)

            # پاک کردن پیام پیش‌نمایش
            try:
                await bot.delete_message(item["chat_id"], item["preview_message_id"])
            except:
                pass

            media_queue.task_done()
            await asyncio.sleep(interval_seconds)

        except Exception as e:
            logging.error(f"خطا در worker: {e}")
            await asyncio.sleep(5)

async def main():
    await set_bot_commands()
    asyncio.create_task(queue_worker())
    logging.info("ربات آماده است...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
