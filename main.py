import asyncio
import random
import time
import math
import sqlite3
from datetime import datetime
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN, ADMIN_ID
from database import *
from states import RegisterState, AddTestState, TestState
from keyboards import *

# Flask app (Render uchun keep-alive)
app = Flask('')

@app.route('/')
def home():
    return "🤖 Matematika bot ishlamoqda!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Bot sozlamalari
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Foydalanuvchilarning test jarayoni uchun vaqtincha ma'lumotlar
user_test_data = {}  # user_id: {...}
user_timer_tasks = {}  # user_id: asyncio.Task

# ==================== ADMIN TEKSHIRUV FUNKSIYASI ====================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ==================== ADMIN MENU BUYRUQLARINI SOZLASH ====================

async def setup_admin_commands():
    commands = [
        BotCommand(command="stat", description="📊 Bot statistikasi"),
        BotCommand(command="users_count", description="👥 Foydalanuvchilar soni"),
        BotCommand(command="broadcast", description="📢 Xabar tarqatish"),
        BotCommand(command="clear_daily", description="🗑 Kunlik natijalarni tozalash"),
        BotCommand(command="get_stats", description="📈 Eng yaxshi natijalar"),
        BotCommand(command="export_users", description="📤 Foydalanuvchilarni eksport qilish"),
    ]
    await bot.set_my_commands(commands)

async def get_bot_statistics():
    conn = sqlite3.connect("math_bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM personal_results")
    total_tests = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM daily_results WHERE date = date('now')")
    today_tests = c.fetchone()[0]
    conn.close()
    return total_users, total_tests, today_tests

async def get_all_users():
    conn = sqlite3.connect("math_bot.db")
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, last_name, registered_at FROM users")
    users = c.fetchall()
    conn.close()
    return users

async def clear_daily_results_full():
    conn = sqlite3.connect("math_bot.db")
    c = conn.cursor()
    c.execute("DELETE FROM daily_results")
    conn.commit()
    conn.close()

async def get_top_users():
    conn = sqlite3.connect("math_bot.db")
    c = conn.cursor()
    c.execute('''SELECT u.first_name, u.last_name, COUNT(p.id) as tests_count 
                 FROM users u LEFT JOIN personal_results p ON u.user_id = p.user_id 
                 GROUP BY u.user_id ORDER BY tests_count DESC LIMIT 10''')
    data = c.fetchall()
    conn.close()
    return data

async def get_top_results():
    conn = sqlite3.connect("math_bot.db")
    c = conn.cursor()
    c.execute('''SELECT first_name, last_name, correct_answers, time_spent, date 
                 FROM personal_results ORDER BY correct_answers DESC, time_spent ASC LIMIT 10''')
    data = c.fetchall()
    conn.close()
    return data

# ==================== JAVOBLARNI TAHLLI QILISH ====================

def analyze_answers(questions, user_answers):
    """Xato qilingan savollarni tahlil qilish"""
    wrong_answers = []
    for i, (q, user_ans) in enumerate(zip(questions, user_answers)):
        if user_ans != q["correct"]:
            correct_text = q["options"][q["correct"]]
            wrong_answers.append({
                "num": i + 1,
                "question": q["question"],
                "user_choice": q["options"][user_ans] if user_ans < len(q["options"]) else "Javob berilmagan",
                "correct": correct_text
            })
    return wrong_answers

# ==================== STANDART 30 TA SAVOL ====================

