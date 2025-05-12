from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
        
        # Проверка, существует ли уже запись за эту дату
        cursor.execute("SELECT rowid FROM pressure WHERE user_id = ? AND date = ? ORDER BY time DESC LIMIT 1", (message.from_user.id, past_date))
        existing_entry = cursor.fetchone()

        if existing_entry:
            # Если запись существует, редактируем ее
            cursor.execute("UPDATE pressure SET systolic = ?, diastolic = ?, pulse = ? WHERE rowid = ?",
                           (systolic, diastolic, pulse, existing_entry[0]))
            conn.commit()
            await message.answer(f"✅ Запись за {past_date} была обновлена!")
        else:
            # Если записи нет, создаём новую
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
    cursor.execute("SELECT rowid, date, time, systolic, diastolic, pulse FROM pressure WHERE user_id = ? ORDER BY date DESC, time DESC", (message.from_user.id,))
    rows = cursor.fetchall()
    if rows:
        text = "📝 Последние записи:\n"
        for row in rows:
            entry_text = f"{row[1]} {row[2]} — {row[3]}/{row[4]}, пульс {row[5]}"
            edit_button = InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{row[0]}")
            delete_button = InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{row[0]}")
            keyboard = InlineKeyboardMarkup(row_width=2).add(edit_button, delete_button)
            await message.answer(entry_text, reply_markup=keyboard)
    else:
        await message.answer("📍 У вас пока нет записей.")

@dp.callback_query_handler(lambda query: query.data.startswith("edit_"))
async def edit_entry_callback(query: types.CallbackQuery):
    entry_id = query.data.split("_")[1]
    cursor.execute("SELECT date, time, systolic, diastolic, pulse FROM pressure WHERE rowid = ?", (entry_id,))
    entry = cursor.fetchone()
    if entry:
        await query.message.answer(f"Редактирование записи от {entry[0]} {entry[1]}.\nВведите новые данные в формате: САД/ДАД Пульс")
        await dp.bot.answer_callback_query(query.id)  # Закрыть кнопку после нажатия
        # Далее обработчик обновления записи, чтобы перезаписать данные в базу

@dp.callback_query_handler(lambda query: query.data.startswith("delete_"))
async def delete_entry_callback(query: types.CallbackQuery):
    entry_id = query.data.split("_")[1]
    cursor.execute("SELECT date FROM pressure WHERE rowid = ?", (entry_id,))
    entry = cursor.fetchone()
    if entry:
        cursor.execute("DELETE FROM pressure WHERE rowid = ?", (entry_id,))
        conn.commit()
        await query.message.answer(f"🗑 Запись за {entry[0]} была удалена.")
        await dp.bot.answer_callback_query(query.id)  # Закрыть кнопку после нажатия

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
