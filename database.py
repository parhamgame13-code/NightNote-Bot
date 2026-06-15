import aiosqlite

DB_NAME = "nightnote.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            score INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            last_daily TEXT DEFAULT NULL,
            is_banned INTEGER DEFAULT 0
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_name TEXT
        )''')
        await db.execute('''INSERT OR IGNORE INTO channels (channel_id, channel_name) 
            VALUES (?, ?)''', ('@NightNote_official', 'NightNote'))
        await db.commit()

async def add_user(user_id, first_name, username, referred_by=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''INSERT OR IGNORE INTO users 
            (user_id, first_name, username, referred_by) VALUES (?, ?, ?, ?)''',
            (user_id, first_name, username, referred_by))
        if referred_by:
            await db.execute('''UPDATE users SET referral_count = referral_count + 1 
                WHERE user_id = ?''', (referred_by,))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_score(user_id, score):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''UPDATE users SET score = MAX(score, ?) 
            WHERE user_id = ?''', (score, user_id))
        await db.commit()

async def get_leaderboard():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''SELECT first_name, username, score 
            FROM users ORDER BY score DESC LIMIT 10''') as cursor:
            return await cursor.fetchall()

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total = (await cursor.fetchone())[0]
        return total

async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT channel_id, channel_name FROM channels') as cursor:
            return await cursor.fetchall()

async def add_channel(channel_id, channel_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO channels (channel_id, channel_name) VALUES (?, ?)',
            (channel_id, channel_name))
        await db.commit()

async def remove_channel(channel_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
        await db.commit()

async def ban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def unban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        await db.commit()

async def set_daily(user_id, today):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET last_daily = ?, score = score + 10 WHERE user_id = ?',
            (today, user_id))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id FROM users WHERE is_banned = 0') as cursor:
            return await cursor.fetchall()

async def add_question(question, option_a, option_b, option_c, option_d, correct):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct TEXT
        )''')
        await db.execute('''INSERT INTO questions 
            (question, option_a, option_b, option_c, option_d, correct) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (question, option_a, option_b, option_c, option_d, correct))
        await db.commit()

async def get_daily_questions():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct TEXT
        )''')
        async with db.execute('SELECT * FROM questions ORDER BY RANDOM() LIMIT 5') as c:
            return await c.fetchall()

async def get_user_quiz_today(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question_id INTEGER,
            date TEXT,
            correct INTEGER
        )''')
        today = datetime.now().strftime("%Y-%m-%d")
        async with db.execute('''SELECT COUNT(*) FROM quiz_answers 
            WHERE user_id = ? AND date = ?''', (user_id, today)) as c:
            return (await c.fetchone())[0]

async def save_quiz_answer(user_id, question_id, correct):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question_id INTEGER,
            date TEXT,
            correct INTEGER
        )''')
        today = datetime.now().strftime("%Y-%m-%d")
        await db.execute('''INSERT INTO quiz_answers (user_id, question_id, date, correct
