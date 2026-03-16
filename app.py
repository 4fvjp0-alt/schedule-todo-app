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
    cur = conn.cursor()
    if driver == 'pg':
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL, description TEXT DEFAULT '',
            completed INTEGER DEFAULT 0, priority TEXT DEFAULT 'medium',
            due_date TEXT DEFAULT '', tags TEXT DEFAULT '',
            created_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL, description TEXT DEFAULT '',
            start_datetime TEXT NOT NULL, end_datetime TEXT DEFAULT '',
            color TEXT DEFAULT '#4f8ef7', tags TEXT DEFAULT '',
            created_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS'))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            item_type TEXT NOT NULL, item_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS'))''')
        # Migrations for existing tables
        for tbl in ('todos', 'events'):
            for col in (f"ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
                        f"ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''"):
                try:
                    cur.execute(f'ALTER TABLE {tbl} {col}')
                except Exception:
                    conn.rollback()
    else:
        cur.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                title TEXT NOT NULL, description TEXT DEFAULT '',
                completed INTEGER DEFAULT 0, priority TEXT DEFAULT 'medium',
                due_date TEXT DEFAULT '', tags TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                title TEXT NOT NULL, description TEXT DEFAULT '',
                start_datetime TEXT NOT NULL, end_datetime TEXT DEFAULT '',
                color TEXT DEFAULT '#4f8ef7', tags TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
                item_type TEXT NOT NULL, item_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')));
        ''')
        for tbl in ('todos', 'events'):
            for col, default in (('user_id', 'INTEGER REFERENCES users(id)'),
                                 ('tags', "TEXT DEFAULT ''")):
                try:
                    cur.execute(f'ALTER TABLE {tbl} ADD COLUMN {col} {default}')
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
    (SELECT COUNT(*) FROM comments WHERE item_type='todo' AND item_id=t.id) AS comment_count
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
    return jsonify(row), 201

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
@login_required
def update_todo(todo_id):
    owner, _ = query('SELECT user_id FROM todos WHERE id=?', (todo_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    d = request.json
    query('UPDATE todos SET title=?,description=?,completed=?,priority=?,due_date=?,tags=? WHERE id=?',
          (d['title'], d.get('description',''), d.get('completed',0),
           d.get('priority','medium'), d.get('due_date',''), d.get('tags',''), todo_id), commit=True)
    row, _ = query(f'{TODO_SELECT} WHERE t.id=?', (todo_id,), fetchone=True)
    return jsonify(row)

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def delete_todo(todo_id):
    owner, _ = query('SELECT user_id FROM todos WHERE id=?', (todo_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    query('DELETE FROM comments WHERE item_type=? AND item_id=?', ('todo', todo_id), commit=True)
    query('DELETE FROM todos WHERE id=?', (todo_id,), commit=True)
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
        'INSERT INTO events (user_id,title,description,start_datetime,end_datetime,color,tags) VALUES (?,?,?,?,?,?,?)',
        (current_user_id(), d['title'], d.get('description',''),
         d['start_datetime'], d.get('end_datetime',''), d.get('color','#4f8ef7'), d.get('tags','')))
    row, _ = query(f'{EVENT_SELECT} WHERE e.id=?', (new_id,), fetchone=True)
    return jsonify(row), 201

@app.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    owner, _ = query('SELECT user_id FROM events WHERE id=?', (event_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    d = request.json
    query('UPDATE events SET title=?,description=?,start_datetime=?,end_datetime=?,color=?,tags=? WHERE id=?',
          (d['title'], d.get('description',''), d['start_datetime'],
           d.get('end_datetime',''), d.get('color','#4f8ef7'), d.get('tags',''), event_id), commit=True)
    row, _ = query(f'{EVENT_SELECT} WHERE e.id=?', (event_id,), fetchone=True)
    return jsonify(row)

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    owner, _ = query('SELECT user_id FROM events WHERE id=?', (event_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    query('DELETE FROM comments WHERE item_type=? AND item_id=?', ('event', event_id), commit=True)
    query('DELETE FROM events WHERE id=?', (event_id,), commit=True)
    return '', 204


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
    return jsonify(row), 201

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    owner, _ = query('SELECT user_id FROM comments WHERE id=?', (comment_id,), fetchone=True)
    if not owner or owner['user_id'] != current_user_id():
        return jsonify({'error': '권한이 없습니다'}), 403
    query('DELETE FROM comments WHERE id=?', (comment_id,), commit=True)
    return '', 204


# ── Boot ──────────────────────────────────────────────────────────────────────
init_db()

if __name__ == '__main__':
    print(f'\n  일정/할일 앱  |  http://localhost:5000\n')
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
