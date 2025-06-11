import json

# --- CONFIGURATION LOADER ---
def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception("config.json file not found. Please create it.")
    except json.JSONDecodeError:
        raise Exception("Invalid JSON format in config.json")

# Load configuration
CONFIG = load_config()

# Extracted values
NOTION_API_KEY = CONFIG["notion"]["api_key"]
NOTION_DB_ID = CONFIG["notion"]["database_id"]
SPREADSHEET_NAME = CONFIG["google_sheets"]["spreadsheet_name"]
NOTION_ID_COLUMN = CONFIG["google_sheets"].get("notion_id_column", "Notion Page ID")
GOOGLE_CREDENTIALS_FILE = "creds.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
RATE_LIMIT_DELAY = CONFIG.get("rate_limit_delay", 0.1)

# Notion request headers
notion_headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
