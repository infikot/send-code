import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import secrets
from dateutil import parser

# Конфигурация Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.db'
db = SQLAlchemy(app)

# Модель Paste
class Paste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)
    title = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime)
    from_ip = db.Column(db.String(15))
    password_hash = db.Column(db.String(128))
    is_public = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Paste {self.id}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


def generate_unique_code():
    """Генерирует уникальный 8-символьный код."""
    while True:
        code = secrets.token_hex(4)  # 8 hex символов
        if not Paste.query.filter_by(code=code).first():
            return code

def migrate_database(old_db_path='pastes.db', default_ip='127.0.0.1'):
    """Миграция базы данных."""

    with app.app_context():
        db.create_all()
        db.session.query(Paste).delete()
        db.session.commit()
        print("Новая база данных очищена.")

    old_conn = sqlite3.connect(old_db_path)
    old_cursor = old_conn.cursor()

    old_cursor.execute("SELECT id, title, content, created_at, password_hash, is_public FROM paste")
    pastes_data = old_cursor.fetchall()
    print(f"Количество записей, полученных из старой базы: {len(pastes_data)}")
    old_conn.close()

    with app.app_context():
        with db.session.begin():  # Явная транзакция
            for paste_data in pastes_data:
                paste_id, title, content, created_at, password_hash, is_public = paste_data

                # Номера ID, для которых content должен быть "Error"
                special_ids = [42, 43, 44, 45, 46, 47, 48, 49]

                print(f"Обработка записи id={paste_id}")

                # Обработка BLOB данных в title
                try:
                    title = title.decode('utf-8', errors='ignore') if isinstance(title, bytes) else title  # Обработка title
                except Exception as e:
                    print(f"Не удалось декодировать title для id={paste_id}: {e}. Оставляем как строку.")
                    title = str(title)

                # Присваиваем "Error" content для определенных id
                if paste_id in special_ids:
                    content = "Error"
                    print(f"Запись id={paste_id} - Content установлено в 'Error'.")
                else:
                    # Обработка BLOB данных в content (если необходимо)
                    try:
                        content = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content
                    except Exception as e:
                        print(f"Не удалось декодировать content для id={paste_id}: {e}. Оставляем как строку.")
                        content = str(content)

                code = generate_unique_code()

                from_ip = default_ip

                try:
                    # Use dateutil.parser to handle various date formats
                    created_at_datetime = parser.parse(created_at) if created_at else datetime.datetime.now()
                except (ValueError, TypeError) as e:  # Catch TypeError if created_at is None
                    print(f"Ошибка при парсинге даты для id={paste_id}: {e}. Используется текущее время.")
                    created_at_datetime = datetime.datetime.now()

                new_paste = Paste(
                    code=code,
                    title=title,
                    content=content,
                    created_at=created_at_datetime,
                    from_ip=from_ip,
                    password_hash=password_hash,
                    is_public=bool(is_public)
                )
                db.session.add(new_paste)
                print(f"Добавлена паста id={paste_id} в сессию.")
        print("Транзакция завершена успешно.")

if __name__ == '__main__':
    migrate_database()

    with app.app_context():
        pastes = Paste.query.all()
        print(f"Количество записей в новой базе: {len(pastes)}")  # Проверка
        for paste in pastes:
            print(f"ID: {paste.id}, Code: {paste.code}, Title: {paste.title}, IP: {paste.from_ip}, Content: {paste.content[:50]}...")  # Обрезаем content для вывода