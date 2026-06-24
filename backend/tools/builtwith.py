import random
from typing import Dict, Any

def get_builtwith_data(company_website: str) -> Dict[str, Any]:
    """
    Stub implementation returning realistic fake BuiltWith tech stack data.
    """
    tech_stacks = [
        {
            "frontend": ["React", "TypeScript", "Tailwind CSS"],
            "backend": ["Node.js", "Python", "PostgreSQL"],
            "infrastructure": ["AWS", "Docker", "Kubernetes"],
            "analytics": ["Segment", "Mixpanel", "DataDog"]
        },
        {
            "frontend": ["Vue.js", "JavaScript", "Bootstrap"],
            "backend": ["Java", "Spring Boot", "MySQL"],
            "infrastructure": ["Google Cloud", "Docker"],
            "analytics": ["Google Analytics", "Amplitude"]
        },
        {
            "frontend": ["Next.js", "TypeScript", "Material UI"],
            "backend": ["Python", "FastAPI", "PostgreSQL"],
            "infrastructure": ["AWS", "Terraform", "GitHub Actions"],
            "analytics": ["Rudderstack", "Heap"]
        }
    ]

    stack = random.choice(tech_stacks)

    fake_data = {
        "website": company_website,
        "technologies": stack,
        "last_updated": "2024-06-15",
        "confidence": random.choice([0.85, 0.90, 0.95, 0.99])
    }

    return {
        "raw_data": fake_data,
        "summary": None  # Will be populated by LLM
    }
