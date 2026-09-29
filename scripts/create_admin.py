#!/usr/bin/env python3
"""
scripts/create_admin.py
Run once to promote a user to Super Admin.

Usage:
    python scripts/create_admin.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User

def main():
    app = create_app('development')
    with app.app_context():
        users = User.query.order_by(User.created_at).all()
        if not users:
            print('No users found. Register first via the web app.')
            return

        print('\nAll users:')
        for u in users:
            role = 'super' if u.is_super_admin else ('admin' if u.is_admin else 'user')
            print(f'  [{u.id}] {u.username} <{u.email}> — {role}')

        email = input('\nEnter email to promote to Super Admin: ').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if not user:
            print('User not found.')
            return

        user.is_admin       = True
        user.is_super_admin = True
        db.session.commit()
        print(f'\n✓ {user.username} is now a Super Admin!')

if __name__ == '__main__':
    main()
