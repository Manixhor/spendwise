"""
Spending coach — generates contextual messages based on spend percentage.
Also fetches a dad joke from icanhazdadjoke.com to lighten the mood.
"""

import random
import urllib.request
import urllib.error


# ── Message banks ─────────────────────────────────────────

EXCELLENT = [  # < 30% spent
    "You're basically a savings ninja. 🥷 Your wallet is thriving.",
    "Under 30% spent? You're not just saving money — you're collecting future freedom.",
    "Your bank account is doing a happy dance right now. Keep it up! 💃",
    "Spending less than 30%? You're playing financial chess while others play checkers.",
    "Your future self just sent a thank-you note. Seriously, this is impressive.",
]

GOOD = [  # 30–50% spent
    "Solid work — you're in the green zone. Your budget is well under control. 🌿",
    "30–50% spent and still going strong. You've got this budget thing figured out.",
    "You're spending wisely. A little treat here and there won't hurt — you've earned it.",
    "Balanced and in control. That's the sweet spot most people never find.",
    "Your spending habits are healthier than most people's diets. Well done. 🥗",
]

WARNING = [  # 50–75% spent
    "Halfway through your budget already? Time to pump the brakes a little. 🚦",
    "You're at the halfway mark. The finish line is savings — don't spend it all before you get there.",
    "50–75% in. Still manageable, but now's the time to be intentional with every rupee.",
    "Your wallet is sending subtle SOS signals. Maybe skip that extra coffee today? ☕",
    "You're in the yellow zone. Not an emergency, but worth a second look at your spending.",
]

HIGH = [  # 75–90% spent
    "Whoa — 75–90% of your budget is gone. Your savings account is giving you the silent treatment. 😶",
    "Your budget is on life support. Time to put the credit card in the freezer. Literally.",
    "At this rate, your wallet will need therapy. Let's slow down and breathe. 💸",
    "You've spent most of your budget. The good news? You still have time to course-correct.",
    "Your money is leaving faster than a Netflix series gets cancelled. Time to pause. 📺",
]

CRITICAL = [  # > 90% spent
    "Budget almost gone. Your savings account is crying in a corner. 😭 Time to stop.",
    "You've crossed into the danger zone. Every purchase from here is borrowing from future you.",
    "Over 90% spent. Your wallet just filed a missing persons report on itself.",
    "This is the financial equivalent of running on fumes. Park the car. Stop spending.",
    "Future you is watching this in horror. Be the hero of your own money story — stop now.",
]

NO_SALARY = [
    "Set your salary first so SpendWise can give you personalised spending insights. 💡",
    "We can't coach what we can't measure. Add your salary to unlock smart spending tips.",
    "Your spending coach is ready — just needs your salary to get started. 🎯",
]


def get_spending_message(spend_pct: float | None) -> dict:
    """
    Returns a dict with:
      - message: str  (spending coach message)
      - tone: str     ('excellent' | 'good' | 'warning' | 'high' | 'critical' | 'neutral')
      - emoji: str
    """
    if spend_pct is None:
        return {
            'message': random.choice(NO_SALARY),
            'tone': 'neutral',
            'emoji': '💡',
        }

    if spend_pct < 30:
        return {'message': random.choice(EXCELLENT), 'tone': 'excellent', 'emoji': '🏆'}
    elif spend_pct < 50:
        return {'message': random.choice(GOOD),     'tone': 'good',     'emoji': '✅'}
    elif spend_pct < 75:
        return {'message': random.choice(WARNING),  'tone': 'warning',  'emoji': '⚠️'}
    elif spend_pct < 90:
        return {'message': random.choice(HIGH),     'tone': 'high',     'emoji': '🔴'}
    else:
        return {'message': random.choice(CRITICAL), 'tone': 'critical', 'emoji': '🚨'}


def fetch_dad_joke() -> str:
    """Fetches a random dad joke from icanhazdadjoke.com."""
    try:
        req = urllib.request.Request(
            'https://icanhazdadjoke.com/',
            headers={'Accept': 'text/plain', 'User-Agent': 'SpendWise/1.0'},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode('utf-8').strip()
    except (urllib.error.URLError, Exception):
        # Fallback jokes if API is unreachable
        fallbacks = [
            "Why did the bank robber take a bath? He wanted to make a clean getaway.",
            "I told my wallet a joke. It didn't laugh — it was too broke.",
            "Why is money called dough? Because we all knead it.",
            "I asked my bank for a loan. They said 'Sure, what's your collateral?' I said 'My sense of humour.' They didn't laugh.",
        ]
        return random.choice(fallbacks)
