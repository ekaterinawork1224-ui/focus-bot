from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import date, timedelta
import asyncio
import aioschedule as schedule

TOKEN = "8518435616:AAElInJHuK4AwF41G1G93kVs0ainvSGAVrg"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.answer(
        "Привет 🤍\n\n"
        "Я твой фокус-бот.\n"
        "Утром напомню главное,\n"
        "днём мягко верну к фокусу,\n"
        "вечером подведём итоги и спланируем завтра ✨"
    )

# ===== БАЗА =====
db = sqlite3.connect("focus.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS days (
    user_id INTEGER,
    day TEXT,
    main_goal TEXT,
    habits TEXT,
    optional_goals TEXT,
    habits_done TEXT,
    optional_done TEXT,
    main_done INTEGER
)
""")
db.commit()

# ===== СОСТОЯНИЯ ДИАЛОГА =====
user_state = {}
ASK_MAIN = "ask_main"
ASK_HABITS = "ask_habits"
ASK_OPTIONAL = "ask_optional"

# ===== УТРО =====
async def morning_message():
    today = str(date.today())
    cur.execute("SELECT user_id, main_goal FROM days WHERE day=?", (today,))
    for user_id, main in cur.fetchall():
        await bot.send_message(
            user_id,
            f"Доброе утро ☀️\n\n"
            f"Главное сегодня:\n"
            f"**{main}**\n\n"
            f"Если сделать только это — день уже засчитан 🤍",
            parse_mode="Markdown"
        )

# ===== ДЕНЬ =====
async def daytime_reminder():
    today = str(date.today())
    cur.execute("SELECT user_id, main_goal FROM days WHERE day=?", (today,))
    for user_id, main in cur.fetchall():
        await bot.send_message(
            user_id,
            f"Небольшое напоминание 🤍\n\n"
            f"Если сейчас есть силы только на одно —\n"
            f"вернись к **{main}**.",
            parse_mode="Markdown"
        )

# ===== ВЕЧЕР: ИТОГИ =====
async def evening_checkin():
    today = str(date.today())
    cur.execute("SELECT user_id, habits FROM days WHERE day=?", (today,))
    
    for user_id, habits in cur.fetchall():
        kb = InlineKeyboardMarkup(row_width=1)

        # привычки
        if habits:
            for h in habits.split(","):
                kb.add(
                    InlineKeyboardButton(
                        text=f"✔️ {h.strip()}",
                        callback_data=f"habit:{h.strip()}"
                    )
                )

        # второстепенные цели
        cur.execute(
            "SELECT optional_goals FROM days WHERE user_id=? AND day=?",
            (user_id, today)
        )
        row = cur.fetchone()
        optional = row[0] if row else ""

        if optional:
            for o in optional.split(","):
                kb.add(
                    InlineKeyboardButton(
                        text=f"⭐ {o.strip()}",
                        callback_data=f"optional:{o.strip()}"
                    )
                )

        kb.add(
            InlineKeyboardButton("Главное сделано ✅", callback_data="main_done"),
            InlineKeyboardButton("Перейти к плану на завтра ➜", callback_data="plan_next")
        )

        await bot.send_message(
            user_id,
            "Как прошёл день? 🤍\n\nОтметь, что получилось:",
            reply_markup=kb
        )
# ===== ПЛАН НА ЗАВТРА =====
async def start_planning(user_id):
    user_state[user_id] = ASK_MAIN
    await bot.send_message(
        user_id,
        "Давай набросаем завтрашний день 🤍\n\n"
        "Сначала — *главная задача*.\n"
        "Та, после которой день уже будет засчитан.",
        parse_mode="Markdown"
    )
@dp.message_handler(commands=["week"])
async def week_stats(message: types.Message):
    user_id = message.from_user.id
    today = date.today()
    week_ago = today - timedelta(days=7)

    cur.execute(
        "SELECT main_done, habits, habits_done FROM days WHERE user_id=? AND day>=?",
        (user_id, str(week_ago))
    )
    rows = cur.fetchall()

    if not rows:
        await message.answer("За последнюю неделю данных пока нет 🤍")
        return

    total_days = len(rows)
    main_done_count = 0
    habit_total = 0
    habit_done_total = 0

    for row in rows:
        main_done = row[0]
        habits = row[1]
        habits_done = row[2]

        if main_done == 1:
            main_done_count += 1

        if habits:
            habit_total += len(habits.split(","))

        if habits_done:
            habit_done_total += len(habits_done.split(","))

    await message.answer(
        f"Статистика за 7 дней 📊\n\n"
        f"Главная цель: {main_done_count}/{total_days}\n"
        f"Привычки: {habit_done_total}/{habit_total}\n\n"
        f"Ты строишь систему 🤍"
    )
@dp.message_handler()
async def dialog(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_state:
        return

    tomorrow = str(date.today() + timedelta(days=1))

    if user_state[user_id] == ASK_MAIN:
        cur.execute(
            "INSERT OR REPLACE INTO days VALUES (?, ?, ?, '', '', '', '', 0)",
            (user_id, tomorrow, text)
        )
        db.commit()
        user_state[user_id] = ASK_HABITS
        await message.answer("Теперь привычки 🤍\nМожно списком через запятую.")

    elif user_state[user_id] == ASK_HABITS:
        cur.execute(
            "UPDATE days SET habits=? WHERE user_id=? AND day=?",
            (text, user_id, tomorrow)
        )
        db.commit()
        user_state[user_id] = ASK_OPTIONAL
        await message.answer(
            "И опциональные цели.\n"
            "Это «если будут силы».\n\n"
            "Можно написать или ответить: нет"
        )

    elif user_state[user_id] == ASK_OPTIONAL:
        cur.execute(
            "UPDATE days SET optional_goals=? WHERE user_id=? AND day=?",
            (text, user_id, tomorrow)
        )
        db.commit()
        del user_state[user_id]
        await message.answer(
            "Готово ✨\n\n"
            "Если сделать только главное — день уже будет хорошим 🤍"
        )

# ===== КНОПКИ =====
@dp.callback_query_handler(lambda c: c.data.startswith("habit"))
async def habit_done(callback: types.CallbackQuery):
    habit = callback.data.split(":")[1]
    user_id = callback.from_user.id
    today = str(date.today())

    cur.execute(
        "SELECT habits_done FROM days WHERE user_id=? AND day=?",
        (user_id, today)
    )
    row = cur.fetchone()
    done = row[0] if row and row[0] else ""
    new_done = done + ", " + habit if done else habit

    cur.execute(
        "UPDATE days SET habits_done=? WHERE user_id=? AND day=?",
        (new_done, user_id, today)
    )
    db.commit()
    await callback.answer("Отмечено 🤍")
@dp.callback_query_handler(lambda c: c.data.startswith("optional"))
async def optional_done(callback: types.CallbackQuery):
    goal = callback.data.split(":")[1]
    user_id = callback.from_user.id
    today = str(date.today())

    cur.execute(
        "SELECT optional_done FROM days WHERE user_id=? AND day=?",
        (user_id, today)
    )
    row = cur.fetchone()
    done = row[0] if row and row[0] else ""
    new_done = done + ", " + goal if done else goal

    cur.execute(
        "UPDATE days SET optional_done=? WHERE user_id=? AND day=?",
        (new_done, user_id, today)
    )
    db.commit()

    await callback.answer("Отмечено ⭐")
@dp.callback_query_handler(lambda c: c.data == "main_done")
async def main_done(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    today = str(date.today())

    cur.execute(
        "UPDATE days SET main_done=1 WHERE user_id=? AND day=?",
        (user_id, today)
    )
    db.commit()

    cur.execute(
        "SELECT habits, habits_done, optional_goals, optional_done FROM days WHERE user_id=? AND day=?",
        (user_id, today)
    )
    row = cur.fetchone()

    habits = row[0] if row and row[0] else ""
    habits_done = row[1] if row and row[1] else ""
    optional = row[2] if row and row[2] else ""
    optional_done = row[3] if row and row[3] else ""

    total = len(habits.split(",")) if habits else 0
    done_count = len(habits_done.split(",")) if habits_done else 0

    optional_total = len(optional.split(",")) if optional else 0
    optional_count = len(optional_done.split(",")) if optional_done else 0

    percent = int((done_count / total) * 100) if total > 0 else 0

    await callback.message.answer(
        f"День засчитан ✅\n\n"
        f"Привычки: {done_count}/{total}\n"
        f"Дополнительно: {optional_count}/{optional_total}\n"
        f"Процент привычек: {percent}%\n\n"
        f"Ты закрыла главное — это самое важное 🤍"
    )
@dp.callback_query_handler(lambda c: c.data == "plan_next")
async def plan_next(callback: types.CallbackQuery):
    await start_planning(callback.from_user.id)
    await callback.answer()

# ===== ПЛАНИРОВЩИК =====
async def scheduler():
    schedule.every().day.at("08:00").do(morning_message)
    schedule.every().day.at("14:00").do(daytime_reminder)
    schedule.every().day.at("21:00").do(evening_checkin)

    while True:
        await schedule.run_pending()
        await asyncio.sleep(60)

async def main():
    asyncio.create_task(scheduler())
    print("Бот запущен 🤍")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())