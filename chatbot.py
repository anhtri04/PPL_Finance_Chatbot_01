import sqlite3
from datetime import datetime
import json
from parser import FinanceParser
from utils import format_vnd, convert_to_vnd, check_funds, check_unallocated, get_unallocated, get_spending_by_category
from advisor import Advisor
from visualizer import generate_spending_graph

def init_db():
    """Initialize SQLite database and create tables."""
    conn = sqlite3.connect('finance_chatbot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salary (
            salary_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            original_amount REAL NOT NULL,
            currency TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            UNIQUE(user_id, category)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spending (
            spending_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            original_amount REAL NOT NULL,
            currency TEXT NOT NULL,
            item TEXT NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            description TEXT NOT NULL,
            details TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    return conn, cursor
 
def add_user(cursor, conn, name):
    """Add a user to the database and return their user_id."""
    try:
        cursor.execute('INSERT INTO users (name) VALUES (?)', (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # User already exists
    cursor.execute('SELECT user_id FROM users WHERE name = ?', (name,))
    return cursor.fetchone()[0]

def run():
    conn, cursor = init_db()
    parser = FinanceParser()
    advisor = Advisor()
    
    # Add a default user for simplicity
    user_name = "TestUser"
    user_id = add_user(cursor, conn, user_name)
    
    print("Hello, User. I am your finance chatbot. What can I do for you today?")
    print("Examples: 'I have 10000000 VND this month', 'I want 5000000 VND for Food, 2000000 VND for Hobby', 'I spent 50000 VND for pho in Food', 'show graph', 'give advice'")
    
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ['exit', 'quit']:
            break
        
        parse_input = user_input.lower()
        try:
            intents = parser.parse(parse_input)
            for intent in intents:
                date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if intent['type'] == 'salary':
                    original_amount = intent['amount']
                    currency = intent['currency']
                    amount_vnd = int(convert_to_vnd(original_amount, currency))
                    cursor.execute('''
                        INSERT INTO salary (user_id, amount, original_amount, currency, date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, amount_vnd, original_amount, currency, date))
                    cursor.execute('''
                        INSERT INTO actions (user_id, description, details, date)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, "Spent", json.dumps({
                        'amount': amount_vnd,
                        'original_amount': original_amount,
                        'currency': currency
                    }), date))
                    conn.commit()
                    print(f"Chatbot: Added {format_vnd(amount_vnd)} VND ({format_vnd(original_amount)} {currency.upper()}) to salary. Please specify spending categories.")
                
                elif intent['type'] == 'category':
                    categories_vnd = []
                    total_category_amount = 0
                    for category, amount, orig_amount, currency in intent['categories']:
                        amount_vnd = int(convert_to_vnd(amount, currency))
                        categories_vnd.append((category.capitalize(), amount_vnd, orig_amount, currency))
                        total_category_amount += amount_vnd
                    
                    if check_unallocated(get_unallocated(cursor, user_id), total_category_amount):
                        for category, amount_vnd, orig_amount, currency in categories_vnd:
                            cursor.execute('''
                                INSERT INTO categories (user_id, category, amount)
                                VALUES (?, ?, ?)
                                ON CONFLICT(user_id, category) DO UPDATE SET amount = amount + ?
                            ''', (user_id, category, amount_vnd, amount_vnd))
                            cursor.execute('''
                                INSERT INTO actions (user_id, description, details, date)
                                VALUES (?, ?, ?, ?)
                            ''', (user_id, f"Added category {category}", json.dumps({
                                'category': category,
                                'amount': amount_vnd,
                                'original_amount': orig_amount,
                                'currency': currency
                            }), date))
                        conn.commit()   #merge 1.0
                        print(f"Chatbot: Categories added. Unallocated money: {format_vnd(get_unallocated(cursor, user_id))} VND")
                    else:
                        print("Chatbot: Not enough unallocated money to add these categories.")
                
                elif intent['type'] == 'spend':
                    original_amount = intent['amount']
                    currency = intent['currency']
                    amount_vnd = int(convert_to_vnd(original_amount, currency))
                    item = intent['item']
                    category = intent['category'].capitalize()
                    cursor.execute('SELECT amount FROM categories WHERE user_id = ? AND category = ?', (user_id, category))
                    result = cursor.fetchone()
                    if result and check_funds(result[0], amount_vnd):
                        cursor.execute('''
                            UPDATE categories SET amount = amount - ? WHERE user_id = ? AND category = ?
                        ''', (amount_vnd, user_id, category))
                        cursor.execute('''
                            INSERT INTO spending (user_id, amount, original_amount, currency, item, category, date)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (user_id, amount_vnd, original_amount, currency, item, category, date))
                        cursor.execute('''
                            INSERT INTO actions (user_id, description, details, date)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, "Spent", json.dumps({
                            'amount': amount_vnd,
                            'original_amount': original_amount,
                            'currency': currency,
                            'item': item,
                            'category': category
                        }), date))
                        conn.commit()
                        print(f"Chatbot: Enough money. Proceeding with {item} for {format_vnd(amount_vnd)} VND ({format_vnd(original_amount)} {currency.upper()}).")
                    else:
                        print(f"Chatbot: Insufficient funds in {category} or category does not exist.")
                
                elif intent['type'] == 'modify_category':
                    category = intent['category'].capitalize()
                    original_amount = intent['amount']
                    currency = intent['currency']
                    new_amount_vnd = int(convert_to_vnd(original_amount, currency))
                    cursor.execute('SELECT amount FROM categories WHERE user_id = ? AND category = ?', (user_id, category))
                    result = cursor.fetchone()
                    if result:
                        old_amount = result[0]
                        unallocated = get_unallocated(cursor, user_id) + old_amount
                        if check_unallocated(unallocated, new_amount_vnd):
                            cursor.execute('''
                                UPDATE categories SET amount = ? WHERE user_id = ? AND category = ?
                            ''', (new_amount_vnd, user_id, category))
                            cursor.execute('''
                                INSERT INTO actions (user_id, description, details, date)
                                VALUES (?, ?, ?, ?)
                            ''', (user_id, f"Modified category {category}", json.dumps({
                                'category': category,
                                'amount': new_amount_vnd,
                                'original_amount': original_amount,
                                'currency': currency
                            }), date))
                            conn.commit()
                            print(f"Chatbot: Category {category} modified to {format_vnd(new_amount_vnd)} VND ({format_vnd(original_amount)} {currency.upper()}).")
                        else:
                            print("Chatbot: Not enough unallocated money to modify category.")
                    else:
                        print(f"Chatbot: Category {category} does not exist.")
                
                elif intent['type'] == 'delete_category':
                    category = intent['category'].capitalize()
                    cursor.execute('SELECT amount FROM categories WHERE user_id = ? AND category = ?', (user_id, category))
                    result = cursor.fetchone()
                    if result:
                        cursor.execute('''
                            DELETE FROM categories WHERE user_id = ? AND category = ?
                        ''', (user_id, category))
                        cursor.execute('''
                            INSERT INTO actions (user_id, description, details, date)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, f"Deleted category {category}", json.dumps({
                            'category': category
                        }), date))
                        conn.commit()
                        print(f"Chatbot: Category {category} deleted.")
                    else:
                        print(f"Chatbot: Category {category} does not exist.")
                
                elif intent['type'] == 'reset':
                    cursor.execute('DELETE FROM salary WHERE user_id = ?', (user_id,))
                    cursor.execute('DELETE FROM categories WHERE user_id = ?', (user_id,))
                    cursor.execute('DELETE FROM spending WHERE user_id = ?', (user_id,))
                    cursor.execute('DELETE FROM actions WHERE user_id = ?', (user_id,))
                    cursor.execute('''
                        INSERT INTO actions (user_id, description, details, date)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, "Reset all data", json.dumps({}), date))
                    conn.commit()
                    print("Chatbot: All data reset.")
                
                elif intent['type'] == 'analyze':
                    data = {
                        'salary': get_unallocated(cursor, user_id) + sum(c[0] for c in cursor.execute('SELECT amount FROM categories WHERE user_id = ?', (user_id,)).fetchall()),
                        'not_used': get_unallocated(cursor, user_id),
                        'categories': {c[0]: c[1] for c in cursor.execute('SELECT category, amount FROM categories WHERE user_id = ?', (user_id,)).fetchall()},
                        'actions': [json.loads(a[0]) for a in cursor.execute('SELECT details FROM actions WHERE user_id = ?', (user_id,)).fetchall()]
                    }
                    advice = advisor.generate_advice(data)
                    cursor.execute('''
                        INSERT INTO actions (user_id, description, details, date)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, "Provided advice", json.dumps({'advice': advice}), date))
                    conn.commit()
                    print(f"Chatbot: {advice}")
                
                elif intent['type'] == 'graph':
                    spending = get_spending_by_category(cursor, user_id)
                    if spending:
                        generate_spending_graph(spending)
                        cursor.execute('''
                            INSERT INTO actions (user_id, description, details, date)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, "Displayed spending graph", json.dumps({}), date))
                        conn.commit()
                        print(f"Chatbot: Displaying spending graph for your categories.")
                    else:
                        print(f"Chatbot: No spending data to graph yet.")
        
        except Exception as e:
            print(f"Chatbot: Error processing input: {str(e)}")
    
    conn.close()

if __name__ == "__main__":
    run()
