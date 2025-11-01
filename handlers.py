from datetime import datetime
from aiogram import F
from aiogram.enums import ChatType
from aiogram.types import Message, ChatMemberUpdated, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router
from aiogram.filters import CommandStart

from core import bot, logger
from database import init_group_table, group_table_exists
from moderation import moderation_bot
from logs import log_delete_failure

router = Router()


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def handle_start(message: Message):
    add_group_url = f"https://t.me/{(await bot.me()).username}?startgroup=new"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=add_group_url)]]
    )
    await message.answer(
        "Bu bot faqat guruhlarda ishlaydi. Meni guruhga qo‘shing.",
        reply_markup=keyboard,
    )


@router.message(F.text.startswith("/"))
async def _debug_command_logger(message: Message):
    try:
        logger.info(
            "Incoming command: %r from user %s in chat %s (type=%s)",
            message.text,
            getattr(message.from_user, "id", None),
            getattr(message.chat, "id", None),
            getattr(message.chat, "type", None),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("captcha_"))
async def handle_captcha_callback(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    chat_id = callback.message.chat.id
    if callback.from_user.id != user_id:
        await callback.answer("Bu tugma sizga tegishli emas!", show_alert=True)
        return
    if await moderation_bot.verify_captcha(user_id, chat_id):
        await callback.answer("✅ CAPTCHA muvaffaqiyatli tasdiqlandi!")
    else:
        await callback.answer("❌ CAPTCHA topilmadi!", show_alert=True)


@router.message(~F.text.startswith("/"))
async def handle_all_messages(message: Message):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    if group_table_exists(chat_id) is False and message.chat.title:
        init_group_table(chat_id, message.chat.title)
    # Skip commands (in case of entities like via clients sending rich entities)
    try:
        if message.entities:
            for ent in message.entities:
                if ent.type == "bot_command":
                    return
    except Exception:
        pass
    content = message.text or message.caption or ""
    if not content:
        return
    matched = moderation_bot.find_forbidden_word(content)
    if matched:
        chat_title = message.chat.title or f"Chat {chat_id}"
        user_name = message.from_user.full_name or message.from_user.username or f"User {user_id}"
        if not group_table_exists(chat_id):
            init_group_table(chat_id, chat_title)
        total_count, daily_count, _ = moderation_bot.add_violation(user_id, chat_id, chat_title)
        logger.info(f"Qoida buzish: User {user_id}, So'z: {matched}, Total: {total_count}, Daily: {daily_count}")
        await moderation_bot.send_group_notification(chat_id, user_id, user_name, 0, total_count, daily_count)
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Habar o'chirishda xatolik: {e}")
            try:
                log_delete_failure(logger, chat_id=chat_id, message_id=message.message_id, user_id=user_id, reason=str(e))
            except Exception:
                pass
        if daily_count >= 5:
            await moderation_bot.ban_user(chat_id, user_id)
            await moderation_bot.send_private_warning(user_id, 0, daily_count)
            return
        duration = moderation_bot.get_punishment_duration(daily_count)
        if duration > 0:
            if await moderation_bot.restrict_user(chat_id, user_id, duration):
                await moderation_bot.send_private_warning(user_id, duration, daily_count)


@router.chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    if event.new_chat_member.user.id == (await bot.me()).id and event.new_chat_member.status in ("administrator", "member"):
        group_id = event.chat.id
        group_title = event.chat.title or f"Group {group_id}"
        init_group_table(group_id, group_title)
        logger.info(f"✅ Bot yangi guruhga qo'shildi: {group_title} ({group_id})")


@router.chat_member()
async def on_new_member(event: ChatMemberUpdated):
    if (
        event.new_chat_member.status == "member"
        and event.old_chat_member.status in ["left", "kicked", None]
        and event.new_chat_member.user.id != (await bot.me()).id
    ):
        user_id = event.new_chat_member.user.id
        chat_id = event.chat.id
        user_name = event.new_chat_member.user.full_name or event.new_chat_member.user.username or f"User {user_id}"
        await moderation_bot.send_captcha(chat_id, user_id, user_name)

__all__ = ["router"]


