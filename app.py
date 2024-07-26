from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    try:
        conn = sqlite3.connect('d:/Uni Work/CS202/Banking Database/database/bankingDB.db')
        conn.row_factory = sqlite3.Row
        conn.commit()
        return conn
    except sqlite3.Error as e:
        raise Exception(f"Error connecting to the database: {e}")

@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        with get_db_connection() as conn:
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['email'] = email
            return redirect(url_for('home'))
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        firstName = request.form['firstName']
        lastName = request.form['lastName']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (firstName, lastName, email, password) VALUES (?, ?, ?, ?)', (firstName, lastName, email, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            return 'User already exists'
        conn.close()
        session['email'] = email
        return redirect(url_for('home'))
    return render_template('signup.html')

@app.route('/home')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/profile')
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))
    with get_db_connection() as conn:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
    return render_template('profile.html', email=session['email'], firstName=user['firstName'], lastName=user['lastName'])

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
