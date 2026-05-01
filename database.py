import sqlite3
import json
from datetime import datetime

DB_NAME = "math_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        registered_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS personal_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        test_name TEXT,
        correct_answers INTEGER,
        time_spent INTEGER,
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        first_name TEXT,
        last_name TEXT,
        correct_answers INTEGER,
        time_spent INTEGER,
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS test_collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        questions_json TEXT
    )''')
    conn.commit()
    conn.close()

def save_user(user_id, first_name, last_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, first_name, last_name, registered_at) VALUES (?, ?, ?, ?)",
              (user_id, first_name, last_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def save_personal_result(user_id, test_name, correct, time_spent):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO personal_results (user_id, test_name, correct_answers, time_spent, date) VALUES (?, ?, ?, ?, ?)",
              (user_id, test_name, correct, time_spent, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def save_daily_result(user_id, first_name, last_name, correct, time_spent):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("INSERT INTO daily_results (user_id, first_name, last_name, correct_answers, time_spent, date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, first_name, last_name, correct, time_spent, today))
    conn.commit()
    conn.close()

def get_personal_results(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT test_name, correct_answers, time_spent, date FROM personal_results WHERE user_id=? ORDER BY date DESC", (user_id,))
    data = c.fetchall()
    conn.close()
    return data

def clear_personal_results(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM personal_results WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_daily_ranking():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute('''SELECT first_name, last_name, correct_answers, time_spent 
                 FROM daily_results WHERE date=? 
                 ORDER BY correct_answers DESC, time_spent ASC''', (today,))
    data = c.fetchall()
    conn.close()
    return data

def clear_old_daily_results():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("DELETE FROM daily_results WHERE date != ?", (today,))
    conn.commit()
    conn.close()

def get_test_collections():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name FROM test_collections")
    data = c.fetchall()
    conn.close()
    return data

def get_test_collection_by_id(collection_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, questions_json FROM test_collections WHERE id=?", (collection_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    return None, None

def add_test_collection(name, questions):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO test_collections (name, questions_json) VALUES (?, ?)", (name, json.dumps(questions)))
    conn.commit()
    conn.close()
