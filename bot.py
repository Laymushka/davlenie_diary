from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from datetime import datetime

import os
API_TOKEN = os.getenv('API_TOKEN')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Инициализация базы данных
conn = sqlite3.connect('pressure_diary.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS pressure (
    user_id INTEGER,
    date TEXT,
    systolic INTEGER,
    diastolic INTEGER,
    pulse INTEGER,
    note TEXT
)''')
conn.commit()

# Клавиатура главного меню
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("📥 Сделать запись"))
main_kb.add(KeyboardButton("🗓 Запись за прошедшую дату"), KeyboardButton("📃 Посмотреть дневник"))

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("👋 Я бот для ведения дневника давления. Выберите действие:", reply_markup=main_kb)

@dp.message_handler(lambda message: message.text == "📥 Сделать запись")
async def new_entry(message: types.Message):
    await message.answer("Введите данные в формате: САД/ДАД Пульс (например: 120/80 72)")

@dp.message_handler(lambda message: '/' not in message.text and message.text.replace(' ', '').isdigit() is False)
async def handle_entry(message: types.Message):
    try:
        parts = message.text.split()
        pressure = parts[0].split('/')
        systolic = int(pressure[0])
        diastolic = int(pressure[1])
        pulse = int(parts[1]) if len(parts) > 1 else 0
        cursor.execute("INSERT INTO pressure (user_id, date, systolic, diastolic, pulse, note) VALUES (?, ?, ?, ?, ?, ?)",
                       (message.from_user.id, datetime.now().strftime('%Y-%m-%d'), systolic, diastolic, pulse, ''))
        conn.commit()
        await message.answer("✅ Запись сохранена!")
    except:
        await message.answer("⚠️ Ошибка. Убедитесь, что вы ввели данные в правильном формате.")

@dp.message_handler(lambda message: message.text == "📃 Посмотреть дневник")
async def show_diary(message: types.Message):
    cursor.execute("SELECT date, systolic, diastolic, pulse FROM pressure WHERE user_id = ? ORDER BY date DESC LIMIT 10", (message.from_user.id,))
    rows = cursor.fetchall()
    if rows:
        text = "📝 Последние записи:\n"
        for row in rows:
            text += f"{row[0]} — {row[1]}/{row[2]}, пульс {row[3]}\n"
        await message.answer(text)
    else:
        await message.answer("📭 У вас пока нет записей.")
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
