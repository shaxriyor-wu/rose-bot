import asyncio
import re
from datetime import datetime, timedelta
from aiogram.enums import ChatType, ChatMemberStatus
from aiogram.types import ChatPermissions

from config import FORBIDDEN_WORDS, PUNISHMENT_DURATIONS, BLOCKED_MESSAGE_TEMPLATE, GROUP_NOTIFICATION_TEMPLATE, format_duration, format_until_time
from database import (
    get_violations_db,
    add_violation_db,
    clear_violations_db,
    add_captcha_user,
    is_captcha_user,
    remove_captcha_user,
    get_captcha_message_id,
)
from core import bot, logger


class ModerationBot:
    def __init__(self):
        self.forbidden_words = [word.lower() for word in FORBIDDEN_WORDS]
        self.admin_notifications = {}
        self.captcha_tasks = {}
        self._forbidden_patterns = []
        for w in self.forbidden_words:
            try:
                pattern = re.compile(rf"(?<!\\w){re.escape(w)}(?!\\w)", re.IGNORECASE)
                self._forbidden_patterns.append(pattern)
            except Exception:
                continue

    def contains_forbidden_word(self, text: str) -> bool:
        if not text:
            return False
        try:
            import unicodedata
            # Normalize unicode (NFKD) and strip diacritics
            nfkd = unicodedata.normalize("NFKD", (text or "")).lower()
            without_marks = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
        except Exception:
            without_marks = (text or "").lower()

        # Normalize common apostrophes/quotes and separators to spaces
        normalized = (
            without_marks
            .replace("’", " ")
            .replace("ʻ", " ")
            .replace("ʼ", " ")
            .replace("`", " ")
            .replace("·", " ")
            .replace("–", "-")
            .replace("—", "-")
        )

        # Collapse non-alphanumeric characters to spaces for token-boundary checks
        try:
            import re as _re
            collapsed = _re.sub(r"[^a-z0-9]+", " ", normalized)
        except Exception:
            collapsed = normalized

        # Fast path: simple substring over normalized text
        for w in self.forbidden_words:
            if w in normalized:
                return True

        # Token-aware exact word/prefix/suffix boundaries via regex patterns prepared in __init__
        for pat in self._forbidden_patterns:
            if pat.search(normalized) or pat.search(collapsed):
                return True

        # Last resort: token-by-token equality
        tokens = set(collapsed.split())
        if tokens:
            for w in self.forbidden_words:
                if w in tokens:
                    return True
        return False

    def find_forbidden_word(self, text: str) -> str | None:
        """Return the first matching forbidden token for diagnostics, else None."""
        if not text:
            return None
        try:
            import unicodedata
            nfkd = unicodedata.normalize("NFKD", (text or "")).lower()
            without_marks = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
        except Exception:
            without_marks = (text or "").lower()
        normalized = (
            without_marks
            .replace("’", " ")
            .replace("ʻ", " ")
            .replace("ʼ", " ")
            .replace("`", " ")
            .replace("·", " ")
            .replace("–", "-")
            .replace("—", "-")
        )
        try:
            import re as _re
            collapsed = _re.sub(r"[^a-z0-9]+", " ", normalized)
        except Exception:
            collapsed = normalized
        for w in self.forbidden_words:
            if w in normalized:
                return w
        for pat, w in zip(self._forbidden_patterns, self.forbidden_words):
            try:
                if pat.search(normalized) or pat.search(collapsed):
                    return w
            except Exception:
                continue
        tokens = set(collapsed.split())
        for w in self.forbidden_words:
            if w in tokens:
                return w
        return None

    def get_violation_count(self, user_id: int, group_id: int) -> tuple:
        return get_violations_db(user_id, group_id)

    def add_violation(self, user_id: int, group_id: int, group_title: str = None) -> tuple:
        add_violation_db(user_id, group_id, group_title)
        return get_violations_db(user_id, group_id)

    def get_punishment_duration(self, daily_count: int) -> int:
        if daily_count <= 4:
            return PUNISHMENT_DURATIONS[daily_count - 1]
        else:
            return 0

    async def restrict_user(self, chat_id: int, user_id: int, duration: int) -> bool:
        try:
            chat = await bot.get_chat(chat_id)
            if chat.type == ChatType.GROUP:
                await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                if duration > 0:
                    asyncio.create_task(self.unban_user_after_duration(chat_id, user_id, duration))
                return True
            else:
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
                until_date = datetime.now() + timedelta(seconds=duration)
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=permissions,
                    until_date=until_date
                )
                return True
        except Exception as e:
            logger.error(f"Failed to restrict user {user_id} in chat {chat_id}: {e}")
            return False

    async def ban_user(self, chat_id: int, user_id: int) -> bool:
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            clear_violations_db(user_id, chat_id)
            return True
        except Exception as e:
            logger.error(f"Failed to ban user {user_id} in chat {chat_id}: {e}")
            return False

    async def unban_user_after_duration(self, chat_id: int, user_id: int, duration: int) -> None:
        try:
            await asyncio.sleep(duration)
            await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            logger.info(f"Foydalanuvchi {user_id} guruh {chat_id} dan unban qilindi")
        except Exception as e:
            logger.error(f"Failed to unban user {user_id} in chat {chat_id}: {e}")

    async def send_private_warning(self, user_id: int, duration: int, daily_count: int) -> bool:
        try:
            message = BLOCKED_MESSAGE_TEMPLATE.format(
                duration=format_duration(duration) if duration else "doimiy",
                count=daily_count
            )
            await bot.send_message(chat_id=user_id, text=message)
            return True
        except Exception as e:
            logger.error(f"Failed to send warning to user {user_id}: {e}")
            return False

    async def send_group_notification(self, chat_id: int, user_id: int, user_name: str, duration: int, total_count: int, daily_count: int) -> None:
        try:
            message = GROUP_NOTIFICATION_TEMPLATE.format(
                user_name=user_name,
                user_id=user_id,
                duration=format_duration(duration) if duration else "doimiy",
                total_count=total_count,
                daily_count=daily_count,
                until_time=format_until_time(duration) if duration else "doimiy"
            )
            notification_msg = await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML"
            )
            self.admin_notifications[user_id] = {
                'message_id': notification_msg.message_id,
                'chat_id': chat_id,
                'duration': duration
            }
            if duration:
                asyncio.create_task(self.delete_group_notification_after_unblock(user_id, duration))
        except Exception as e:
            logger.error(f"Failed to send group notification: {e}")

    async def delete_group_notification_after_unblock(self, user_id: int, duration: int) -> None:
        try:
            await asyncio.sleep(duration)
            if user_id in self.admin_notifications:
                notification_data = self.admin_notifications[user_id]
                try:
                    await bot.delete_message(
                        chat_id=notification_data['chat_id'],
                        message_id=notification_data['message_id']
                    )
                except Exception as e:
                    logger.error(f"Failed to delete group notification for user {user_id}: {e}")
                del self.admin_notifications[user_id]
        except Exception as e:
            logger.error(f"Failed to delete group notification for user {user_id}: {e}")

    async def send_captcha(self, chat_id: int, user_id: int, user_name: str) -> None:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        try:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Men odamman", callback_data=f"captcha_{user_id}")]
                ]
            )
            message = (
                f"👋 Salom <a href='tg://user?id={user_id}'>{user_name}</a>!\n\n"
                f"🔐 Guruhga xush kelibsiz! Spam va botlardan himoya qilish uchun "
                f"quyidagi tugmani bosing va 30 daqiqa ichida tasdiqlang.\n\n"
                f"⏰ Vaqt: 30 daqiqa"
            )
            captcha_msg = await bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=keyboard
            )
            add_captcha_user(user_id, chat_id, captcha_msg.message_id)
            task = asyncio.create_task(self.captcha_timeout(chat_id, user_id, 1800))
            self.captcha_tasks[f"{user_id}_{chat_id}"] = task
        except Exception as e:
            logger.error(f"Failed to send CAPTCHA: {e}")

    async def captcha_timeout(self, chat_id: int, user_id: int, timeout: int) -> None:
        try:
            await asyncio.sleep(timeout)
            if is_captcha_user(user_id, chat_id):
                try:
                    await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"⏰ <a href='tg://user?id={user_id}'>Foydalanuvchi</a> CAPTCHA tekshiruvidan o'ta olmadi va guruhdan chiqarildi."
                    )
                except Exception as e:
                    logger.error(f"Failed to ban user after CAPTCHA timeout: {e}")
                remove_captcha_user(user_id, chat_id)
                task_key = f"{user_id}_{chat_id}"
                if task_key in self.captcha_tasks:
                    del self.captcha_tasks[task_key]
        except Exception as e:
            logger.error(f"CAPTCHA timeout error: {e}")

    async def verify_captcha(self, user_id: int, chat_id: int) -> bool:
        try:
            if is_captcha_user(user_id, chat_id):
                message_id = get_captcha_message_id(user_id, chat_id)
                if message_id:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except:
                        pass
                remove_captcha_user(user_id, chat_id)
                task_key = f"{user_id}_{chat_id}"
                if task_key in self.captcha_tasks:
                    self.captcha_tasks[task_key].cancel()
                    del self.captcha_tasks[task_key]
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ <a href='tg://user?id={user_id}'>Foydalanuvchi</a> CAPTCHA tekshiruvidan muvaffaqiyatli o'tdi!"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to verify CAPTCHA: {e}")
            return False

    async def is_admin(self, chat_id: int, user_id: int) -> bool:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            status = getattr(member, 'status', None)
            if isinstance(status, ChatMemberStatus):
                status_value = status.value
            else:
                status_value = str(status).lower() if status else ""
            return status_value in ["administrator", "creator", "owner"]
        except Exception:
            return False

    async def get_admins(self, chat_id: int) -> list:
        try:
            admins = []
            members = await bot.get_chat_administrators(chat_id)
            for member in members:
                status = getattr(member, 'status', None)
                if hasattr(status, 'value'):
                    status_value = status.value
                else:
                    status_value = str(status).lower() if status else ""
                if status_value in ["administrator", "creator", "owner"]:
                    admins.append(member.user.id)
            return admins
        except Exception:
            return []


moderation_bot = ModerationBot()

__all__ = ["moderation_bot", "ModerationBot"]


