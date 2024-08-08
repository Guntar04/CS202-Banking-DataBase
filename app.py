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
    """Establishes and returns a connection to the SQLite database."""
    try:
        # Build the path to the database file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "database", "bankingDB.db")
        
        # Check if the database file exists
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at {db_path}")
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise RuntimeError(f"Error connecting to the database: {e}")
    except Exception as e:
        raise RuntimeError(f"General error: {e}")

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    """Handles contact form submissions."""
    # Extract form data
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    message = request.form.get('message')
    
    # For demonstration, print the data to the console
    print(f"Name: {name}, Email: {email}, Phone: {phone}, Message: {message}")

    return redirect(url_for('contact'))

@app.route('/')
def index():
    """Redirects user to home or login based on session status."""
    if 'email' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
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
    """Handles user registration."""
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
            conn.execute('INSERT INTO users (firstName, lastName, email, password) VALUES (?, ?, ?, ?)', 
                         (firstName, lastName, email, hashed_password))
            
            # Generate random banking number and create an account
            banking_number = generate_banking_number()
            conn.execute('INSERT INTO accounts (user_id, accountNumber, accountBalance) VALUES ((SELECT user_id FROM users WHERE email = ?), ?, ?)', 
                         (email, banking_number, 100))
            
            # Insert initial transaction into transactions table
            conn.execute('INSERT INTO userBank (accountNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', 
                         (banking_number, datetime.now().strftime('%d-%m-%Y'), 'Initial Deposit', 100))
            
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
    """Returns a list of accounts for the logged-in user."""
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401
    
    email = session['email']
    conn = get_db_connection()
    accounts = conn.execute('SELECT * FROM accounts WHERE user_id = (SELECT user_id FROM users WHERE email = ?)', 
                           (email,)).fetchall()
    conn.close()
    
    return jsonify({'success': True, 'accounts': [dict(account) for account in accounts]})

@app.route('/create_account', methods=['POST'])
def create_account():
    """Creates a new account for the logged-in user."""
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    email = session['email']
    conn = get_db_connection()
    banking_number = generate_banking_number()

    try:
        conn.execute('INSERT INTO accounts (user_id, accountNumber, accountBalance) VALUES ((SELECT user_id FROM users WHERE email = ?), ?, ?)', 
                     (email, banking_number, 0))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

def generate_banking_number():
    """Generates a random 10-digit banking number."""
    return int(''.join(random.choices(string.digits, k=10)))

@app.route('/home')
def home():
    """Renders the home page for logged-in users."""
    if 'email' not in session:
        return redirect(url_for('login'))
    
    return render_template('home.html')

@app.route('/bank', methods=['GET', 'POST'])
def bank():
    """Handles banking operations including viewing balances and transactions."""
    if 'email' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    if request.method == 'GET':
        user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
        accounts = conn.execute('SELECT * FROM accounts WHERE user_id = ?', (user['user_id'],)).fetchall()
        transactions = conn.execute('SELECT * FROM userBank WHERE accountNumber IN (SELECT accountNumber FROM accounts WHERE user_id = ?)', 
                                    (user['user_id'],)).fetchall()
        account_balance = sum(account['accountBalance'] for account in accounts)  # Compute total balance
        conn.close()
        
        return render_template('bank.html', accounts=accounts, transactions=transactions, accountBalance=account_balance)

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
    
@app.route('/get_transactions')
def get_transactions():
    """Returns the list of transactions for the logged-in user."""
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
    transactions = conn.execute('SELECT * FROM userBank WHERE accountNumber IN (SELECT accountNumber FROM accounts WHERE user_id = ?)', 
                                (user['user_id'],)).fetchall()
    conn.close()
    
    return jsonify({'success': True, 'transactions': [dict(transaction) for transaction in transactions]})

@app.route('/transfer_funds', methods=['POST'])
def transfer_funds():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    data = request.get_json()
    from_account = data.get('fromAccount')
    to_account = data.get('toAccount')
    amount = float(data.get('amount'))

    if not from_account or not to_account or not amount:
        return jsonify({'success': False, 'message': 'Invalid input'}), 400

    try:
        conn = get_db_connection()
        conn.execute('BEGIN')

        from_account_balance = conn.execute('SELECT accountBalance FROM accounts WHERE accountNumber = ?', (from_account,)).fetchone()
        to_account_balance = conn.execute('SELECT accountBalance FROM accounts WHERE accountNumber = ?', (to_account,)).fetchone()

        if not from_account_balance or not to_account_balance:
            return jsonify({'success': False, 'message': 'One or both accounts not found'}), 404

        if from_account_balance['accountBalance'] < amount:
            return jsonify({'success': False, 'message': 'Insufficient funds in from account'}), 400

        new_from_balance = from_account_balance['accountBalance'] - amount
        new_to_balance = to_account_balance['accountBalance'] + amount

        conn.execute('UPDATE accounts SET accountBalance = ? WHERE accountNumber = ?', (new_from_balance, from_account))
        conn.execute('UPDATE accounts SET accountBalance = ? WHERE accountNumber = ?', (new_to_balance, to_account))

        trans_date = datetime.now().strftime('%d-%m-%Y')
        conn.execute('INSERT INTO userBank (accountNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', (from_account, trans_date, 'Transfer Out', -amount))
        conn.execute('INSERT INTO userBank (accountNumber, transDate, transType, transAmount) VALUES (?, ?, ?, ?)', (to_account, trans_date, 'Transfer In', amount))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    if request.method == 'POST':
        # Handle profile update
        firstName = request.form['firstName']
        lastName = request.form['lastName']
        email = request.form['email']

        conn.execute('UPDATE users SET firstName = ?, lastName = ?, email = ? WHERE email = ?', 
                     (firstName, lastName, email, session['email']))
        conn.commit()
        conn.close()

        # Update session email if it was changed
        session['email'] = email

        return redirect(url_for('profile'))

    else:
        # Display profile
        user = conn.execute('SELECT * FROM users WHERE email = ?', (session['email'],)).fetchone()
        conn.close()
        return render_template('profile.html', email=session['email'], firstName=user['firstName'], lastName=user['lastName'])

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    """Logs out the user by clearing the session."""
    session.pop('email', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
