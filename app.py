from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string  
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "database", "bankingDB.db")
        
        # Check if the database file exists
        if not os.path.exists(db_path):
            raise Exception(f"Database file not found at {db_path}")
        
        conn = sqlite3.connect(db_path)
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
        
        if len(email) < 3 or len(password) < 3:
            return "<script>alert('Email and password must be at least 3 characters long.'); window.location.href='/signup';</script>"
        
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            # Generate random banking number
            banking_number = generate_banking_number()
            
            # Insert user into users table
            conn.execute('INSERT INTO users (firstName, lastName, email, password, bankingNumber, totalMoney) VALUES (?, ?, ?, ?, ?, ?)', (firstName, lastName, email, hashed_password, banking_number, 100))
            
            # Insert user into userBank table
            conn.execute('INSERT INTO userBank (bankingNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', (banking_number, datetime.now().strftime('%d-%m-%Y'), 'Initial Deposit', 100))
            
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "<script>alert('User already exists'); window.location.href='/signup';</script>"
        
        conn.close()
        session['email'] = email
        return "<script>alert('You have created your account'); window.location.href='/login';</script>"
    return render_template('signup.html')

def generate_banking_number():
    # Generate a random 10-digit banking number
    banking_number = ''.join(random.choices(string.digits, k=10))
    return banking_number

@app.route('/home')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/bank', methods=['GET', 'POST'])
def bank():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    with get_db_connection() as conn:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
        userBank = conn.execute('SELECT * FROM userBank WHERE bankingNumber = ?', (user['bankingNumber'],)).fetchall()
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            if 'amount' not in data or 'transaction_type' not in data:
                return {'success': False, 'message': 'Invalid request: amount or transaction_type is missing'}, 400
            
            amount = int(data['amount'])
            transaction_type = data['transaction_type']
            
            if transaction_type == 'Deposit':
                new_total_money = user['totalMoney'] + amount
            elif transaction_type == 'Withdraw':
                new_total_money = user['totalMoney'] - amount
            else:
                return {'success': False, 'message': 'Invalid transaction type'}, 400
            
            with get_db_connection() as conn:
                conn.execute('UPDATE users SET totalMoney = ? WHERE email = ?', (new_total_money, session['email']))
                conn.commit()
                
                # Insert new transaction record into userBank table
                conn.execute('INSERT INTO userBank (bankingNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', 
                            (user['bankingNumber'], datetime.now().strftime('%d-%m-%Y'), transaction_type, amount))
                conn.commit()
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'message': str(e)}, 500

    return render_template('bank.html', totalMoney=user['totalMoney'], bankingNumber=user['bankingNumber'], transactions=userBank)

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
    app.secret_key = 'your_secret_key'
    app.run(debug=True)