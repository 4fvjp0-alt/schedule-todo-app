"""
DB 초기화 및 초기 사용자 생성 스크립트
Render 쉘에서 실행: python seed.py
"""
import os
from werkzeug.security import generate_password_hash
from app import get_db, init_db, insert

def seed():
    init_db()
    conn, driver = get_db()
    cur = conn.cursor()

    print("모든 데이터 초기화 중...")
    if driver == 'pg':
        cur.execute("DELETE FROM comments")
        cur.execute("DELETE FROM todos")
        cur.execute("DELETE FROM events")
        cur.execute("DELETE FROM users")
    else:
        cur.execute("DELETE FROM comments")
        cur.execute("DELETE FROM todos")
        cur.execute("DELETE FROM events")
        cur.execute("DELETE FROM users")
    conn.commit()
    conn.close()

    print("사용자 생성 중...")
    users = [('혜수', '1234'), ('상현', '1234')]
    for username, password in users:
        insert('INSERT INTO users (username, password_hash) VALUES (?,?)',
               (username, generate_password_hash(password)))
        print(f"  [완료] {username} 생성")

    print("\n완료!")
    print("로그인 정보:")
    print("  혜수 / 비밀번호: 1234")
    print("  상현 / 비밀번호: 1234")

if __name__ == '__main__':
    seed()
