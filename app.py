from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pastes.db'
db = SQLAlchemy(app)


class Paste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    password_hash = db.Column(db.String(128))
    is_public = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Paste {self.id}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


print("nice")


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pastes = Paste.query.filter_by(is_public=True).order_by(Paste.created_at.desc()).paginate(page=page,
                                                                                              per_page=per_page,
                                                                                              error_out=False)
    return render_template('index.html', pastes=pastes)


@app.route('/paste/<int:paste_id>', methods=['GET', 'POST'])
def paste(paste_id):
    paste = Paste.query.get_or_404(paste_id)
    if paste.password_hash:
        if request.method == 'POST':
            password = request.form['password']
            if paste.check_password(password):
                return render_template('paste.html', paste=paste)
            else:
                flash('Incorrect password')
                return redirect(url_for('paste', paste_id=paste_id))
        return render_template('enter_password.html', paste_id=paste_id)
    return render_template('paste.html', paste=paste)


@app.route('/new', methods=['GET', 'POST'])
def new_paste():
    if 'last_request_time' in session:
        last_request_time = session['last_request_time']
        current_time = time.time()
        if current_time - last_request_time < 2:
            flash('You are doing that too much. Please wait a few seconds and try again.')
            return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        password = request.form['password']
        is_public = 'is_public' in request.form
        new_paste = Paste(title=title, content=content, is_public=is_public)
        if password:
            new_paste.set_password(password)
        try:
            db.session.add(new_paste)
            db.session.commit()
            session['last_request_time'] = time.time()
            return redirect(url_for('paste', paste_id=new_paste.id))
        except:
            return 'There was an issue adding your paste'
    return render_template('new_paste.html')


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port='80')