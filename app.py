from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "database", "bankingDB.db")
        
        if not os.path.exists(db_path):
            raise Exception(f"Database file not found at {db_path}")
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.commit()
        return conn
    except sqlite3.Error as e:
        raise Exception(f"Error connecting to the database: {e}")
    except Exception as e:
        raise Exception(f"General error: {e}")

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    # Extract form data
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    message = request.form.get('message')
    
    # For demonstration, let's just print the data to the console
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Phone: {phone}")
    print(f"Message: {message}")

    # You could process the data, save it to the database, or send an email here

    return redirect(url_for('contact'))  # Redirect back to the contact page or another page

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
            # Insert user into users table
            conn.execute('INSERT INTO users (firstName, lastName, email, password) VALUES (?, ?, ?, ?)', (firstName, lastName, email, hashed_password))
            
            # Generate random banking number and create an account
            banking_number = generate_banking_number()
            conn.execute('INSERT INTO accounts (user_id, accountNumber, accountBalance) VALUES ((SELECT user_id FROM users WHERE email = ?), ?, ?)', (email, banking_number, 100))
            
            # Insert initial transaction into transactions table
            conn.execute('INSERT INTO userBank (accountNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', (banking_number, datetime.now().strftime('%d-%m-%Y'), 'Initial Deposit', 100))
            
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "<script>alert('User already exists'); window.location.href='/signup';</script>"
        
        conn.close()
        session['email'] = email
        return "<script>alert('You have created your account'); window.location.href='/login';</script>"
    return render_template('signup.html')

@app.route('/my_accounts')
def my_accounts():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401
    
    email = session['email']
    conn = get_db_connection()
    accounts = conn.execute('SELECT * FROM accounts WHERE user_id = (SELECT user_id FROM users WHERE email = ?)', (email,)).fetchall()
    conn.close()
    return jsonify({'success': True, 'accounts': [dict(account) for account in accounts]})

@app.route('/create_account', methods=['POST'])
def create_account():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    email = session['email']
    conn = get_db_connection()
    banking_number = generate_banking_number()

    try:
        conn.execute('INSERT INTO accounts (user_id, accountNumber, accountBalance) VALUES ((SELECT user_id FROM users WHERE email = ?), ?, ?)', (email, banking_number, 0))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


def generate_banking_number():
    # Generate a random 10-digit banking number
    banking_number = int(''.join(random.choices(string.digits, k=10)))
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
    
    conn = get_db_connection()
    
    if request.method == 'GET':
        user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
        accounts = conn.execute('SELECT * FROM accounts WHERE user_id = ?', (user['user_id'],)).fetchall()
        transactions = conn.execute('SELECT * FROM userBank WHERE accountNumber IN (SELECT accountNumber FROM accounts WHERE user_id = ?)', (user['user_id'],)).fetchall()
        conn.close()
        return render_template('bank.html', accounts=accounts, transactions=transactions)

    if request.method == 'POST':
        data = request.get_json()
        if 'amount' not in data or 'transaction_type' not in data or 'accountNumber' not in data:
            return {'success': False, 'message': 'Invalid request: amount, transaction_type, or accountNumber is missing'}, 400
        
        amount = int(data['amount'])
        transaction_type = data['transaction_type']
        accountNumber = data['accountNumber']
        
        # Fetch current balance
        account = conn.execute('SELECT * FROM accounts WHERE accountNumber = ?', (accountNumber,)).fetchone()
        if not account:
            return {'success': False, 'message': 'Invalid account number'}, 400
        
        if transaction_type == 'Deposit':
            new_balance = account['accountBalance'] + amount
        elif transaction_type == 'Withdraw':
            if amount > account['accountBalance']:
                return {'success': False, 'message': 'Insufficient funds'}, 400
            new_balance = account['accountBalance'] - amount
        else:
            return {'success': False, 'message': 'Invalid transaction type'}, 400
        
        conn.execute('UPDATE accounts SET accountBalance = ? WHERE accountNumber = ?', (new_balance, accountNumber))
        conn.commit()
        
        # Insert new transaction record into transactions table
        conn.execute('INSERT INTO userBank (accountNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', 
                    (accountNumber, datetime.now().strftime('%d-%m-%Y'), transaction_type, amount))
        conn.commit()
        conn.close()
        
        return {'success': True}


@app.route('/profile')
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    with get_db_connection() as conn:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
    
    return render_template('profile.html', email=session['email'], firstName=user['firstName'], lastName=user['lastName'])

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
