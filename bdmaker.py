"""Скрипт для создания тестовых баз (SQLite и MS SQL Server)."""
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

print("⏳ Генерируем 10 000 тестовых строк...")
df = pd.DataFrame({
    "id": range(1, 10001),
    "name": [f"User_{i}" for i in range(1, 10001)],
    "age": [i % 80 + 18 for i in range(1, 10001)],
    "email": [f"user{i}@example.com" for i in range(1, 10001)]
})

# ==========================================
# 1. SQLite
# ==========================================
print("📦 Создаем SQLite (source.db)...")
sqlite_engine = create_engine("sqlite:///source.db")
df.to_sql("users", sqlite_engine, if_exists="replace", index=False)
print("✅ SQLite готов! (файл source.db)")

# ==========================================
# 2. Microsoft SQL Server (Windows Authentication)
# ==========================================
# ВАЖНО: Указываем точное имя экземпляра из твоего SSMS
DB_HOST = r"localhost\SQLEXPRESS01" 
DB_NAME = "dbporter_test"

print(f"🐘 Подключаемся к MS SQL Server ({DB_HOST})...")

# Строка подключения для Windows-аутентификации (trusted_connection=yes)
# Обрати внимание: нет логина и пароля, только @ перед хостом
master_url = f"mssql+pyodbc://@{DB_HOST}/master?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

try:
    # isolation_level="AUTOCOMMIT" обязателен для команды CREATE DATABASE
    master_engine = create_engine(master_url, isolation_level="AUTOCOMMIT")
    
    with master_engine.connect() as conn:
        # Создаем базу данных, если её еще нет
        conn.execute(text(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{DB_NAME}') CREATE DATABASE {DB_NAME}"))
    print(f"✅ База данных '{DB_NAME}' создана (или уже существовала).")
    
    # Теперь подключаемся к нашей новой базе и заливаем данные
    target_url = f"mssql+pyodbc://@{DB_HOST}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
    target_engine = create_engine(target_url)
    
    print("📦 Заливаем данные в SQL Server...")
    df.to_sql("users", target_engine, if_exists="replace", index=False)
    print("✅ MS SQL Server готов! (таблица users)")

except OperationalError as e:
    print("\n❌ Не удалось подключиться к SQL Server.")
    print("Убедись, что в SQL Server Configuration Manager включен протокол TCP/IP для SQLEXPRESS01.")
    print(f"Детали: {e}")
except Exception as e:
    print(f"\n❌ Другая ошибка: {e}")

print("\n🎉 Все готово! Запускай GUI: python -m dbporter.gui.app")