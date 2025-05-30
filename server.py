from flask import Flask, request, jsonify, send_file
import sqlite3
from datetime import datetime
import json
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'CompiledFiles'))
from advisor import Advisor
from parser import FinanceParser
from utils import format_vnd, convert_to_vnd, check_funds, check_unallocated, get_unallocated, get_spending_by_category
from chatbot import init_db, add_user

app = Flask(__name__)

# Initialize components
advisor = Advisor()
parser = FinanceParser()

def get_db_connection():
    """Create a new database connection for each request."""
    conn = sqlite3.connect('finance_chatbot.db')
    cursor = conn.cursor()
    return conn, cursor

def close_db_connection(conn):
    """Close the database connection."""
    if conn:
        conn.commit()
        conn.close()

@app.route('/')
def serve_index():
    """Serve the index.html file for the root URL."""
    return send_file('index.html')

@app.route('/api/init', methods=['GET'])
def init_database():
    """Initialize the database and add default user."""
    try:
        conn, cursor = get_db_connection()
        init_db()  # Create tables
        user_id = add_user(cursor, conn, "TestUser")
        close_db_connection(conn)
        return jsonify({'user_id': user_id, 'message': 'Database initialized and user added.'})
    except Exception as e:
        return jsonify({'error': f'Failed to initialize database: {str(e)}'}), 500

def get_financial_data(cursor, user_id):
    """Retrieve financial overview and categories for the UI."""
    total_salary = cursor.execute('SELECT SUM(amount) FROM salary WHERE user_id = ?', (user_id,)).fetchone()[0] or 0
    unallocated = get_unallocated(cursor, user_id)
    spending = get_spending_by_category(cursor, user_id)
    total_spent = sum(spending.values())
    categories = [{'category': c[0], 'amount': format_vnd(c[1])} for c in cursor.execute('SELECT category, amount FROM categories WHERE user_id = ?', (user_id,)).fetchall()]
    return {
        'total_salary': format_vnd(total_salary),
        'unallocated': format_vnd(unallocated),
        'total_spent': format_vnd(total_spent),
        'categories': categories,
        'spending': {'labels': list(spending.keys()), 'data': list(spending.values())}
    }

