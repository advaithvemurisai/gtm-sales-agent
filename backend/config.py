import os


SONNET_MODEL = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-5")
HAIKU_MODEL = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5")
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}
# Keep one slow upstream call from holding a request open for the SDK default (10 min x 3 tries).
REQUEST_TIMEOUT_SECONDS = 90
MAX_RETRIES = 1
MAX_COMPANY_NAME_LENGTH = 120
MAX_PRODUCT_DESCRIPTION_LENGTH = 2000