def generate_standard_questions():
    questions = []
    
    # 1. a + b
    a, b = random.randint(1, 100), random.randint(1, 100)
    correct = a + b
    options = [correct, correct+1, correct-1, correct+2]
    random.shuffle(options)
    questions.append({"question": f"{a} + {b} = ?", "options": options, "correct": options.index(correct)})
    
    # 2. a - b
    a, b = random.randint(20, 100), random.randint(1, 19)
    correct = a - b
    options = [correct, correct+1, correct-1, correct+2]
    random.shuffle(options)
    questions.append({"question": f"{a} - {b} = ?", "options": options, "correct": options.index(correct)})
    
    # 3. a * b
    a, b = random.randint(2, 20), random.randint(2, 15)
    correct = a * b
    options = [correct, correct+2, correct-2, correct+5]
    random.shuffle(options)
    questions.append({"question": f"{a} × {b} = ?", "options": options, "correct": options.index(correct)})
    
    # 4. a / b
    a, b = random.randint(10, 100), random.randint(2, 10)
    correct = round(a / b, 2)
    options = [correct, round(correct+0.5,2), round(correct-0.5,2), round(correct+1,2)]
    random.shuffle(options)
    questions.append({"question": f"{a} ÷ {b} = ? (2 xonagacha)", "options": options, "correct": options.index(correct)})
    
    # 5. x ning darajasi
    x = random.randint(2, 10)
    y = random.randint(2, 5)
    correct = x ** y
    options = [correct, correct*2, correct//2, correct+10]
    random.shuffle(options)
    questions.append({"question": f"{x} ning {y}-darajasi = ?", "options": options, "correct": options.index(correct)})
    
    # 6. Ildiz ostida y
    y = random.randint(4, 100)
    correct = round(math.sqrt(y), 2)
    options = [correct, round(correct+1,2), round(correct-1,2), round(correct+0.5,2)]
    random.shuffle(options)
    questions.append({"question": f"√{y} = ? (2 xonagacha)", "options": options, "correct": options.index(correct)})
    
    # 7. EKUK
    a, b = random.randint(2, 30), random.randint(2, 30)
    correct = abs(a*b) // math.gcd(a, b)
    options = [correct, correct*2, correct//2, correct+5]
    random.shuffle(options)
    questions.append({"question": f"{a} va {b} sonlarining EKUK = ?", "options": options, "correct": options.index(correct)})
    
    # 8. EKUB
    a, b = random.randint(2, 50), random.randint(2, 50)
    correct = math.gcd(a, b)
    options = [correct, correct*2, correct+1, correct+3]
    random.shuffle(options)
    questions.append({"question": f"{a} va {b} sonlarining EKUB = ?", "options": options, "correct": options.index(correct)})
    
    # 9. Murakkab daraja
    a = random.randint(2, 5)
    b = random.randint(2, 3)
    c = random.randint(2, 3)
    correct = (a ** b) ** c
    options = [correct, correct*2, correct//2, correct+10]
    random.shuffle(options)
    questions.append({"question": f"({a}^{b})^{c} = ?", "options": options, "correct": options.index(correct)})
    
    # 10. Murakkab ildiz
    a, b = random.randint(1, 50), random.randint(1, 50)
    correct = round(math.sqrt(a + b), 2)
    options = [correct, round(correct+1,2), round(correct-1,2), round(correct+0.5,2)]
    random.shuffle(options)
    questions.append({"question": f"√({a} + {b}) = ?", "options": options, "correct": options.index(correct)})
    
    # 11. Diskriminant
    a = random.randint(1, 5)
    b = random.randint(-10, 10)
    c = random.randint(-10, 10)
    correct = b**2 - 4*a*c
    options = [correct, correct+5, correct-5, correct+10]
    random.shuffle(options)
    questions.append({"question": f"{a}x² + {b}x + {c} = 0 ning diskriminantini toping", "options": options, "correct": options.index(correct)})
    
    # 12. Ildizlar
    a = random.randint(1, 3)
    b = random.randint(-8, 8)
    c = random.randint(-8, 8)
    D = b**2 - 4*a*c
    if D >= 0:
        x1 = round((-b + math.sqrt(D)) / (2*a), 2)
        x2 = round((-b - math.sqrt(D)) / (2*a), 2)
        correct = f"{x1} va {x2}"
    else:
        correct = "Haqiqiy ildiz yo'q"
    options = [correct, "1 va 2", "-1 va -2", "0 va 1"]
    random.shuffle(options)
    questions.append({"question": f"{a}x² + {b}x + {c} = 0 ning ildizlarini toping", "options": options, "correct": options.index(correct)})
    
    # 13. Ildizlar yig'indisi
    a = random.randint(1, 5)
    b = random.randint(-10, 10)
    c = random.randint(-10, 10)
    correct = -b / a
    options = [round(correct,2), round(correct+1,2), round(correct-1,2), round(correct+2,2)]
    random.shuffle(options)
    questions.append({"question": f"{a}x² + {b}x + {c} = 0 ning ildizlari yig'indisi = ?", "options": options, "correct": options.index(round(correct,2))})
    
    # 14. Logarifm
    a = random.randint(2, 5)
    b = a ** random.randint(1, 3)
    correct = round(math.log(b, a), 2)
    options = [correct, correct+1, correct-1, correct+2]
    random.shuffle(options)
    questions.append({"question": f"log_{a}({b}) = ?", "options": options, "correct": options.index(correct)})
    
    # 15. Murakkab logarifm
    a = random.randint(2, 4)
    b = random.randint(2, 5)
    c = random.randint(2, 5)
    correct = round(math.log(b*c, a), 2)
    options = [correct, round(correct+1,2), round(correct-1,2), round(correct+0.5,2)]
    random.shuffle(options)
    questions.append({"question": f"log_{a}({b}×{c}) = ?", "options": options, "correct": options.index(correct)})
    
    # 16. Logarifm tenglama
    a = random.randint(2, 4)
    b = random.randint(1, 3)
    correct = a ** b
    options = [correct, correct*2, correct//2, correct+3]
    random.shuffle(options)
    questions.append({"question": f"log_{a}(x) = {b} tenglamani yeching. x = ?", "options": options, "correct": options.index(correct)})
    
    # 17. Funksiya choraklari
    functions = [
        ("y = 2x + 1", "1, 2, 3"), ("y = -x + 5", "1, 2, 4"), ("y = x²", "1, 2"),
        ("y = -x² + 4", "1, 2, 3, 4"), ("y = 3/x", "1, 3"), ("y = -2/x", "2, 4")
    ]
    func_name, correct_ch = random.choice(functions)
    options = ["1, 2, 3", "1, 2, 4", "1, 2, 3, 4", "1, 3"]
    random.shuffle(options)
    questions.append({"question": f"{func_name} funksiya qaysi choraklardan o'tadi?", "options": options, "correct": options.index(correct_ch)})
    
    # 18. Trigonometriya boshlang'ich
    angles = [0, 30, 45, 60, 90]
    angle = random.choice(angles)
    if random.choice([True, False]):
        correct = round(math.cos(math.radians(angle)), 2)
        q_text = f"cos({angle}°) = ?"
    else:
        correct = round(math.sin(math.radians(angle)), 2)
        q_text = f"sin({angle}°) = ?"
    options = [correct, round(correct+0.3,2), round(correct-0.3,2), round(1-correct,2)]
    random.shuffle(options)
    questions.append({"question": q_text, "options": options, "correct": options.index(correct)})
    
    # 19. Trigonometriya o'rta
    angles = [30, 45, 60]
    angle = random.choice(angles)
    correct = round(math.tan(math.radians(angle)), 2)
    options = [correct, round(correct+0.5,2), round(correct-0.5,2), 1.0]
    random.shuffle(options)
    questions.append({"question": f"tan({angle}°) = ?", "options": options, "correct": options.index(correct)})
    
    # 20. Murakkab trigonometriya
    angle = random.randint(0, 360)
    correct = 1
    options = [1, 0, -1, 2]
    random.shuffle(options)
    questions.append({"question": f"sin²({angle}°) + cos²({angle}°) = ?", "options": options, "correct": options.index(correct)})
    
    # 21. Arifmetik progressiya
    a1 = random.randint(1, 10)
    d = random.randint(1, 5)
    n = random.randint(3, 10)
    correct = a1 + (n-1) * d
    options = [correct, correct+d, correct-d, correct+2*d]
    random.shuffle(options)
    questions.append({"question": f"Arifmetik progressiyada a₁={a1}, d={d}. a_{n}=?", "options": options, "correct": options.index(correct)})
    
    # 22. Geometrik progressiya
    b1 = random.randint(1, 5)
    q = random.randint(2, 4)
    n = random.randint(3, 6)
    correct = b1 * (q ** (n-1))
    options = [correct, correct*q, correct//q, correct+5]
    random.shuffle(options)
    questions.append({"question": f"Geometrik progressiyada b₁={b1}, q={q}. b_{n}=?", "options": options, "correct": options.index(correct)})
    
    # 23. Hosila boshlang'ich
    a = random.randint(2, 10)
    b = random.randint(1, 10)
    correct = a
    options = [correct, correct+1, correct-1, b]
    random.shuffle(options)
    questions.append({"question": f"y = {a}x + {b} funksiyaning hosilasi y' = ?", "options": options, "correct": options.index(correct)})
    
    # 24. Hosila o'rta
    a = random.randint(2, 5)
    b = random.randint(2, 5)
    correct = f"{2*a}x + {b}"
    options = [f"{2*a}x + {b}", f"{a}x + {b}", f"{2*a}x", f"{2*a}x + {b+1}"]
    random.shuffle(options)
    questions.append({"question": f"y = {a}x² + {b}x funksiyaning hosilasi y' = ?", "options": options, "correct": options.index(correct)})
    
    # 25. Hosila yuqori
    a = random.randint(1, 3)
    b = random.randint(1, 3)
    correct = f"{3*a}x² + {b}"
    options = [f"{3*a}x² + {b}", f"{2*a}x + {b}", f"{3*a}x²", f"{a}x² + {b}"]
    random.shuffle(options)
    questions.append({"question": f"y = {a}x³ + {b}x funksiyaning hosilasi y' = ?", "options": options, "correct": options.index(correct)})
    
    # 26. Boshlang'ich oddiy
    a = random.randint(2, 5)
    correct = f"({a}/2)x² + C"
    options = [f"{a}x + C", f"({a}/2)x² + C", f"{a}x² + C", f"({a}/3)x³ + C"]
    random.shuffle(options)
    questions.append({"question": f"∫{a}x dx = ?", "options": options, "correct": options.index(correct)})
    
    # 27. Boshlang'ich murakkab
    a = random.randint(2, 4)
    b = random.randint(1, 5)
    correct = f"({a}/3)x³ + {b}x + C"
    options = [f"{a}x³ + {b}x + C", f"({a}/3)x³ + {b}x + C", f"{a}x² + {b}x + C", f"({a}/2)x² + {b} + C"]
    random.shuffle(options)
    questions.append({"question": f"∫({a}x² + {b})dx = ?", "options": options, "correct": options.index(correct)})
    
    # 28. Pifagor teoremasi
    a = random.randint(3, 10)
    b = random.randint(3, 10)
    correct = round(math.sqrt(a**2 + b**2), 2)
    options = [correct, round(correct+1,2), round(correct-1,2), round(correct+0.5,2)]
    random.shuffle(options)
    questions.append({"question": f"To'g'ri burchakli uchburchak katetlari {a} va {b}. Gipotenuzani toping", "options": options, "correct": options.index(correct)})
    
    # 29. Faktorial
    n = random.randint(3, 7)
    correct = math.factorial(n)
    options = [correct, correct*2, correct//2, correct+10]
    random.shuffle(options)
    questions.append({"question": f"{n}! = ?", "options": options, "correct": options.index(correct)})
    
    # 30. Juft/toq/tub
    num = random.randint(10, 100)
    if num % 2 == 0:
        correct = "Juft"
    else:
        correct = "Toq"
    options = ["Tub", "Toq", "Juft", "Murakkab"]
    random.shuffle(options)
    questions.append({"question": f"{num} soni qaysi turga kiradi?", "options": options, "correct": options.index(correct)})
    
    random.shuffle(questions)
    return questions

# ==================== SAVOL YUBORISH FUNKSIYASI (TIMER BILAN) ====================

async def cancel_timer(user_id: int):
    """Foydalanuvchi uchun taymerni bekor qilish"""
    if user_id in user_timer_tasks:
        task = user_timer_tasks[user_id]
        if not task.done():
            task.cancel()
        del user_timer_tasks[user_id]

async def timeout_callback(user_id: int, message: Message, question_index: int):
    """60 soniyadan keyin avtomatik keyingi savolga o'tish"""
    await asyncio.sleep(60)
    
    if user_id not in user_test_data:
        return
    
    data = user_test_data[user_id]
    # Agar hali o'sha savol bo'lsa (javob berilmagan)
    if data["current_q"] == question_index and len(data["answers"]) == question_index:
        data["answers"].append(0)  # Noto'g'ri deb hisobla
        data["current_q"] += 1
        
        try:
            await message.answer("⏰ **Vaqt tugadi! Javob berilmadi.**", parse_mode="Markdown")
        except:
            pass
        
        await send_question(message, user_id)

async def send_question(message: Message, user_id: int):
    """Savol yuborish va taymer boshlash"""
    if user_id not in user_test_data:
        return
    
    data = user_test_data[user_id]
    q_index = data["current_q"]
    
    if q_index >= len(data["questions"]):
        # Test tugadi
        await cancel_timer(user_id)
        
        end_time = time.time()
        time_spent = int(end_time - data["start_time"])
        correct_count = sum(data["answers"])
        
        # Xato qilingan savollarni tahlil qilish
        wrong_answers = analyze_answers(data["questions"], data["answers"])
        
        # Natija xabari
        result_text = f"✅ **Test tugadi!**\n\n"
        result_text += f"📊 **To'g'ri javoblar:** {correct_count}/{len(data['questions'])}\n"
        result_text += f"⏱ **Sarflangan vaqt:** {time_spent} sekund\n"
        result_text += f"📈 **Foiz:** {int(correct_count/len(data['questions'])*100)}%\n\n"
        
        if wrong_answers:
            result_text += f"❌ **Xato qilingan savollar ({len(wrong_answers)} ta):**\n\n"
            for wa in wrong_answers[:10]:  # Faqat 10 tasini ko'rsatish
                result_text += f"**{wa['num']}.** {wa['question']}\n"
                result_text += f"   Sizning javobingiz: {wa['user_choice']}\n"
                result_text += f"   ✅ To'g'ri javob: {wa['correct']}\n\n"
            if len(wrong_answers) > 10:
                result_text += f"... va yana {len(wrong_answers)-10} ta xato"
        
        await message.answer(result_text, parse_mode="Markdown")
        
        # Ma'lumotlar bazasiga saqlash
        save_personal_result(user_id, data["test_name"], correct_count, time_spent)
        
        conn = sqlite3.connect("math_bot.db")
        c = conn.cursor()
        c.execute("SELECT first_name, last_name FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            first_name, last_name = row
            save_daily_result(user_id, first_name, last_name, correct_count, time_spent)
        
        del user_test_data[user_id]
        await message.answer("Yana test yechish uchun menyudan foydalaning.", reply_markup=main_menu())
        return
    
    # Savolni yuborish
    q_data = data["questions"][q_index]
    remaining = len(data["questions"]) - q_index
    text = f"❓ **Savol {q_index+1}/{len(data['questions'])}**\n"
    text += f"⏰ Vaqt limiti: 60 soniya\n"
    text += f"📋 Qolgan savollar: {remaining}\n\n"
    text += f"{q_data['question']}"
    
    try:
        msg = await message.answer(text, parse_mode="Markdown", reply_markup=option_buttons(q_data["options"]))
        data["message_id"] = msg.message_id
        
        # Taymerni boshlash
        await cancel_timer(user_id)
        task = asyncio.create_task(timeout_callback(user_id, message, q_index))
        user_timer_tasks[user_id] = task
    except Exception as e:
        print(f"Xatolik: {e}")

# ==================== FOYDALANUVCHI RO'YXATDAN O'TISH ====================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(RegisterState.waiting_for_first_name)
    await message.answer(
        "🤖 **Assalomu alaykum!**\n\n"
        "🏆 **Matematika botiga xush kelibsiz!**\n\n"
        "Bu bot sizning matematika bilimingizni oshirish uchun yaratilgan.\n"
        "📚 30 ta savoldan iborat testlar, ⏰ 60 soniya vaqt limiti!\n\n"
        "📝 **Iltimos, ismingizni kiriting:**",
        parse_mode="Markdown"
    )

@dp.message(RegisterState.waiting_for_first_name)
async def get_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await state.set_state(RegisterState.waiting_for_last_name)
    await message.answer("📝 Endi familiyangizni kiriting:")

@dp.message(RegisterState.waiting_for_last_name)
async def get_last_name(message: Message, state: FSMContext):
    data = await state.get_data()
    first_name = data["first_name"]
    last_name = message.text
    save_user(message.from_user.id, first_name, last_name)
    await state.clear()
    await message.answer(
        f"✅ **Xush kelibsiz, {first_name} {last_name}!**\n\n"
        f"Quyidagi menyu orqali test yechishni boshlashingiz mumkin:\n\n"
        f"📚 **Testni boshlash** - 30 ta savoldan iborat test\n"
        f"📊 **Shaxsiy natijalar** - Sizning barcha natijalaringiz\n"
        f"🏆 **Kunlik reyting** - Bugungi eng yaxshi natijalar\n"
        f"✏️ **Test qo'shish** - O'zingiz test yaratishingiz\n"
        f"🎯 **Test to'plamlari** - Boshqalar yaratgan testlar",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# ==================== TEST YECHISH (1-BO'LIM) ====================

@dp.message(lambda msg: msg.text == "📚 Testni boshlash")
async def start_test(message: Message):
    user_id = message.from_user.id
    
    # Agar oldingi test mavjud bo'lsa, tozalash
    if user_id in user_test_data:
        await cancel_timer(user_id)
        del user_test_data[user_id]
    
    questions = generate_standard_questions()
    user_test_data[user_id] = {
        "questions": questions,
        "answers": [],
        "start_time": time.time(),
        "current_q": 0,
        "message_id": None,
        "test_name": "Standart test"
    }
    
    await message.answer("🎯 **Test boshlandi!**\n\n⏰ Har bir savolga 60 soniya vaqtingiz bor.\n✅ Javob berish uchun tugmalardan birini bosing.\n⏰ Javob bermasangiz, avtomatik keyingi savolga o'tadi.\n\n**Omad!** 🍀", parse_mode="Markdown")
    await send_question(message, user_id)

@dp.callback_query(lambda c: c.data and c.data.startswith("ans_"))
async def handle_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_test_data:
        await callback.answer("Test topilmadi! /start bilan qaytadan boshlang.")
        return
    
    data = user_test_data[user_id]
    q_index = data["current_q"]
    
    if q_index >= len(data["questions"]):
        await callback.answer("Test allaqachon tugagan!")
        return
    
    chosen_idx = int(callback.data.split("_")[1])
    is_correct = (chosen_idx == data["questions"][q_index]["correct"])
    
    data["answers"].append(1 if is_correct else 0)
    data["current_q"] += 1
    
    await callback.answer("✅ To'g'ri!" if is_correct else "❌ Xato!")
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await send_question(callback.message, user_id)

# ==================== SHAXSIY NATIJALAR (2-BO'LIM) ====================

@dp.message(lambda msg: msg.text == "📊 Shaxsiy natijalar")
async def show_personal_results(message: Message):
    user_id = message.from_user.id
    results = get_personal_results(user_id)
    
    if not results:
        await message.answer(
            "❌ **Siz hali hech qanday test yechmagansiz!**\n\n"
            "📚 Test yechish uchun 'Testni boshlash' tugmasini bosing.",
            parse_mode="Markdown"
        )
        return
    
    text = "📊 **SIZNING SHAXSIY NATIJALARINGIZ**\n\n"
    for i, (test_name, correct, time_spent, date) in enumerate(results, 1):
        text += f"**{i}.** 📅 {date[:10]}\n"
        text += f"   📚 {test_name}\n"
        text += f"   ✅ To'g'ri: {correct} ta\n"
        text += f"   ⏱ Vaqt: {time_spent} sek\n\n"
    
    text += "\n🗑 **Natijalarni tozalash** uchun /clear_results yuboring."
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("clear_results"))
async def clear_results(message: Message):
    user_id = message.from_user.id
    clear_personal_results(user_id)
    await message.answer("✅ **Sizning barcha shaxsiy natijalaringiz tozalandi!**", parse_mode="Markdown")

# ==================== KUNLIK REYTING (3-BO'LIM) ====================

@dp.message(lambda msg: msg.text == "🏆 Kunlik reyting")
async def show_daily_ranking(message: Message):
    ranking = get_daily_ranking()
    
    if not ranking:
        await message.answer(
            "❌ **Bugun hali hech kim test yechmagan!**\n\n"
            "🏆 Birinchi bo'lish uchun test yeching!",
            parse_mode="Markdown"
        )
        return
    
    text = "🏆 **BUGUNGI KUNNING ENG YAXSHI NATIJALARI** 🏆\n\n"
    for idx, (first_name, last_name, correct, time_spent) in enumerate(ranking[:20], 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        text += f"{medal} {first_name} {last_name}\n"
        text += f"   ✅ {correct} ta to'g'ri\n"
        text += f"   ⏱ {time_spent} sekund\n\n"
    
    await message.answer(text, parse_mode="Markdown")

# ==================== TEST QO'SHISH (4-BO'LIM) - HAMMA UCHUN ====================

@dp.message(lambda msg: msg.text == "✏️ Test qo'shish")
async def start_add_test(message: Message, state: FSMContext):
    await state.set_state(AddTestState.waiting_for_collection_name)
    await message.answer(
        "📝 **Yangi test to'plami yaratish**\n\n"
        "Test to'plamiga nom bering (masalan: 'Algebra asoslari'):",
        parse_mode="Markdown"
    )

@dp.message(AddTestState.waiting_for_collection_name)
async def get_collection_name(message: Message, state: FSMContext):
    await state.update_data(collection_name=message.text, questions=[])
    await state.set_state(AddTestState.waiting_for_question)
    await message.answer("✏️ **1-savol matnini yozing:**", parse_mode="Markdown")

@dp.message(AddTestState.waiting_for_question)
async def get_question(message: Message, state: FSMContext):
    await state.update_data(current_question=message.text)
    await state.set_state(AddTestState.waiting_for_options)
    await message.answer(
        "📝 **4 ta javob variantini vergul bilan ajratib yozing**\n\n"
        "Masalan: `10, 20, 30, 40`",
        parse_mode="Markdown"
    )

@dp.message(AddTestState.waiting_for_options)
async def get_options(message: Message, state: FSMContext):
    options = [opt.strip() for opt in message.text.split(",")]
    if len(options) != 4:
        await message.answer("❌ **4 ta variant kiriting!** Vergul bilan ajrating.", parse_mode="Markdown")
        return
    await state.update_data(current_options=options)
    await state.set_state(AddTestState.waiting_for_correct_option)
    await message.answer("✅ **To'g'ri javobni raqam bilan tanlang (1-4):**", parse_mode="Markdown")

@dp.message(AddTestState.waiting_for_correct_option)
async def get_correct(message: Message, state: FSMContext):
    try:
        correct_idx = int(message.text) - 1
        if correct_idx not in range(4):
            raise ValueError
    except:
        await message.answer("❌ **1 dan 4 gacha raqam kiriting!**", parse_mode="Markdown")
        return
    
    data = await state.get_data()
    question = {
        "question": data["current_question"],
        "options": data["current_options"],
        "correct": correct_idx
    }
    questions = data.get("questions", [])
    questions.append(question)
    await state.update_data(questions=questions)
    await state.set_state(AddTestState.waiting_for_more)
    await message.answer(
        f"✅ **Savol qo'shildi!** ({len(questions)} ta savol)\n\n"
        f"Yana savol qo'shasizmi? (ha/yo'q)",
        parse_mode="Markdown"
    )

@dp.message(AddTestState.waiting_for_more)
async def ask_more(message: Message, state: FSMContext):
    if message.text.lower() in ["ha", "yes", "y", "haa", "1"]:
        await state.set_state(AddTestState.waiting_for_question)
        await message.answer("✏️ **Yangi savol matnini yozing:**", parse_mode="Markdown")
    else:
        data = await state.get_data()
        name = data["collection_name"]
        questions = data["questions"]
        
        if len(questions) == 0:
            await message.answer("❌ **Hech qanday savol qo'shilmadi!**", parse_mode="Markdown")
            await state.clear()
            await message.answer("Asosiy menyu", reply_markup=main_menu())
            return
        
        add_test_collection(name, questions)
        await state.clear()
        await message.answer(
            f"✅ **'{name}' test to'plami muvaffaqiyatli saqlandi!**\n\n"
            f"📚 {len(questions)} ta savol qo'shildi.\n"
            f"🎯 Endi boshqalar ham bu testni yecha oladi.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

# ==================== TEST TO'PLAMLARI (5-BO'LIM) ====================

@dp.message(lambda msg: msg.text == "🎯 Test to'plamlari")
async def show_test_collections(message: Message):
    collections = get_test_collections()
    
    if not collections:
        await message.answer(
            "❌ **Hali hech qanday test to'plami mavjud emas!**\n\n"
            "✏️ **'Test qo'shish'** bo'limidan o'zingiz test yarating.",
            parse_mode="Markdown"
        )
        return
    
    await message.answer(
        "📚 **Mavjud test to'plamlari:**\n\n"
        "Kerakli testni tanlang:",
        parse_mode="Markdown",
        reply_markup=custom_tests_list(collections)
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("start_custom_"))
async def start_custom_test(callback: CallbackQuery):
    collection_id = int(callback.data.split("_")[2])
    name, questions = get_test_collection_by_id(collection_id)
    
    if not questions:
        await callback.answer("Test topilmadi!")
        return
    
    user_id = callback.from_user.id
    
    # Agar oldingi test mavjud bo'lsa, tozalash
    if user_id in user_test_data:
        await cancel_timer(user_id)
        del user_test_data[user_id]
    
    user_test_data[user_id] = {
        "questions": questions,
        "answers": [],
        "start_time": time.time(),
        "current_q": 0,
        "message_id": None,
        "test_name": name
    }
    
    await callback.message.delete()
    await callback.message.answer(
        f"🎯 **Test boshlandi: {name}**\n\n"
        f"📚 Jami savollar: {len(questions)} ta\n"
        f"⏰ Har bir savolga 60 soniya vaqt\n\n"
        f"**Omad!** 🍀",
        parse_mode="Markdown"
    )
    await send_question(callback.message, user_id)

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🔙 **Asosiy menyuga qaytdingiz.**",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# ==================== ADMIN BUYRUQLARI ====================

@dp.message(Command("stat"))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return
    
    total_users, total_tests, today_tests = await get_bot_statistics()
    await message.answer(
        f"📊 **BOT STATISTIKASI**\n\n"
        f"👥 Foydalanuvchilar soni: {total_users}\n"
        f"📝 Jami testlar: {total_tests}\n"
        f"📅 Bugungi testlar: {today_tests}\n"
        f"🤖 Bot ishlayapti ✅",
        parse_mode="Markdown"
    )

@dp.message(Command("users_count"))
async def admin_users_count(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return
    
    users = await get_all_users()
    text = f"👥 **BARCHA FOYDALANUVCHILAR** ({len(users)} ta)\n\n"
    for i, (user_id, first_name, last_name, reg_date) in enumerate(users[:50], 1):
        text += f"{i}. 🆔 `{user_id}` | {first_name} {last_name} | 📅 {reg_date[:10]}\n"
    if len(users) > 50:
        text += f"\n... va yana {len(users)-50} ta foydalanuvchi"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return
    
    msg_text = message.text.replace("/broadcast", "").strip()
    if not msg_text:
        await message.answer("❌ Xabar matnini yozing!\nMasalan: /broadcast Salom hammaga!")
        return
    
    users = await get_all_users()
    sent = 0
    failed = 0
    
    status_msg = await message.answer(f"📢 Xabar yuborish boshlandi... ({len(users)} ta foydalanuvchiga)")
    
    for user_id, _, _, _ in users:
        try:
            await bot.send_message(user_id, f"📢 **XABAR**\n\n{msg_text}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Yuborildi: {sent} ta\n❌ Yuborilmadi: {failed} ta")

@dp.message(Command("clear_daily"))
async def admin_clear_daily(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return
    
    await clear_daily_results_full()
    await message.answer("✅ Kunlik natijalar tozalandi!")

@dp.message(Command("get_stats"))
async def admin_get_full_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return
    
    top_users = await get_top_users()
    top_results = await get_top_results()
    
    text = "🏆 **ENG FAOL FOYDALANUVCHILAR**\n\n"
    for idx, (first, last, count) in enumerate(top_users, 1):
        text += f"{idx}. {first} {last} → {count} ta test\n"
    
    text += "\n📊 **ENG YAXSHI NATIJALAR**\n\n"
    for idx, (first, last, correct, time_spent, date) in enumerate(top_results, 1):
        text += f"{idx}. {first} {last} → ✅ {correct} ta ⏱ {time_spent} sek (📅 {date[:10]})\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("export_users"))
async def admin_export_users(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return
    
    users = await get_all_users()
    text = "user_id,first_name,last_name,registered_at\n"
    for user_id, first_name, last_name, reg_date in users:
        text += f"{user_id},{first_name},{last_name},{reg_date}\n"
    
    from aiogram.types import BufferedInputFile
    file_bytes = text.encode('utf-8')
    await message.answer_document(
        BufferedInputFile(file_bytes, filename="users_export.csv"),
        caption="📊 Foydalanuvchilar ro'yxati"
    )

# ==================== BOTNI ISHGA TUSHIRISH ====================

async def main():
    # Flask serverni alohida threadda ishga tushirish
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    init_db()
    clear_old_daily_results()
    await setup_admin_commands()
    print("🤖 Bot ishga tushdi... Admin huquqi faol!")
    print("🌐 Flask server 8080-portda ishlamoqda!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
