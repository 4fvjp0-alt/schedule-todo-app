import os
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')

DATABASE_URL = os.environ.get('DATABASE_URL')  # PostgreSQL on cloud, None = SQLite locally


# ── DB abstraction ────────────────────────────────────────────────────────────

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn, 'pg'
    else:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), 'data.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'


def query(sql, params=(), fetchone=False, fetchall=False, commit=False):
    """Run a SQL query. Handles both SQLite and PostgreSQL transparently."""
    conn, driver = get_db()
    # Convert ? placeholders to %s for PostgreSQL
    if driver == 'pg':
        sql = sql.replace('?', '%s')
        cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
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

    lastrowid = cur.lastrowid if driver == 'sqlite' else None
    if driver == 'pg' and commit:
        # Get last inserted id via RETURNING clause (handled separately)
        pass

    conn.close()
    return result, lastrowid


def insert(sql, params=()):
    """INSERT with RETURNING id for PostgreSQL."""
    conn, driver = get_db()
    if driver == 'pg':
        sql = sql.replace('?', '%s')
        # Append RETURNING id
        if 'RETURNING' not in sql.upper():
            sql += ' RETURNING id'
        cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
        cur.execute(sql, params)
        row = cur.fetchone()
        new_id = row['id'] if row else None
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
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                completed INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'medium',
                due_date TEXT DEFAULT '',
                created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                start_datetime TEXT NOT NULL,
                end_datetime TEXT DEFAULT '',
                color TEXT DEFAULT '#4f8ef7',
                created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
            )
        ''')
    else:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                completed INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'medium',
                due_date TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                start_datetime TEXT NOT NULL,
                end_datetime TEXT DEFAULT '',
                color TEXT DEFAULT '#4f8ef7',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        ''')
    conn.commit()
    conn.close()


# ── Static ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ── Todos ─────────────────────────────────────────────────────────────────────

@app.route('/api/todos', methods=['GET'])
def get_todos():
    rows, _ = query(
        'SELECT * FROM todos ORDER BY completed ASC, due_date ASC, created_at DESC',
        fetchall=True
    )
    return jsonify(rows or [])


@app.route('/api/todos', methods=['POST'])
def create_todo():
    d = request.json
    new_id = insert(
        'INSERT INTO todos (title, description, priority, due_date) VALUES (?,?,?,?)',
        (d['title'], d.get('description', ''), d.get('priority', 'medium'), d.get('due_date', ''))
    )
    row, _ = query('SELECT * FROM todos WHERE id=?', (new_id,), fetchone=True)
    return jsonify(row), 201


@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    d = request.json
    query(
        'UPDATE todos SET title=?, description=?, completed=?, priority=?, due_date=? WHERE id=?',
        (d['title'], d.get('description', ''), d.get('completed', 0),
         d.get('priority', 'medium'), d.get('due_date', ''), todo_id),
        commit=True
    )
    row, _ = query('SELECT * FROM todos WHERE id=?', (todo_id,), fetchone=True)
    return jsonify(row)


@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    query('DELETE FROM todos WHERE id=?', (todo_id,), commit=True)
    return '', 204


# ── Events ────────────────────────────────────────────────────────────────────

@app.route('/api/events', methods=['GET'])
def get_events():
    rows, _ = query(
        'SELECT * FROM events ORDER BY start_datetime ASC',
        fetchall=True
    )
    return jsonify(rows or [])


@app.route('/api/events', methods=['POST'])
def create_event():
    d = request.json
    new_id = insert(
        'INSERT INTO events (title, description, start_datetime, end_datetime, color) VALUES (?,?,?,?,?)',
        (d['title'], d.get('description', ''), d['start_datetime'],
         d.get('end_datetime', ''), d.get('color', '#4f8ef7'))
    )
    row, _ = query('SELECT * FROM events WHERE id=?', (new_id,), fetchone=True)
    return jsonify(row), 201


@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    d = request.json
    query(
        'UPDATE events SET title=?, description=?, start_datetime=?, end_datetime=?, color=? WHERE id=?',
        (d['title'], d.get('description', ''), d['start_datetime'],
         d.get('end_datetime', ''), d.get('color', '#4f8ef7'), event_id),
        commit=True
    )
    row, _ = query('SELECT * FROM events WHERE id=?', (event_id,), fetchone=True)
    return jsonify(row)


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    query('DELETE FROM events WHERE id=?', (event_id,), commit=True)
    return '', 204


if __name__ == '__main__':
    init_db()
    mode = 'PostgreSQL (클라우드)' if DATABASE_URL else 'SQLite (로컬)'
    print(f'\n{"="*50}')
    print(f'  일정/할일 관리 앱  |  DB: {mode}')
    print(f'{"="*50}')
    print(f'  PC:     http://localhost:5000')
    if not DATABASE_URL:
        print(f'  모바일: http://<이 PC의 IP>:5000  (같은 WiFi)')
    print(f'{"="*50}\n')
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
