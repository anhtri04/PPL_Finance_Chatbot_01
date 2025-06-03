import spacy
from collections import Counter
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class Advisor:
    def __init__(self):
        try:
            # Load small English model for local NLP
            self.nlp = spacy.load("en_core_web_sm")
            logging.debug("Spacy model loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load spacy model: {str(e)}")
            raise

    def generate_advice(self, data):
        """Analyze spending data and generate financial advice."""
        logging.debug(f"Generating advice with data: {data}")
        if not data.get('actions'):
            logging.info("No actions to analyze")
            return "No financial activity to analyze yet. Try adding a salary or spending some money!"

        salary = data.get('salary', 0)
        not_used = data.get('not_used', 0)
        categories = data.get('categories', {})
        actions = data.get('actions', [])

        # Calculate spending by category
        category_spending = {cat: 0 for cat in categories}
        item_counts = Counter()
        for action in actions:
            try:
                if not isinstance(action, dict):
                    logging.warning(f"Skipping invalid action: {action}")
                    continue
                if action.get('description') == "Spent" and 'amount' in action and 'category' in action:
                    category = action['category']
                    amount = action['amount']
                    if category in category_spending:
                        category_spending[category] += amount
                    item = action.get('item', '').lower()
                    item_counts[item] += 1
            except Exception as e:
                logging.error(f"Error processing action: {action}, error: {str(e)}")
                continue

        # Analyze spending patterns
        advice = []

        # 1. Check for high spending in any category (>50% of salary)
        for category, amount in category_spending.items():
            if salary > 0 and amount / salary > 0.5:
                advice.append(
                    f"You're spending {amount / salary * 100:.1f}% of your salary ({amount} VND) on {category}. "
                    f"Consider reducing this to save more."
                )

        # 2. Check for high unallocated money (>70% of salary)
        if salary > 0 and not_used / salary > 0.7:
            advice.append(
                f"You have {not_used / salary * 100:.1f}% of your salary ({not_used} VND) unallocated. "
                f"Consider allocating more to savings or investment categories."
            )

        # 3. Highlight frequent spending items
        frequent_items = [item for item, count in item_counts.items() if count > 2]
        if frequent_items:
            advice.append(
                f"You frequently spend on {', '.join(frequent_items)}. "
                f"Review if these are essential or if you can cut back."
            )

        # 4. General advice if spending is balanced
        if not advice:
            total_spent = sum(category_spending.values())
            if salary > 0 and total_spent / salary < 0.3:
                advice.append(
                    "Your spending is quite conservative, which is great! "
                    "Consider investing some of your unallocated funds for future growth."
                )
            else:
                advice.append(
                    "Your spending seems balanced. Keep tracking your expenses to stay on top of your finances!"
                )

        # Process spending descriptions with spaCy for additional insights
        spend_descriptions = [
            action.get('item', '') for action in actions
            if isinstance(action, dict) and action.get('description') == "Spent" and 'item' in action
        ]
        if spend_descriptions:
            try:
                doc = self.nlp(" ".join(spend_descriptions))
                entities = [ent.text for ent in doc.ents if ent.label_ in ["PRODUCT", "MONEY"]]
                if entities:
                    advice.append(
                        f"You've mentioned items like {', '.join(entities)}. "
                        f"Ensure these purchases align with your financial goals."
                    )
            except Exception as e:
                logging.error(f"Error processing spaCy descriptions: {str(e)}")

        return " ".join(advice) if advice else "No specific advice at this time. Keep managing your finances wisely!"