@app.route('/api/process', methods=['POST'])
def process_input():
    conn, cursor = get_db_connection()
    user_id = add_user(cursor, conn, "TestUser")  # Ensure user exists
    try:
        data = request.get_json()
        user_input = data.get('input', '').strip()
        if not user_input:
            close_db_connection(conn)
            return jsonify({'response': 'Please provide an input.', 'financial_data': get_financial_data(cursor, user_id)}), 400

        intents = parser.parse(user_input.lower())
        responses = []
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for intent in intents:
            if intent['type'] == 'salary':
                amount_vnd = int(convert_to_vnd(intent['amount'], intent['currency']))
                cursor.execute('INSERT INTO salary (user_id, amount, original_amount, currency, date) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, amount_vnd, intent['amount'], intent['currency'], date))
                cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                             (user_id, "Spent", json.dumps({
                                 'amount': amount_vnd,
                                 'original_amount': intent['amount'],
                                 'currency': intent['currency']
                             }), date))
                responses.append(f"Added {format_vnd(amount_vnd)} VND ({format_vnd(intent['amount'])} {intent['currency'].upper()}) to salary. Please specify spending categories.")

            elif intent['type'] == 'category':
                total_amount = 0
                categories_vnd = []
                for category, amount, orig_amount, currency in intent['categories']:
                    amount_vnd = int(convert_to_vnd(amount, currency))
                    categories_vnd.append((category.capitalize(), amount_vnd, orig_amount, currency))
                    total_amount += amount_vnd
                if check_unallocated(get_unallocated(cursor, user_id), total_amount):
                    for category, amount_vnd, orig_amount, currency in categories_vnd:
                        cursor.execute('INSERT INTO categories (user_id, category, amount) VALUES (?, ?, ?) ON CONFLICT(user_id, category) DO UPDATE SET amount = amount + ?', 
                                     (user_id, category, amount_vnd, amount_vnd))
                        cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                                     (user_id, f"Added category {category}", json.dumps({
                                         'category': category,
                                         'amount': amount_vnd,
                                         'original_amount': orig_amount,
                                         'currency': currency
                                     }), date))
                    responses.append(f"Categories added. Unallocated money: {format_vnd(get_unallocated(cursor, user_id))} VND")
                else:
                    responses.append("Not enough unallocated money to add these categories.")

            elif intent['type'] == 'spend':
                amount_vnd = int(convert_to_vnd(intent['amount'], intent['currency']))
                category = intent['category'].capitalize()
                result = cursor.execute('SELECT amount FROM categories WHERE user_id = ? AND category = ?', (user_id, category)).fetchone()
                if result and check_funds(result[0], amount_vnd):
                    cursor.execute('UPDATE categories SET amount = amount - ? WHERE user_id = ? AND category = ?', 
                                 (amount_vnd, user_id, category))
                    cursor.execute('INSERT INTO spending (user_id, amount, original_amount, currency, item, category, date) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                                 (user_id, amount_vnd, intent['amount'], intent['currency'], intent['item'], category, date))
                    cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                                 (user_id, "Spent", json.dumps({
                                     'amount': amount_vnd,
                                     'original_amount': intent['amount'],
                                     'currency': intent['currency'],
                                     'item': intent['item'],
                                     'category': category
                                 }), date))
                    responses.append(f"Enough money. Proceeding with {intent['item']} for {format_vnd(amount_vnd)} VND ({format_vnd(intent['amount'])} {intent['currency'].upper()}).")
                else:
                    responses.append(f"Insufficient funds in {category} or category does not exist.")

            elif intent['type'] == 'modify_category':
                category = intent['category'].capitalize()
                amount_vnd = int(convert_to_vnd(intent['amount'], intent['currency']))
                result = cursor.execute('SELECT amount FROM categories WHERE user_id = ? AND category = ?', (user_id, category)).fetchone()
                if result:
                    old_amount = result[0]
                    unallocated = get_unallocated(cursor, user_id) + old_amount
                    if check_unallocated(unallocated, amount_vnd):
                        cursor.execute('UPDATE categories SET amount = ? WHERE user_id = ? AND category = ?', 
                                     (amount_vnd, user_id, category))
                        cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                                     (user_id, f"Modified category {category}", json.dumps({
                                         'category': category,
                                         'amount': amount_vnd,
                                         'original_amount': intent['amount'],
                                         'currency': intent['currency']
                                     }), date))
                        responses.append(f"Category {category} modified to {format_vnd(amount_vnd)} VND ({format_vnd(intent['amount'])} {intent['currency'].upper()}).")
                    else:
                        responses.append("Not enough unallocated money to modify category.")
                else:
                    responses.append(f"Category {category} does not exist.")

            elif intent['type'] == 'delete_category':
                category = intent['category'].capitalize()
                result = cursor.execute('SELECT amount FROM categories WHERE user_id = ? AND category = ?', (user_id, category)).fetchone()
                if result:
                    cursor.execute('DELETE FROM categories WHERE user_id = ? AND category = ?', (user_id, category))
                    cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                                 (user_id, f"Deleted category {category}", json.dumps({'category': category}), date))
                    responses.append(f"Category {category} deleted.")
                else:
                    responses.append(f"Category {category} does not exist.")

            elif intent['type'] == 'reset':
                cursor.execute('DELETE FROM salary WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM categories WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM spending WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM actions WHERE user_id = ?', (user_id,))
                cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                             (user_id, "Reset all data", json.dumps({}), date))
                responses.append("All data reset.")

            elif intent['type'] == 'analyze':
                data = {
                    'salary': cursor.execute('SELECT SUM(amount) FROM salary WHERE user_id = ?', (user_id,)).fetchone()[0] or 0,
                    'not_used': get_unallocated(cursor, user_id),
                    'categories': {c[0]: c[1] for c in cursor.execute('SELECT category, amount FROM categories WHERE user_id = ?', (user_id,)).fetchall()},
                    'actions': [json.loads(a[0]) for a in cursor.execute('SELECT details FROM actions WHERE user_id = ?', (user_id,)).fetchall()]
                }
                advice = advisor.generate_advice(data)
                cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                             (user_id, "Provided advice", json.dumps({'advice': advice}), date))
                responses.append(advice)

            elif intent['type'] == 'graph':
                spending = get_spending_by_category(cursor, user_id)
                if spending:
                    cursor.execute('INSERT INTO actions (user_id, description, details, date) VALUES (?, ?, ?, ?)', 
                                 (user_id, "Displayed spending graph", json.dumps({}), date))
                    responses.append("Displaying spending graph for your categories.")
                else:
                    responses.append("No spending data to graph yet.")

        conn.commit()
        financial_data = get_financial_data(cursor, user_id)
        close_db_connection(conn)
        return jsonify({'response': '\n'.join(responses), 'financial_data': financial_data})

    except Exception as e:
        close_db_connection(conn)
        return jsonify({'response': f"Error processing input: {str(e)}", 'financial_data': get_financial_data(cursor, user_id)}), 500

@app.route('/api/financial_data', methods=['GET'])
def get_financial_data_endpoint():
    conn, cursor = get_db_connection()
    try:
        user_id = add_user(cursor, conn, "TestUser")
        financial_data = get_financial_data(cursor, user_id)
        close_db_connection(conn)
        return jsonify(financial_data)
    except Exception as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to retrieve financial data: {str(e)}'}), 500

if __name__ == '__main__':
    # Initialize database and user
    conn, cursor = get_db_connection()
    init_db()
    add_user(cursor, conn, "TestUser")
    close_db_connection(conn)
    # Run Flask server without debug mode
    app.run(host='0.0.0.0', port=5000)