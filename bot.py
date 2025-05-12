from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from datetime import datetime
import pytz
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
    time TEXT,
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
main_kb.add(KeyboardButton("❌ Удалить последнюю запись"), KeyboardButton("✏️ Редактировать последнюю запись"))

# Получение текущей даты и времени в нужной зоне
TZ = pytz.timezone("Europe/Moscow")

def get_now():
    now = datetime.now(TZ)
    return now.strftime('%Y-%m-%d'), now.strftime('%H:%M')

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("👋 Я бот для ведения дневника давления. Выберите действие:", reply_markup=main_kb)

@dp.message_handler(lambda message: message.text == "📥 Сделать запись")
async def new_entry(message: types.Message):
    await message.answer("Введите данные в формате: САД/ДАД Пульс (например: 120/80 72)")

@dp.message_handler(lambda message: '/' in message.text and message.text.replace(' ', '').replace('/', '').isdigit())
async def handle_entry(message: types.Message):
    try:
        parts = message.text.split()
        pressure = parts[0].split('/')
        systolic = int(pressure[0])
        diastolic = int(pressure[1])
        pulse = int(parts[1]) if len(parts) > 1 else 0
        
        date, time = get_now()
        cursor.execute("INSERT INTO pressure (user_id, date, time, systolic, diastolic, pulse, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (message.from_user.id, date, time, systolic, diastolic, pulse, ''))
        conn.commit()
        await message.answer("✅ Запись сохранена!")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка. Проверьте формат данных. Ошибка: {str(e)}")

@dp.message_handler(lambda message: message.text == "🗓 Запись за прошедшую дату")
async def past_entry_prompt(message: types.Message):
    await message.answer("Для того чтобы сделать запись за прошедшую дату, введите данные в формате: САД/ДАД Пульс Дата (например: 120/80 72 2025-05-10)")

@dp.message_handler(lambda message: '/' in message.text and message.text.replace(' ', '').replace('/', '').isdigit() and len(message.text.split()) == 3)
async def handle_past_entry(message: types.Message):
    try:
        parts = message.text.split()
        pressure = parts[0].split('/')
        systolic = int(pressure[0])
        diastolic = int(pressure[1])
        pulse = int(parts[1]) if len(parts) > 1 else 0
        past_date = parts[2]

        # Проверяем, что дата имеет правильный формат
        datetime.strptime(past_date, '%Y-%m-%d')  # Если дата неправильная, возникнет ошибка ValueError
        
        # Время будет текущее, а дата - введенная пользователем
        date, time = get_now()
        cursor.execute("INSERT INTO pressure (user_id, date, time, systolic, diastolic, pulse, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (message.from_user.id, past_date, time, systolic, diastolic, pulse, ''))
        conn.commit()
        await message.answer(f"✅ Запись за {past_date} сохранена!")
    except ValueError:
        await message.answer("⚠️ Ошибка. Неправильный формат даты. Используйте формат: ГГГГ-ММ-ДД")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка. Проверьте формат данных. Ошибка: {str(e)}")

@dp.message_handler(lambda message: message.text == "📃 Посмотреть дневник")
async def show_diary(message: types.Message):
    cursor.execute("SELECT date, time, systolic, diastolic, pulse FROM pressure WHERE user_id = ? ORDER BY date DESC, time DESC LIMIT 10", (message.from_user.id,))
    rows = cursor.fetchall()
    if rows:
        text = "📝 Последние записи:\n"
        for row in rows:
            text += f"{row[0]} {row[1]} — {row[2]}/{row[3]}, пульс {row[4]}\n"
        await message.answer(text)
    else:
        await message.answer("📍 У вас пока нет записей.")

@dp.message_handler(lambda message: message.text == "❌ Удалить последнюю запись")
async def delete_last_entry(message: types.Message):
    cursor.execute("SELECT rowid FROM pressure WHERE user_id = ? ORDER BY date DESC, time DESC LIMIT 1", (message.from_user.id,))
    last = cursor.fetchone()
    if last:
        cursor.execute("DELETE FROM pressure WHERE rowid = ?", (last[0],))
        conn.commit()
        await message.answer("🗑 Последняя запись удалена.")
    else:
        await message.answer("⚠️ У вас нет записей для удаления.")

@dp.message_handler(lambda message: message.text == "✏️ Редактировать последнюю запись")
async def edit_last_entry_prompt(message: types.Message):
    await message.answer("Введите новые данные в формате: САД/ДАД Пульс (например: 120/80 72)")

@dp.message_handler(lambda message: '/' in message.text and any(trigger in message.text.lower() for trigger in ["редактировать", "редактировать"]))
async def edit_last_entry(message: types.Message):
    try:
        parts = message.text.split()
        pressure = parts[0].split('/')
        systolic = int(pressure[0])
        diastolic = int(pressure[1])
        pulse = int(parts[1]) if len(parts) > 1 else 0

        cursor.execute("SELECT rowid FROM pressure WHERE user_id = ? ORDER BY date DESC, time DESC LIMIT 1", (message.from_user.id,))
        last = cursor.fetchone()
        if last:
            cursor.execute("UPDATE pressure SET systolic = ?, diastolic = ?, pulse = ? WHERE rowid = ?",
                           (systolic, diastolic, pulse, last[0]))
            conn.commit()
            await message.answer("✅ Запись обновлена!")
        else:
            await message.answer("⚠️ У вас нет записей для редактирования.")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка. Проверьте формат данных. Ошибка: {str(e)}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
