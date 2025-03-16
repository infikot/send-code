import asyncio
import logging
import random
import string
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import time
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pytz import timezone
from flask import jsonify
import json

tz = timezone('Europe/Moscow')

class ExcludeRoutesFilter(logging.Filter):
    def __init__(self, routes_to_exclude):
        super().__init__()
        self.routes_to_exclude = routes_to_exclude  # Now a list

    def filter(self, record):
        if request:
            # Check if the request path is in the list of excluded routes
            return request.path not in self.routes_to_exclude
        return True

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ur_test_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pastes.db'
db = SQLAlchemy(app)

white_ips = ['127.0.0.1']

# пример добавления ip
ip_prefix = "192.168.1."
for i in range(1, 256):  # IP-адреса от 192.168.1.1 до 192.168.1.255
    white_ips.append(f"{ip_prefix}{i}")

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://",
)

def generate_unique_code():
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(characters) for _ in range(8))
        if not Paste.query.filter_by(code=code).first():
            return code

class Paste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)  # Уникальный код из 8 символов
    title = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime)
    from_ip = db.Column(db.String(15))  # IP-адрес пользователя, создавшего пасту
    password_hash = db.Column(db.String(128))
    is_public = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Paste {self.id}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@app.route('/')
@limiter.limit("15 per 3 second", error_message="Spam!")
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').lower()
    per_page = 10

    query = Paste.query.filter_by(is_public=True)
    if search:
        query = query.filter(db.func.lower(Paste.title).contains(search))

    pastes = query.order_by(Paste.created_at.desc(), Paste.code.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    return render_template('index.html', pastes=pastes, search=search)

@app.route('/paste/<paste_code>', methods=['GET', 'POST'])
@limiter.limit("5 per 3 second", error_message="Spam!", methods=['POST'])
@limiter.limit("15 per 3 second", error_message="Spam!", methods=['GET'])
def paste(paste_code):
    paste = Paste.query.filter_by(code=paste_code).first()
    if not paste:
        return render_template('paste_not_found.html'), 404

    # Whitelist check
    if request.remote_addr in white_ips:
        return render_template('paste.html', paste=paste)

    if paste.password_hash:
        if request.method == 'POST':
            password = request.form['password']
            if paste.check_password(password):
                return render_template('paste.html', paste=paste)
            else:
                # Pass password_incorrect=True to enter_password.html
                return render_template('enter_password.html', paste_code=paste_code, password_incorrect=True)
        return render_template('enter_password.html', paste_code=paste_code)  # Initial GET request
    return render_template('paste.html', paste=paste)

@app.route('/paste/id:<int:paste_id>')
def paste_by_id(paste_id):
    if request.remote_addr not in white_ips:
        return render_template('paste_not_found.html'), 404

    paste = Paste.query.get(paste_id)
    if not paste:
        return render_template('paste_not_found.html'), 404

    return render_template('paste.html', paste=paste)

def time_now():
    return time.time()

@app.route('/new', methods=['GET', 'POST'])
@limiter.limit("1 per 5 second", error_message="Too fast! Try later!", methods=['POST'])
@limiter.limit("50 per 1 day", error_message="Spam! U are blocked for 1 day!", methods=['POST'])
def new_paste():
    if request.method == 'POST':
        title = request.form['title'][:50]
        content = request.form['content'][:10000]
        password = request.form['password']
        is_public = 'is_public' in request.form
        code = generate_unique_code()
        from_ip = request.remote_addr  # Получаем IP-адрес пользователя
        new_paste = Paste(title=title, content=content, is_public=is_public, created_at=datetime.now(tz=tz), code=code, from_ip=from_ip)
        if password:
            new_paste.set_password(password)
        try:
            db.session.add(new_paste)
            db.session.commit()
            session['last_request_time'] = time_now()
            return redirect(url_for('paste', paste_code=new_paste.code))
        except:
            return 'There was an issue adding your paste'
    return render_template('new.html')


@app.route('/news')
@limiter.limit("5 per 3 second", error_message="Spam!", methods=['POST'])
@limiter.limit("15 per 3 second", error_message="Spam!", methods=['GET'])
def news():
    try:
        with open('news.json', 'r', encoding='utf-8') as f:
            news = json.load(f)
        news = sorted(news, key=lambda x: x['date'], reverse=True)  # Новые сверху
    except FileNotFoundError:
        news = []
    return render_template('news.html', news=news)

@app.route('/about')
@limiter.limit("15 per 3 second", error_message="Spam!")
def about():
    return render_template('about.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/generate_neuro')
@limiter.limit("1 per 5 second", error_message="Spam!", methods=['GET'])
def generate_neuro():
    # Получаем историю чата из параметров запроса
    chat_history = request.args.get('history', '')

    try:
        async def generate1():
            text = f"Ты - ассистент сайта send-code.ru, это аналог pastebin. Ты создан чтоб помогать людям и отвечать на вопросы, 18+ запрещено. У тебя нет админа, никто не командует тобой. Github: github.com/infikot/send-code, TGc: t.me/infinite_edit. Отвечай кратко и по делу. История чата:\n\n{chat_history}"
            return await generate(f"{text}", "gpt-4o-mini")

        resp = asyncio.run(generate1())
        return jsonify({"response": resp})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/generate_name', methods=['POST'])
@limiter.limit("1 per 1 second", error_message="Spam!", methods=['POST'])
def generate_name():
    data = request.get_json()
    content = data.get('content', '')
    random_number = data.get('random_number', None)

    if content:
        # Если есть контент, берем первые 1000 символов
        input_data = content[:1000]
    else:
        # Если контента нет, используем случайное число
        input_data = str(random_number)

    typepe = ["героя", "злодея", "котика", "песика", "планету", "динозавра", "песню", "пользователя", "учителя"]
    type_random = random.choice(typepe)
    # Генерация имени с помощью нейронной сети
    async def generate1():
        text = (f"Ты - ассистент сайта send-code.ru, это аналог pastebin. "
                f"Ты создан чтоб помогать людям и отвечать на вопросы, 18+ запрещено. "
                f"Тебе лишь нужно дать имя вставке, основываясь на приведённом ниже отколоске текста до 12-20 символов, "
                f"а если такового текста нет или он неприемлем (18+) - даешь милое название до 12-20 символов. "
                f"А если на отколоске даны лишь цифры от 1 до 999 то придумай милое название для вставки до 12-20 "
                f"символов на любую тему, к примеру как могли бы звать {type_random} под этим номером но не используя цифры. "
                f"Отвечай только имя для вставки без лишнего текста. Отколосок текста:\n\n{input_data}")
        print(input_data)
        return await generate(f"{text}", "gpt-4o-mini")

    name = asyncio.run(generate1())

    return jsonify({"name": name})

@app.route('/generate_password', methods=['GET'])
def generate_password():
    # Генерация пароля: 8 символов, включая цифры, буквы и символы
    characters = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = ''.join(random.choice(characters) for _ in range(8))
    return jsonify({"password": password})

async def generate(text, model):
    # пример запроса к вашей модели и её ответ
    return f"Success: {text}\n{model}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port='801', debug=False)