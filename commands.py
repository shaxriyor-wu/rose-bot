from datetime import datetime
from aiogram import F
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.input_file import FSInputFile
from aiogram import Router

from core import bot, logger
from database import get_blocked_users, add_blocked_user
from moderation import moderation_bot

router = Router()


@router.message(Command("admins"))
async def handle_admins_command(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply("Bu command faqat guruhlarda ishlaydi!")
        return
    admins = await moderation_bot.get_admins(chat_id)
    if not admins:
        await message.reply("Guruhda adminlar topilmadi!")
        return
    for admin_id in admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    "🔔 <b>Ogohlantirish!</b>\n\n"
                    f"Guruh: <b>{message.chat.title}</b>\n"
                    f"Foydalanuvchi: <a href='tg://user?id={user_id}'>{message.from_user.full_name or message.from_user.username}</a>\n"
                    f"Vaqt: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"Sizni guruhda belgilashdi!"
                ),
            )
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")
    await message.reply("✅ Barcha adminlarga ogohlantirish yuborildi!")


@router.message(Command(commands=["blocklists", "blocked_users"]))
async def handle_blocklists_command(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await moderation_bot.is_admin(chat_id, user_id):
        await message.reply("❌ Siz bu xizmatdan foydalana olmaysiz!")
        return
    blocked_users = get_blocked_users(chat_id)
    if not blocked_users:
        await message.reply("📋 Guruhda blocklangan foydalanuvchilar yo'q!")
        return
    text = f"📋 <b>Blocklangan foydalanuvchilar ro'yxati</b>\n"
    text += f"Guruh: <b>{message.chat.title}</b>\n\n"
    for user_id_blocked, blocked_by, reason, blocked_at in blocked_users:
        try:
            user_info = await bot.get_chat_member(chat_id, user_id_blocked)
            user_name = user_info.user.full_name or user_info.user.username or f"User {user_id_blocked}"
            text += f"👤 <a href='tg://user?id={user_id_blocked}'>{user_name}</a>\n"
            text += f"   🚫 Sabab: {reason or 'Ko\'rsatilmagan'}\n"
            text += f"   📅 Vaqt: {blocked_at}\n\n"
        except:
            text += f"👤 User {user_id_blocked}\n"
            text += f"   🚫 Sabab: {reason or 'Ko\'rsatilmagan'}\n"
            text += f"   📅 Vaqt: {blocked_at}\n\n"
    try:
        await bot.send_message(chat_id=user_id, text=text)
        await message.reply("✅ Blocklanganlar ro'yxati shaxsiy xabarga yuborildi!")
    except Exception:
        await message.reply("❌ Shaxsiy xabar yuborishda xatolik!")


@router.message(Command("ban"))
async def handle_ban_command(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    logger.info("/ban invoked by user=%s in chat=%s | is_reply=%s", user_id, chat_id, bool(message.reply_to_message))
    if not await moderation_bot.is_admin(chat_id, user_id):
        await message.reply("❌ Siz bu xizmatdan foydalana olmaysiz!")
        return
    # Resolve target: prefer reply, then text_mention, then numeric id arg
    target_user_id = None
    target_user_name = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_user_name = (
            message.reply_to_message.from_user.full_name
            or message.reply_to_message.from_user.username
            or f"User {target_user_id}"
        )
    else:
        # Try text_mention entity
        try:
            if message.entities:
                for ent in message.entities:
                    if ent.type == "text_mention" and getattr(ent, "user", None):
                        target_user_id = ent.user.id
                        target_user_name = ent.user.full_name or ent.user.username or f"User {target_user_id}"
                        break
        except Exception:
            pass
        # Try numeric id argument
        if target_user_id is None:
            try:
                parts = (message.text or "").strip().split()
                if len(parts) > 1 and parts[1].isdigit():
                    target_user_id = int(parts[1])
                    target_user_name = f"User {target_user_id}"
            except Exception:
                pass
    logger.info("/ban target resolution | reply_user_id=%s", target_user_id)
    if target_user_id is None:
        await message.reply("❌ Ban qilish uchun foydalanuvchi xabariga reply qiling yoki user ID yuboring: /ban <user_id>.")
        return
    if target_user_id == user_id:
        await message.reply("❌ O'zingizni ban qila olmaysiz!")
        return
    if target_user_id == (await bot.me()).id:
        await message.reply("❌ Botni ban qila olmaysiz!")
        return
    try:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=target_user_id)
            status = getattr(member, 'status', None)
            status_value = status.value if hasattr(status, 'value') else str(status).lower()
            if status_value in ['left', 'kicked']:
                await message.reply("❌ Bu foydalanuvchi allaqachon guruhda yo'q!")
                return
            if status_value in ['administrator', 'creator']:
                await message.reply("❌ Admin yoki egani ban qilib bo'lmaydi!")
                return
        except:
            await message.reply("❌ Foydalanuvchi topilmadi!")
            return
        logger.info("/ban executing ban for target=%s in chat=%s", target_user_id, chat_id)
        await bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
        add_blocked_user(target_user_id, chat_id, user_id, "Admin tomonidan ban qilindi")
        await message.reply(f"✅ <a href='tg://user?id={target_user_id}'>{target_user_name}</a> guruhdan chiqarildi!")
    except Exception as e:
        logger.error(f"Ban error: {e}")
        await message.reply(f"❌ Ban qilishda xatolik: {str(e)}")


@router.message(Command("warn"))
async def handle_warn_command(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await moderation_bot.is_admin(chat_id, user_id):
        await message.reply("❌ Siz bu xizmatdan foydalana olmaysiz!")
        return
    if message.text and len(message.text.strip().split()) > 1:
        await message.reply("❌ Faqat '/warn' ni ishlating, parametrsiz. Foydalanuvchi xabariga reply qiling.")
        return
    if not message.reply_to_message:
        await message.reply("❌ Ogohlantirish uchun foydalanuvchi xabariga reply qiling!")
        return
    target_user_id = message.reply_to_message.from_user.id
    target_user_name = message.reply_to_message.from_user.full_name or message.reply_to_message.from_user.username or f"User {target_user_id}"
    try:
        await message.reply_to_message.delete()
        await message.reply(f"⚠️ <a href='tg://user?id={target_user_id}'>{target_user_name}</a> ogohlantirildi!\n\nBunday habar yozish mumkin emas!")
    except Exception:
        await message.reply("❌ Ogohlantirishda xatolik!")


@router.message(Command("captcha"))
async def handle_captcha_command(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await moderation_bot.is_admin(chat_id, user_id):
        await message.reply("❌ Siz bu xizmatdan foydalana olmaysiz!")
        return
    if message.text and len(message.text.strip().split()) > 1:
        await message.reply("❌ Faqat '/captcha' ni ishlating, parametrsiz. Foydalanuvchi xabariga reply qiling.")
        return
    if not message.reply_to_message:
        await message.reply("❌ CAPTCHA uchun foydalanuvchi xabariga reply qiling!")
        return
    target_user_id = message.reply_to_message.from_user.id
    target_user_name = message.reply_to_message.from_user.full_name or message.reply_to_message.from_user.username or f"User {target_user_id}"
    if target_user_id == (await bot.me()).id:
        await message.reply("❌ Botga CAPTCHA yuborib bo'lmaydi!")
        return
    if target_user_id == user_id:
        await message.reply("❌ O'zingizga CAPTCHA yubora olmaysiz!")
        return
    try:
        await moderation_bot.send_captcha(chat_id, target_user_id, target_user_name)
        await message.reply("✅ CAPTCHA yuborildi!")
    except Exception as e:
        logger.error(f"Captcha command error: {e}")
        await message.reply("❌ CAPTCHA yuborishda xatolik")


@router.message(Command("admin_notification"))
async def handle_admin_notification(message: Message):
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply("Bu command faqat guruhlarda ishlaydi!")
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    chat_title = message.chat.title or f"Group {chat_id}"
    if message.text and len(message.text.strip().split()) > 1:
        await message.reply("❌ Faqat '/admin_notification' ni parametrsiz yuboring.")
        return
    admins = await moderation_bot.get_admins(chat_id)
    if not admins:
        await message.reply("Guruhda adminlar topilmadi!")
        return
    link = None
    try:
        if getattr(message.chat, 'username', None):
            link = f"https://t.me/{message.chat.username}/{message.message_id}"
        elif str(chat_id).startswith("-100"):
            link = f"https://t.me/c/{str(chat_id)[4:]}/{message.message_id}"
    except Exception:
        link = None
    kb = None
    if link:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Xabarni ochish", url=link)]])
    sender_name = message.from_user.full_name or message.from_user.username or f"User {user_id}"
    text = (
        "🔔 <b>Adminlarga ogohlantirish</b>\n\n"
        f"Guruh: <b>{chat_title}</b>\n"
        f"Foydalanuvchi: <a href='tg://user?id={user_id}'>{sender_name}</a>\n"
        f"Xabar ID: <code>{message.message_id}</code>\n"
    )
    if not link:
        text += "\nℹ️ Guruhda xabar topildi, lekin to'g'ridan-to'g'ri link mavjud emas."
    ok = 0
    for admin_id in admins:
        try:
            await bot.send_message(chat_id=admin_id, text=text, reply_markup=kb)
            ok += 1
        except Exception as e:
            logger.warning(f"Admin DM failed for {admin_id}: {e}")
            continue
    await message.reply("✅ Adminlarga xabar yuborildi!" if ok else "❌ Hech bir adminga xabar yuborilmadi.")


@router.message(Command("logs"))
async def handle_logs_command(message: Message):
    """Admin-only: send the rotating log file as a document."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await moderation_bot.is_admin(chat_id, user_id):
        await message.reply("❌ Siz bu xizmatdan foydalana olmaysiz!")
        return
    try:
        from logs import LOG_FILE_PATH
        file = FSInputFile(LOG_FILE_PATH)
        # Prefer sending to the admin privately
        await bot.send_document(user_id, file, caption="📄 Bot logs")
        await message.reply("✅ Log fayli shaxsiy xabarga yuborildi!")
    except Exception as e:
        await message.reply(f"❌ Log yuborishda xatolik: {e}")


@router.message(Command("diag"))
async def handle_diag_command(message: Message):
    chat = message.chat
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply("Bu command faqat guruhda ishlaydi!")
        return
    try:
        me = await bot.me()
        member = await bot.get_chat_member(chat_id=chat.id, user_id=me.id)
        status = getattr(member, 'status', None)
        status_value = status.value if hasattr(status, 'value') else str(status)
        perms = getattr(member, 'can_manage_chat', None)
        # Collect key permissions if available
        fields = [
            ('status', status_value),
            ('can_delete_messages', getattr(member, 'can_delete_messages', None)),
            ('can_restrict_members', getattr(member, 'can_restrict_members', None)),
            ('can_manage_chat', getattr(member, 'can_manage_chat', None)),
            ('can_manage_topics', getattr(member, 'can_manage_topics', None)),
            ('can_invite_users', getattr(member, 'can_invite_users', None)),
        ]
        text = "🧪 Bot diag\n\n" + "\n".join(
            f"- {k}: <code>{v}</code>" for k, v in fields
        )
        await message.reply(text)
    except Exception as e:
        logger.error(f"Diag error: {e}")
        await message.reply(f"❌ Diag xatolik: {e}")

__all__ = ["router"]


