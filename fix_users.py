import sqlite3

old_db = r'C:\Users\lahm\Desktop\Many AgentS\blueprint\devteam_users.db'
new_db = r'C:\Users\lahm\Desktop\Many AgentS\blueprint\BLUEPRINT_users.db'

old = sqlite3.connect(old_db)
old.row_factory = sqlite3.Row
users = old.execute('SELECT username, password_hash FROM users').fetchall()
old.close()

print('Old users:', [u['username'] for u in users])

new = sqlite3.connect(new_db)
count = 0
for u in users:
    try:
        new.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (u['username'], u['password_hash']))
        count += 1
        print('Copied:', u['username'])
    except Exception as e:
        print('Skip:', u['username'], e)
new.commit()
new.close()
print('Done, copied', count, 'users')
