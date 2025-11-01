import sqlite3
import os
import re
from datetime import datetime, timedelta

# Bitta database faylida har bir guruh uchun alohida table
DB_PATH = "violations.db"

def sanitize_table_name(name: str) -> str:
    """Guruh nomini SQL table nomi uchun xavfsiz qiladi"""
    # Faqat harflar, raqamlar va pastki chiziq qoldirish
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Raqam bilan boshlanmasligi kerak
    if name and name[0].isdigit():
        name = f"group_{name}"
    # Bo'sh bo'lmasligi kerak
    if not name:
        name = "unknown_group"
    return name[:50]  # Uzunlikni cheklash

def init_db():
    """Asosiy database faylini yaratadi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    # Guruhlar ro'yxatini saqlash uchun table
    c.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_title TEXT,
            table_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # CAPTCHA uchun table
    c.execute("""
        CREATE TABLE IF NOT EXISTS captcha_users (
            user_id INTEGER,
            group_id INTEGER,
            message_id INTEGER,
            captcha_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, group_id)
        )
    """)
    
    # Blocklangan foydalanuvchilar uchun table
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id INTEGER,
            group_id INTEGER,
            blocked_by INTEGER,
            block_reason TEXT,
            blocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, group_id)
        )
    """)
    
    conn.commit()
    conn.close()

def init_group_table(group_id: int, group_title: str = None):
    """Yangi guruh uchun alohida table yaratadi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    
    # Guruh nomini xavfsiz qilish
    if not group_title:
        group_title = f"Group_{abs(group_id)}"
    
    table_name = sanitize_table_name(group_title)
    
    # Guruhni groups table ga qo'shish
    c.execute("INSERT OR REPLACE INTO groups (group_id, group_title, table_name) VALUES (?, ?, ?)", 
              (group_id, group_title, table_name))
    
    # Guruh uchun alohida table yaratish
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            user_id INTEGER PRIMARY KEY UNIQUE,
            total_count INTEGER DEFAULT 0,
            daily_count INTEGER DEFAULT 0,
            last_violation DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_daily_reset DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print(f"✅ Guruh '{group_title}' ({group_id}) uchun yangi table yaratildi: {table_name}")
    return table_name

def add_violation_db(user_id: int, group_id: int, group_title: str = None):
    """Foydalanuvchiga qoida buzish qo'shadi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    
    # Guruh table nomini topish
    c.execute("SELECT table_name FROM groups WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    
    if not result:
        # Agar table mavjud bo'lmasa, yaratish
        table_name = init_group_table(group_id, group_title)
    else:
        table_name = result[0]
    
    # 24 soat ichida qoida buzish hisobini tekshirish
    c.execute(f'SELECT daily_count, last_daily_reset FROM "{table_name}" WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    
    now = datetime.now()
    if row:
        last_reset = datetime.fromisoformat(row[1]) if row[1] else now
        # Agar 24 soat o'tgan bo'lsa, daily_count ni nolga tushirish
        if now - last_reset >= timedelta(hours=24):
            c.execute(f'UPDATE "{table_name}" SET daily_count = 1, total_count = total_count + 1, last_violation = CURRENT_TIMESTAMP, last_daily_reset = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        else:
            c.execute(f'UPDATE "{table_name}" SET daily_count = daily_count + 1, total_count = total_count + 1, last_violation = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
    else:
        c.execute(f'INSERT INTO "{table_name}" (user_id, total_count, daily_count, last_violation, last_daily_reset) VALUES (?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)', (user_id,))
    
    conn.commit()
    conn.close()

def get_violations_db(user_id: int, group_id: int):
    """Foydalanuvchining qoida buzishlar sonini qaytaradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    
    # Guruh table nomini topish
    c.execute("SELECT table_name FROM groups WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    
    if not result:
        return 0, 0, None
    
    table_name = result[0]
    c.execute(f'SELECT total_count, daily_count, last_violation FROM "{table_name}" WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return row[0], row[1], row[2]  # total_count, daily_count, last_violation
    else:
        return 0, 0, None

def clear_violations_db(user_id: int, group_id: int):
    """Foydalanuvchining barcha qoida buzishlarini o'chiradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    
    # Guruh table nomini topish
    c.execute("SELECT table_name FROM groups WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    
    if result:
        table_name = result[0]
        c.execute(f'DELETE FROM "{table_name}" WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

def group_table_exists(group_id: int) -> bool:
    """Guruh table mavjudligini tekshiradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("SELECT table_name FROM groups WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_group_stats(group_id: int):
    """Guruh statistikalarini qaytaradi"""
    if not group_table_exists(group_id):
        return 0, 0
    
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    
    # Guruh table nomini topish
    c.execute("SELECT table_name FROM groups WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    
    if not result:
        return 0, 0
    
    table_name = result[0]
    
    # Jami foydalanuvchilar soni
    c.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    total_users = c.fetchone()[0]
    
    # Jami qoida buzishlar soni
    c.execute(f'SELECT SUM(total_count) FROM "{table_name}"')
    total_violations = c.fetchone()[0] or 0
    
    conn.close()
    return total_users, total_violations

# CAPTCHA funksiyalari
def add_captcha_user(user_id: int, group_id: int, message_id: int):
    """CAPTCHA foydalanuvchisini qo'shadi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO captcha_users (user_id, group_id, message_id) VALUES (?, ?, ?)", 
              (user_id, group_id, message_id))
    conn.commit()
    conn.close()

def remove_captcha_user(user_id: int, group_id: int):
    """CAPTCHA foydalanuvchisini olib tashlaydi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("DELETE FROM captcha_users WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    conn.commit()
    conn.close()

def is_captcha_user(user_id: int, group_id: int) -> bool:
    """Foydalanuvchi CAPTCHA holatida ekanligini tekshiradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("SELECT 1 FROM captcha_users WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_captcha_message_id(user_id: int, group_id: int) -> int:
    """CAPTCHA xabar ID sini qaytaradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("SELECT message_id FROM captcha_users WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# Blocklangan foydalanuvchilar funksiyalari
def add_blocked_user(user_id: int, group_id: int, blocked_by: int, reason: str = ""):
    """Blocklangan foydalanuvchini qo'shadi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO blocked_users (user_id, group_id, blocked_by, block_reason) VALUES (?, ?, ?, ?)", 
              (user_id, group_id, blocked_by, reason))
    conn.commit()
    conn.close()

def get_blocked_users(group_id: int) -> list:
    """Guruhdagi blocklangan foydalanuvchilarni qaytaradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("SELECT user_id, blocked_by, block_reason, blocked_at FROM blocked_users WHERE group_id = ?", (group_id,))
    result = c.fetchall()
    conn.close()
    return result

def is_user_blocked(user_id: int, group_id: int) -> bool:
    """Foydalanuvchi blocklangan ekanligini tekshiradi"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    c = conn.cursor()
    c.execute("SELECT 1 FROM blocked_users WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    result = c.fetchone()
    conn.close()
    return result is not None

# Eski funksiyalar - orqaga muvofiqlik uchun
def create_group_table(group_id: int):
    """Eski tizim bilan muvofiqlik uchun"""
    init_group_table(group_id)