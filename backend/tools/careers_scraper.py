import requests
from bs4 import BeautifulSoup
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def get_careers_page_data(company_name: str, careers_url: str = None) -> Dict[str, Any]:
    """
    Scrapes company careers page for open roles and hiring signals.

    Args:
        company_name: The company name
        careers_url: Direct URL to careers page (optional)

    Returns:
        Dict with raw_data and summary (summary populated by LLM)
    """
    if not careers_url:
        # Construct common careers page URLs
        domain = company_name.lower().replace(" ", "")
        possible_urls = [
            f"https://{domain}.com/careers",
            f"https://jobs.{domain}.com",
            f"https://www.{domain}.com/careers"
        ]
    else:
        possible_urls = [careers_url]

    careers_data = {
        "company_name": company_name,
        "careers_url": careers_url,
        "open_positions": [],
        "hiring_departments": [],
        "error": None
    }

    for url in possible_urls:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # Look for job listings - common patterns
                job_titles = []
                for job_elem in soup.find_all(['h2', 'h3', 'span', 'a'],
                                             {'class': ['job', 'position', 'title', 'opening']}):
                    text = job_elem.get_text(strip=True)
                    if text and len(text) < 100:
                        job_titles.append(text)

                # Extract departments from job postings
                departments = set()
                for elem in soup.find_all(['div', 'p'], {'class': 'department'}):
                    dept = elem.get_text(strip=True)
                    if dept:
                        departments.add(dept)

                careers_data["open_positions"] = job_titles[:10] if job_titles else []
                careers_data["hiring_departments"] = list(departments) if departments else []
                careers_data["careers_url"] = url

                if job_titles or departments:
                    break
        except requests.RequestException as e:
            careers_data["error"] = str(e)
            logger.warning(f"Failed to fetch {url}: {e}")
            continue

    return {
        "raw_data": careers_data,
        "summary": None  # Will be populated by LLM
    }
