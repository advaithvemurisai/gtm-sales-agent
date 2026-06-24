import random
from typing import Dict, Any

STAGE_CONFIG = {
    "Seed": {
        "total_funding_options": [1, 2, 3, 5],
        "headcount_options": [5, 10, 15, 25],
        "rounds": [
            {"year": 2024, "amount_range": (500_000, 3_000_000), "type": "Seed"},
        ]
    },
    "Series A": {
        "total_funding_options": [8, 12, 18, 25],
        "headcount_options": [20, 35, 50, 75],
        "rounds": [
            {"year": 2024, "amount_range": (8_000_000, 20_000_000), "type": "Series A"},
            {"year": 2023, "amount_range": (1_000_000, 4_000_000), "type": "Seed"},
        ]
    },
    "Series B": {
        "total_funding_options": [40, 60, 80, 120],
        "headcount_options": [75, 120, 180, 250],
        "rounds": [
            {"year": 2024, "amount_range": (30_000_000, 80_000_000), "type": "Series B"},
            {"year": 2022, "amount_range": (10_000_000, 22_000_000), "type": "Series A"},
            {"year": 2021, "amount_range": (2_000_000, 5_000_000), "type": "Seed"},
        ]
    },
    "Series C": {
        "total_funding_options": [150, 220, 300, 400],
        "headcount_options": [250, 400, 600, 900],
        "rounds": [
            {"year": 2024, "amount_range": (80_000_000, 200_000_000), "type": "Series C"},
            {"year": 2022, "amount_range": (40_000_000, 80_000_000), "type": "Series B"},
            {"year": 2020, "amount_range": (12_000_000, 25_000_000), "type": "Series A"},
        ]
    },
    "Growth": {
        "total_funding_options": [500, 750, 1000, 1500],
        "headcount_options": [800, 1200, 2000, 3500],
        "rounds": [
            {"year": 2023, "amount_range": (200_000_000, 500_000_000), "type": "Growth"},
            {"year": 2021, "amount_range": (80_000_000, 150_000_000), "type": "Series C"},
            {"year": 2019, "amount_range": (30_000_000, 70_000_000), "type": "Series B"},
        ]
    },
    "Public": {
        "total_funding_options": [2000, 3500, 5000, 8000],
        "headcount_options": [3000, 6000, 10000, 25000],
        "rounds": [
            {"year": 2021, "amount_range": (500_000_000, 2_000_000_000), "type": "IPO"},
            {"year": 2019, "amount_range": (100_000_000, 400_000_000), "type": "Series D"},
        ]
    }
}


def _format_amount(amount: int) -> str:
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    return f"${amount // 1_000_000}M"


def get_crunchbase_data(company_name: str) -> Dict[str, Any]:
    stage = random.choice(list(STAGE_CONFIG.keys()))
    config = STAGE_CONFIG[stage]

    total_funding_m = random.choice(config["total_funding_options"])
    headcount = random.choice(config["headcount_options"])
    founded_year = random.randint(2010, 2021)

    rounds = []
    for r in config["rounds"]:
        amount = random.randint(*r["amount_range"])
        rounds.append({
            "year": r["year"],
            "amount": _format_amount(amount),
            "type": r["type"]
        })

    fake_data = {
        "company_name": company_name,
        "founded_year": founded_year,
        "total_funding": f"${total_funding_m}M",
        "funding_stage": stage,
        "headcount": headcount,
        "headquarters": random.choice([
            "San Francisco, CA", "New York, NY",
            "Seattle, WA", "Boston, MA", "Austin, TX"
        ]),
        "recent_funding_rounds": rounds
    }

    return {
        "raw_data": fake_data,
        "summary": None
    }