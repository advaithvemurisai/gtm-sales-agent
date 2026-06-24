from anthropic import Anthropic
from typing import Dict, Any
import os

def get_web_search_data(company_name: str) -> Dict[str, Any]:
    """
    Uses Anthropic's web search to find recent news and signals about a company.

    Args:
        company_name: The company name to search for

    Returns:
        Dict with raw_data and summary (summary populated by LLM)
    """
    search_query = f"{company_name} recent news funding hiring growth"

    web_search_data = {
        "company_name": company_name,
        "search_query": search_query,
        "results": [],
        "error": None
    }

    try:
        response = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="You are a research assistant. Search the web for recent news about the given company and extract key signals about growth, funding, hiring, and recent developments. Return a JSON-formatted summary.",
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search"}
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Find recent news and signals about {company_name}. Look for funding announcements, hiring news, product launches, and business developments."
                }
            ]
        )

        # Extract web search results from the response
        for block in response.content:
            if hasattr(block, 'text'):
                web_search_data["results"].append({
                    "type": "text",
                    "content": block.text
                })
            elif hasattr(block, 'input'):
                # This would be the tool use block
                web_search_data["results"].append({
                    "type": "search",
                    "query": block.input.get("query", "")
                })

    except Exception as e:
        web_search_data["error"] = str(e)

    return {
        "raw_data": web_search_data,
        "summary": None  # Will be populated by LLM
    }
