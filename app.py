import os
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-please-change')
DATABASE_URL = os.environ.get('DATABASE_URL')


# ── DB ────────────────────────────────────────────────────────────────────────

def get_db():
    if DATABASE_URL:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn, 'pg'
    else:
        import sqlite3
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'data.db'))
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'


def query(sql, params=(), fetchone=False, fetchall=False, commit=False):
    conn, driver = get_db()
    if driver == 'pg':
        sql = sql.replace('?', '%s')
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    cur.execute(sql, params)
    result = None
    if fetchone:
        row = cur.fetchone()
        result = dict(row) if row else None
    elif fetchall:
        rows = cur.fetchall()
        result = [dict(r) for r in rows]
    if commit:
        conn.commit()
    conn.close()
    return result, None


def insert(sql, params=()):
    conn, driver = get_db()
    if driver == 'pg':
        sql = sql.replace('?', '%s')
        if 'RETURNING' not in sql.upper():
            sql += ' RETURNING id'
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        new_id = cur.fetchone()['id']
    else:
        cur = conn.cursor()
        cur.execute(sql, params)
        new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def init_db():
    conn, driver = get_db()
    if driver == 'pg':
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL, description TEXT DEFAULT '',
            completed INTEGER DEFAULT 0, priority TEXT DEFAULT 'medium',
            due_date TEXT DEFAULT '', tags TEXT DEFAULT '',
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL, description TEXT DEFAULT '',
            start_datetime TEXT NOT NULL, end_datetime TEXT DEFAULT '',
            color TEXT DEFAULT '#4f8ef7', tags TEXT DEFAULT '',
            recurrence TEXT DEFAULT 'none',
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            item_type TEXT NOT NULL, item_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS subtasks (
            id SERIAL PRIMARY KEY, todo_id INTEGER REFERENCES todos(id) ON DELETE CASCADE,
            title TEXT NOT NULL, completed INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY, user_id INTEGER, username TEXT,
            action TEXT NOT NULL, item_type TEXT DEFAULT '', item_title TEXT DEFAULT '',
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS diary (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            entry_date TEXT NOT NULL, title TEXT DEFAULT '', content TEXT NOT NULL,
            created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'),
            updated_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS'))''')
        # migrations
        for tbl in ('todos', 'events'):
            for col in ("ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
                        "ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''"):
                try:
                    cur.execute(f'ALTER TABLE {tbl} {col}')
                except Exception:
                    pass
        for col_sql in (
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS recurrence TEXT DEFAULT 'none'",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS all_day INTEGER DEFAULT 0",
        ):
            try:
                cur.execute(col_sql)
            except Exception:
                pass
    else:
        cur = conn.cursor()
        cur.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','+9 hours')));
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                title TEXT NOT NULL, description TEXT DEFAULT '',
                completed INTEGER DEFAULT 0, priority TEXT DEFAULT 'medium',
                due_date TEXT DEFAULT '', tags TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','+9 hours')));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                title TEXT NOT NULL, description TEXT DEFAULT '',
                start_datetime TEXT NOT NULL, end_datetime TEXT DEFAULT '',
                color TEXT DEFAULT '#4f8ef7', tags TEXT DEFAULT '',
                recurrence TEXT DEFAULT 'none',
                created_at TEXT DEFAULT (datetime('now','+9 hours')));
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                item_type TEXT NOT NULL, item_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','+9 hours')));
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, todo_id INTEGER REFERENCES todos(id),
                title TEXT NOT NULL, completed INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','+9 hours')));
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
                action TEXT NOT NULL, item_type TEXT DEFAULT '', item_title TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','+9 hours')));
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                entry_date TEXT NOT NULL, title TEXT DEFAULT '', content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','+9 hours')),
                updated_at TEXT DEFAULT (datetime('now','+9 hours')));
        ''')
        for tbl in ('todos', 'events'):
            for col, default in (('user_id', 'INTEGER REFERENCES users(id)'),
                                 ('tags', "TEXT DEFAULT ''")):
                try:
                    cur.execute(f'ALTER TABLE {tbl} ADD COLUMN {col} {default}')
                    conn.commit()
                except Exception:
                    pass
        for col, default in (
            ('recurrence', "TEXT DEFAULT 'none'"),
            ('all_day', 'INTEGER DEFAULT 0'),
        ):
            try:
                cur.execute(f'ALTER TABLE events ADD COLUMN {col} {default}')
                conn.commit()
            except Exception:
                pass
    conn.commit()
    conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다'}), 401
        return f(*args, **kwargs)
    return decorated

def current_user_id():
    return session.get('user_id')

def log_activity(action, item_type='', item_title=''):
    try:
        insert('INSERT INTO activity_log (user_id, username, action, item_type, item_title) VALUES (?,?,?,?,?)',
               (session.get('user_id'), session.get('username'), action, item_type, (item_title or '')[:80]))
    except Exception:
        pass

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/register', methods=['POST'])
def register():
    d = request.json
    username = (d.get('username') or '').strip()
    password = d.get('password') or ''
    if not username or not password:
        return jsonify({'error': '아이디와 비밀번호를 입력하세요'}), 400
    if len(username) < 2:
        return jsonify({'error': '아이디는 2자 이상이어야 합니다'}), 400
    if len(password) < 4:
        return jsonify({'error': '비밀번호는 4자 이상이어야 합니다'}), 400
    existing, _ = query('SELECT id FROM users WHERE username=?', (username,), fetchone=True)
    if existing:
        return jsonify({'error': '이미 사용 중인 아이디입니다'}), 409
    new_id = insert('INSERT INTO users (username, password_hash) VALUES (?,?)',
                    (username, generate_password_hash(password)))
    session['user_id'] = new_id
    session['username'] = username
    return jsonify({'id': new_id, 'username': username}), 201

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    username = (d.get('username') or '').strip()
    user, _ = query('SELECT * FROM users WHERE username=?', (username,), fetchone=True)
    if not user or not check_password_hash(user['password_hash'], d.get('password') or ''):
        return jsonify({'error': '아이디 또는 비밀번호가 틀렸습니다'}), 401
    session['user_id'] = user['id']
    session['username'] = user['username']
    return jsonify({'id': user['id'], 'username': user['username']})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return '', 204

@app.route('/api/me')
def me():
    if 'user_id' not in session:
        return jsonify(None)
    return jsonify({'id': session['user_id'], 'username': session['username']})

@app.route('/api/seed')
def seed_db():
    secret = request.args.get('secret', '')
    seed_secret = os.environ.get('SEED_SECRET', '')
    if not seed_secret or secret != seed_secret:
        return jsonify({'error': '권한 없음'}), 403

    conn, driver = get_db()
    cur = conn.cursor()
    for tbl in ('activity_log', 'diary', 'comments', 'subtasks', 'todos', 'events', 'users'):
        cur.execute(f'DELETE FROM {tbl}')
    conn.commit()
    conn.close()

    for username, password in [('혜수', '1234'), ('상현', '1234')]:
        insert('INSERT INTO users (username, password_hash) VALUES (?,?)',
               (username, generate_password_hash(password)))

    return jsonify({'ok': True, 'message': '초기화 완료. 혜수/상현 계정 생성됨 (비밀번호: 1234)'})


@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    d = request.json
    current = d.get('current_password') or ''
    new_pw  = d.get('new_password') or ''
    if not current or not new_pw:
        return jsonify({'error': '현재 비밀번호와 새 비밀번호를 입력하세요'}), 400
    if len(new_pw) < 4:
        return jsonify({'error': '새 비밀번호는 4자 이상이어야 합니다'}), 400
    user, _ = query('SELECT * FROM users WHERE id=?', (current_user_id(),), fetchone=True)
    if not user or not check_password_hash(user['password_hash'], current):
        return jsonify({'error': '현재 비밀번호가 틀렸습니다'}), 401
    query('UPDATE users SET password_hash=? WHERE id=?',
          (generate_password_hash(new_pw), current_user_id()), commit=True)
    return jsonify({'ok': True})


@app.route('/api/users')
def get_users():
    rows, _ = query('SELECT id, username FROM users ORDER BY username', fetchall=True)
    return jsonify(rows or [])


# ── Todos ─────────────────────────────────────────────────────────────────────

TODO_SELECT = '''SELECT t.*, u.username,
    (SELECT COUNT(*) FROM comments WHERE item_type='todo' AND item_id=t.id) AS comment_count,
    (SELECT COUNT(*) FROM subtasks WHERE todo_id=t.id) AS subtask_count,
    (SELECT COUNT(*) FROM subtasks WHERE todo_id=t.id AND completed=1) AS subtask_done
    FROM todos t LEFT JOIN users u ON t.user_id=u.id'''

@app.route('/api/todos', methods=['GET'])
def get_todos():
    rows, _ = query(f'{TODO_SELECT} ORDER BY t.completed ASC, t.due_date ASC, t.created_at DESC', fetchall=True)
    return jsonify(rows or [])

@app.route('/api/todos', methods=['POST'])
@login_required
def create_todo():
    d = request.json
    new_id = insert(
        'INSERT INTO todos (user_id,title,description,priority,due_date,tags) VALUES (?,?,?,?,?,?)',
        (current_user_id(), d['title'], d.get('description',''),
         d.get('priority','medium'), d.get('due_date',''), d.get('tags','')))
    row, _ = query(f'{TODO_SELECT} WHERE t.id=?', (new_id,), fetchone=True)
    log_activity('할일 추가', 'todo', d['title'])
    return jsonify(row), 201

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
@login_required
def update_todo(todo_id):
    owner, _ = query('SELECT user_id, completed FROM todos WHERE id=?', (todo_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    d = request.json
    old_completed = owner.get('completed', 0)
    new_completed = d.get('completed', 0)
    query('UPDATE todos SET title=?,description=?,completed=?,priority=?,due_date=?,tags=? WHERE id=?',
          (d['title'], d.get('description',''), new_completed,
           d.get('priority','medium'), d.get('due_date',''), d.get('tags',''), todo_id), commit=True)
    if old_completed != new_completed:
        log_activity('할일 완료' if new_completed else '할일 완료 취소', 'todo', d['title'])
    else:
        log_activity('할일 수정', 'todo', d['title'])
    row, _ = query(f'{TODO_SELECT} WHERE t.id=?', (todo_id,), fetchone=True)
    return jsonify(row)

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def delete_todo(todo_id):
    owner, _ = query('SELECT user_id, title FROM todos WHERE id=?', (todo_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    log_activity('할일 삭제', 'todo', owner.get('title',''))
    query('DELETE FROM subtasks WHERE todo_id=?', (todo_id,), commit=True)
    query('DELETE FROM comments WHERE item_type=? AND item_id=?', ('todo', todo_id), commit=True)
    query('DELETE FROM todos WHERE id=?', (todo_id,), commit=True)
    return '', 204


# ── Subtasks ──────────────────────────────────────────────────────────────────

@app.route('/api/subtasks', methods=['GET'])
def get_subtasks():
    todo_id = request.args.get('todo_id')
    rows, _ = query('SELECT * FROM subtasks WHERE todo_id=? ORDER BY sort_order ASC, id ASC',
                    (todo_id,), fetchall=True)
    return jsonify(rows or [])

@app.route('/api/subtasks', methods=['POST'])
@login_required
def create_subtask():
    d = request.json
    todo_id = d.get('todo_id')
    title = (d.get('title') or '').strip()
    if not title or not todo_id:
        return jsonify({'error': '내용을 입력하세요'}), 400
    todo, _ = query('SELECT user_id FROM todos WHERE id=?', (todo_id,), fetchone=True)
    if not todo or todo['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    mo, _ = query('SELECT COALESCE(MAX(sort_order),0) AS mo FROM subtasks WHERE todo_id=?',
                  (todo_id,), fetchone=True)
    new_id = insert('INSERT INTO subtasks (todo_id, title, sort_order) VALUES (?,?,?)',
                    (todo_id, title, (mo or {}).get('mo', 0) + 1))
    row, _ = query('SELECT * FROM subtasks WHERE id=?', (new_id,), fetchone=True)
    log_activity('서브태스크 추가', 'subtask', title)
    return jsonify(row), 201

@app.route('/api/subtasks/<int:subtask_id>', methods=['PUT'])
@login_required
def update_subtask(subtask_id):
    st, _ = query(
        'SELECT s.*, t.user_id FROM subtasks s JOIN todos t ON s.todo_id=t.id WHERE s.id=?',
        (subtask_id,), fetchone=True)
    if not st or st['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    d = request.json
    query('UPDATE subtasks SET completed=? WHERE id=?',
          (d.get('completed', st['completed']), subtask_id), commit=True)
    row, _ = query('SELECT * FROM subtasks WHERE id=?', (subtask_id,), fetchone=True)
    return jsonify(row)

@app.route('/api/subtasks/<int:subtask_id>', methods=['DELETE'])
@login_required
def delete_subtask(subtask_id):
    st, _ = query(
        'SELECT s.*, t.user_id FROM subtasks s JOIN todos t ON s.todo_id=t.id WHERE s.id=?',
        (subtask_id,), fetchone=True)
    if not st or st['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    query('DELETE FROM subtasks WHERE id=?', (subtask_id,), commit=True)
    return '', 204


# ── Events ────────────────────────────────────────────────────────────────────

EVENT_SELECT = '''SELECT e.*, u.username,
    (SELECT COUNT(*) FROM comments WHERE item_type='event' AND item_id=e.id) AS comment_count
    FROM events e LEFT JOIN users u ON e.user_id=u.id'''

@app.route('/api/events', methods=['GET'])
def get_events():
    rows, _ = query(f'{EVENT_SELECT} ORDER BY e.start_datetime ASC', fetchall=True)
    return jsonify(rows or [])

@app.route('/api/events', methods=['POST'])
@login_required
def create_event():
    d = request.json
    new_id = insert(
        'INSERT INTO events (user_id,title,description,start_datetime,end_datetime,color,tags,recurrence,all_day) VALUES (?,?,?,?,?,?,?,?,?)',
        (current_user_id(), d['title'], d.get('description',''),
         d['start_datetime'], d.get('end_datetime',''), d.get('color','#4f8ef7'),
         d.get('tags',''), d.get('recurrence','none'), d.get('all_day',0)))
    row, _ = query(f'{EVENT_SELECT} WHERE e.id=?', (new_id,), fetchone=True)
    log_activity('일정 추가', 'event', d['title'])
    return jsonify(row), 201

@app.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    owner, _ = query('SELECT user_id FROM events WHERE id=?', (event_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    d = request.json
    query('UPDATE events SET title=?,description=?,start_datetime=?,end_datetime=?,color=?,tags=?,recurrence=?,all_day=? WHERE id=?',
          (d['title'], d.get('description',''), d['start_datetime'],
           d.get('end_datetime',''), d.get('color','#4f8ef7'), d.get('tags',''),
           d.get('recurrence','none'), d.get('all_day',0), event_id), commit=True)
    log_activity('일정 수정', 'event', d['title'])
    row, _ = query(f'{EVENT_SELECT} WHERE e.id=?', (event_id,), fetchone=True)
    return jsonify(row)

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    owner, _ = query('SELECT user_id, title FROM events WHERE id=?', (event_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    log_activity('일정 삭제', 'event', owner.get('title',''))
    query('DELETE FROM comments WHERE item_type=? AND item_id=?', ('event', event_id), commit=True)
    query('DELETE FROM events WHERE id=?', (event_id,), commit=True)
    return '', 204


# ── Activity log ──────────────────────────────────────────────────────────────

@app.route('/api/activity')
def get_activity():
    rows, _ = query(
        'SELECT * FROM activity_log ORDER BY id DESC LIMIT 100',
        fetchall=True)
    return jsonify(rows or [])


# ── Comments ──────────────────────────────────────────────────────────────────

@app.route('/api/comments', methods=['GET'])
def get_comments():
    item_type = request.args.get('type')
    item_id = request.args.get('id')
    rows, _ = query(
        '''SELECT c.*, u.username FROM comments c LEFT JOIN users u ON c.user_id=u.id
           WHERE c.item_type=? AND c.item_id=? ORDER BY c.created_at ASC''',
        (item_type, item_id), fetchall=True)
    return jsonify(rows or [])

@app.route('/api/comments', methods=['POST'])
@login_required
def create_comment():
    d = request.json
    content = (d.get('content') or '').strip()
    if not content:
        return jsonify({'error': '내용을 입력하세요'}), 400
    new_id = insert(
        'INSERT INTO comments (user_id, item_type, item_id, content) VALUES (?,?,?,?)',
        (current_user_id(), d['item_type'], d['item_id'], content))
    row, _ = query(
        'SELECT c.*, u.username FROM comments c LEFT JOIN users u ON c.user_id=u.id WHERE c.id=?',
        (new_id,), fetchone=True)
    log_activity('댓글 작성', d['item_type'], (content[:40]+'…') if len(content)>40 else content)
    return jsonify(row), 201

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    owner, _ = query('SELECT user_id FROM comments WHERE id=?', (comment_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    query('DELETE FROM comments WHERE id=?', (comment_id,), commit=True)
    return '', 204


# ── Diary ─────────────────────────────────────────────────────────────────────

DIARY_SELECT = '''SELECT d.*, u.username FROM diary d LEFT JOIN users u ON d.user_id=u.id'''

@app.route('/api/diary', methods=['GET'])
def get_diary():
    rows, _ = query(f'{DIARY_SELECT} ORDER BY d.entry_date DESC, d.id DESC', fetchall=True)
    return jsonify(rows or [])

@app.route('/api/diary', methods=['POST'])
@login_required
def create_diary():
    d = request.json
    content = (d.get('content') or '').strip()
    entry_date = d.get('entry_date') or ''
    if not content or not entry_date:
        return jsonify({'error': '날짜와 내용을 입력하세요'}), 400
    new_id = insert(
        'INSERT INTO diary (user_id, entry_date, title, content) VALUES (?,?,?,?)',
        (current_user_id(), entry_date, d.get('title',''), content))
    row, _ = query(f'{DIARY_SELECT} WHERE d.id=?', (new_id,), fetchone=True)
    log_activity('일기 작성', 'diary', entry_date)
    return jsonify(row), 201

@app.route('/api/diary/<int:diary_id>', methods=['PUT'])
@login_required
def update_diary(diary_id):
    owner, _ = query('SELECT user_id FROM diary WHERE id=?', (diary_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    d = request.json
    kst_now = "to_char(NOW() AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI:SS')" if DATABASE_URL else "datetime('now','+9 hours')"
    query(f'UPDATE diary SET title=?, content=?, updated_at={kst_now} WHERE id=?',
          (d.get('title',''), d.get('content',''), diary_id), commit=True)
    row, _ = query(f'{DIARY_SELECT} WHERE d.id=?', (diary_id,), fetchone=True)
    log_activity('일기 수정', 'diary', row.get('entry_date','') if row else '')
    return jsonify(row)

@app.route('/api/diary/<int:diary_id>', methods=['DELETE'])
@login_required
def delete_diary(diary_id):
    owner, _ = query('SELECT user_id, entry_date FROM diary WHERE id=?', (diary_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    log_activity('일기 삭제', 'diary', owner.get('entry_date',''))
    query('DELETE FROM diary WHERE id=?', (diary_id,), commit=True)
    return '', 204


# ── Boot ──────────────────────────────────────────────────────────────────────
init_db()

if __name__ == '__main__':
    print(f'\n  일정/할일 앱  |  http://localhost:5000\n')
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
