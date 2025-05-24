
from utils import format_vnd

def generate_spending_graph(spending):
    """Generate a spending graph configuration."""
    labels = list(spending.keys())
    data = list(spending.values())
    
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Spending by Category (VND)",
                "data": data,
                "backgroundColor": [
                    "#4CAF50", "#2196F3", "#FF9800", "#F44336", "#9C27B0"
                ],
                "borderColor": [
                    "#388E3C", "#1976D2", "#F57C00", "#D32F2F", "#7B1FA2"
                ],
                "borderWidth": 1
            }] # 1.0
        },
        "options": {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {
                        "display": True,
                        "text": "Amount (VND)"
                    },
                    "ticks": {
                        "callback": f"function(value) {{ return '{format_vnd(values())} VND'; }}"
                    }
                },
                "x": {
                    "title": {
                        "display": True,
                        "text": "Category"
                    }
                }
            },
            "plugins": {
                "legend": {
                    "display": True
                },
                "title": {
                    "display": True,
                    "text": "Spending by Category"
                }
            }
        }
    }
    
    # In a real app, this would be rendered in a UI. For now, simulate output.
    print("Chart generated (simulated). Data:", chart_config)
