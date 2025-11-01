import asyncio
from aiogram import types
from core import bot, dp, logger
from database import init_db
from handlers import router as handlers_router
from commands import router as commands_router

async def main():
    logger.info("🚀 Telegram moderatsiya boti ishga tushyabdi...")
    init_db()
    dp.include_router(handlers_router)
    dp.include_router(commands_router)
    # Bot commands ro'yxatini sozlash
    commands = [
        types.BotCommand(command="admins", description="Adminlarni ogohlantirish"),
        types.BotCommand(command="blocked_users", description="Blocklanganlar ro'yxati (admin)"),
        types.BotCommand(command="ban", description="Foydalanuvchini ban qilish (admin)"),
        types.BotCommand(command="warn", description="Foydalanuvchini ogohlantirish (admin)"),
        types.BotCommand(command="captcha", description="Foydalanuvchiga CAPTCHA yuborish (admin)"),
        types.BotCommand(command="admin_notification", description="Adminlarga shaxsiy xabar yuborish"),
        types.BotCommand(command="logs", description="Log faylini yuborish (admin)"),
    ]
    
    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Bot ishga tushmoqda!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot shu xatolik bilan to'xtadi: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
