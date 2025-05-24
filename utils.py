import sqlite3

def format_vnd(amount):
    """Format a number in Vietnamese VND format with dots (e.g., 10000000 -> 10.000.000)."""
    amount_str = str(int(amount))  # Ensure integer for formatting
    length = len(amount_str)
    if length <= 3:
        return amount_str # 1.0
    
    result = []
    for i in range(length - 1, -1, -1):
        result.insert(0, amount_str[i])
        if i > 0 and (length - i) % 3 == 0:
            result.insert(0, '.')
    
    return ''.join(result)

def convert_to_vnd(amount, currency):
    """Convert amount from given currency to VND using fixed exchange rates."""
    exchange_rates = {
        'vnd': 1,
        'usd': 25000,
        'eur': 27000,
        'jpy': 170,
        'cny': 3500
    }
    currency = currency.lower()
    if currency not in exchange_rates:
        raise ValueError(f"Unsupported currency: {currency}")
    return amount * exchange_rates[currency]

def check_funds(category_amount, spend_amount):
    """Check if there are sufficient funds in the category."""
    return category_amount >= spend_amount

def check_unallocated(not_used, amount):
    """Check if there is enough unallocated money."""
    return not_used >= amount

def get_unallocated(cursor, user_id):
    """Calculate unallocated money (total salary - total category budgets)."""
    cursor.execute('SELECT SUM(amount) FROM salary WHERE user_id = ?', (user_id,))
    total_salary = cursor.fetchone()[0] or 0.0
    cursor.execute('SELECT SUM(amount) FROM categories WHERE user_id = ?', (user_id,))
    total_categories = cursor.fetchone()[0] or 0.0
    return total_salary - total_categories

def get_spending_by_category(cursor, user_id):
    """Extract total spending per category from spending table."""
    cursor.execute('''
        SELECT category, SUM(amount) FROM spending
        WHERE user_id = ?
        GROUP BY category
    ''', (user_id,))
    spending = {row[0]: row[1] for row in cursor.fetchall()}
    return spending