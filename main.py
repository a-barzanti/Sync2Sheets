import os
import threading
import requests
import gspread
from google.oauth2.service_account import Credentials
import flet as ft
import json
import time
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION LOADER ---
def load_config():
    """Load configuration from config.json file"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception("config.json file not found. Please create it.")
    except json.JSONDecodeError:
        raise Exception("Invalid JSON format in config.json")

# Load configuration
CONFIG = load_config()

# --- CONFIGURATION VALUES ---
NOTION_API_KEY = CONFIG["notion"]["api_key"]
NOTION_DB_ID = CONFIG["notion"]["database_id"]
SPREADSHEET_NAME = CONFIG["google_sheets"]["spreadsheet_name"]
NOTION_ID_COLUMN = CONFIG["google_sheets"].get("notion_id_column", "Notion Page ID")
GOOGLE_CREDENTIALS_FILE = CONFIG["google_sheets"].get("credentials_file", "google-credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
RATE_LIMIT_DELAY = CONFIG.get("rate_limit_delay", 0.1)  # Seconds between API calls

# --- API CLIENT SETUP ---
# Headers for Notion API
notion_headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# --- FLET UI HELPER FUNCTIONS ---

def show_snackbar(page: ft.Page, message: str, color: str = ft.Colors.GREEN):
    """Helper to display a notification snackbar in the UI."""
    snackbar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
    page.overlay.append(snackbar)
    snackbar.open = True
    page.update()

# --- CORE SYNC LOGIC ---

class Sync2Sheets:
    """Encapsulates all logic for syncing between Notion and Google Sheets."""

    def __init__(self, progress_callback=None):
        self.gs_client = self._get_gs_client()
        self.sheet = self._get_sheet()
        self.notion_db_schema = self._fetch_notion_db_schema()
        self.progress_callback = progress_callback
        self.sync_stats = {"updated": 0, "created": 0, "errors": 0}

    def _get_gs_client(self):
        """Initializes and returns the gspread client."""
        try:
            creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
            return gspread.authorize(creds)
        except FileNotFoundError:
            raise Exception(f"Google credentials file not found at '{GOOGLE_CREDENTIALS_FILE}'")
        except Exception as e:
            raise Exception(f"Failed to authorize Google Sheets: {e}")

    def _get_sheet(self):
        """Opens and returns the specific worksheet."""
        try:
            return self.gs_client.open(SPREADSHEET_NAME).sheet1
        except gspread.exceptions.SpreadsheetNotFound:
            raise Exception(f"Spreadsheet '{SPREADSHEET_NAME}' not found.")

    def _fetch_notion_db_schema(self):
        """Fetches the Notion database schema to understand property types."""
        url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}"
        try:
            response = requests.get(url, headers=notion_headers)
            response.raise_for_status()
            return response.json()["properties"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch Notion database schema: {e}")

    def _update_progress(self, message: str):
        """Update progress if callback is provided."""
        if self.progress_callback:
            self.progress_callback(message)
        logger.info(message)

    def sync_notion_to_sheets(self):
        """
        Fetches all pages from the Notion database and intelligently updates or appends
        them to the Google Sheet using batch operations.
        """
        self.sync_stats = {"updated": 0, "created": 0, "errors": 0}
        
        self._update_progress("Fetching Notion database pages...")
        notion_pages = self._fetch_all_notion_pages()
        
        self._update_progress("Processing sheet data...")
        headers = list(self.notion_db_schema.keys()) + [NOTION_ID_COLUMN]
        
        # Prepare batch data
        batch_data = [headers]  # Start with headers
        
        for i, page in enumerate(notion_pages):
            try:
                row_data = self._format_notion_page_for_sheet(page, headers)
                batch_data.append(row_data)
                
                if (i + 1) % 10 == 0:  # Update progress every 10 pages
                    self._update_progress(f"Processed {i + 1}/{len(notion_pages)} pages")
                    
            except Exception as e:
                logger.error(f"Error processing page {page.get('id', 'unknown')}: {e}")
                self.sync_stats["errors"] += 1
        
        # Batch update the sheet
        self._update_progress("Updating Google Sheet...")
        try:
            self.sheet.clear()
            if batch_data:
                # Use batch update for better performance
                self.sheet.update(range_name="A1", values=batch_data)
            self.sync_stats["updated"] = len(notion_pages)
        except Exception as e:
            raise Exception(f"Failed to update Google Sheet: {e}")

    def _fetch_all_notion_pages(self):
        """Fetches all pages from a Notion database, handling pagination with rate limiting."""
        all_results = []
        url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
        payload = {}
        has_more = True
        page_count = 0
        
        while has_more:
            try:
                response = requests.post(url, headers=notion_headers, json=payload)
                response.raise_for_status()
                data = response.json()
                all_results.extend(data["results"])
                has_more = data["has_more"]
                payload["start_cursor"] = data.get("next_cursor")
                page_count += len(data["results"])
                
                # Rate limiting
                if RATE_LIMIT_DELAY > 0:
                    time.sleep(RATE_LIMIT_DELAY)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching Notion pages: {e}")
                raise Exception(f"Failed to fetch Notion pages: {e}")
            
        return all_results

    def _format_notion_page_for_sheet(self, page, headers):
        """Converts a Notion page object into a list for a sheet row."""
        row = {}
        props = page["properties"]
        for key, value in props.items():
            row[key] = self._extract_value_from_prop(value)
        
        row[NOTION_ID_COLUMN] = page['id']
        
        # Order the row according to headers
        return [row.get(header, "") for header in headers]

    def _extract_value_from_prop(self, prop):
        """Extracts a displayable string value from a Notion property object."""
        prop_type = prop.get("type")
        val = prop.get(prop_type)

        if not val:
            return ""
        if prop_type == "title" or prop_type == "rich_text":
            return "".join(t.get("plain_text", "") for t in val)
        if prop_type in ["select", "status"]:
            return val.get("name", "")
        if prop_type == "multi_select":
            return ", ".join(v.get("name", "") for v in val)
        if prop_type == "number":
            return str(val) if val is not None else ""
        if prop_type == "checkbox":
            return "TRUE" if val else "FALSE"
        if prop_type == "date":
            if isinstance(val, dict):
                start_date = val.get("start", "")
                end_date = val.get("end", "")
                return f"{start_date}" + (f" to {end_date}" if end_date else "")
            return str(val)
        if prop_type in ["url", "email", "phone_number"]:
            return val
        if prop_type == "formula":
            return self._extract_value_from_prop(val)
        if prop_type == "relation":
            return f"{len(val)} relations" if isinstance(val, list) else "0 relations"
        if prop_type == "people":
            return ", ".join(person.get('name', 'Unknown User') for person in val)
        if prop_type == "created_time" or prop_type == "last_edited_time":
            return val[:10] if val else ""  # Extract date part
        return str(val)[:100] + "..." if len(str(val)) > 100 else str(val)  # Truncate very long values

    def sync_sheets_to_notion(self):
        """
        Reads rows from Google Sheets and creates or updates corresponding pages in Notion
        with improved error handling and batch processing.
        """
        self.sync_stats = {"updated": 0, "created": 0, "errors": 0}
        
        self._update_progress("Reading Google Sheet data...")
        rows = self.sheet.get_all_values()
        if not rows:
            raise Exception("Sheet is empty.")
            
        headers = rows[0]
        id_column_index = headers.index(NOTION_ID_COLUMN) if NOTION_ID_COLUMN in headers else -1
        
        if id_column_index == -1:
            raise Exception(f"'{NOTION_ID_COLUMN}' column not found in sheet.")

        data_rows = rows[1:]  # Skip header row
        batch_updates = []  # For updating sheet with new page IDs
        
        for row_index, row in enumerate(data_rows, start=2):
            try:
                self._update_progress(f"Processing row {row_index - 1}/{len(data_rows)}")
                
                properties = self._build_notion_properties_from_row(row, headers)
                notion_page_id = row[id_column_index] if len(row) > id_column_index and row[id_column_index] else None

                if notion_page_id:
                    # Update existing page
                    url = f"https://api.notion.com/v1/pages/{notion_page_id}"
                    payload = {"properties": properties}
                    response = requests.patch(url, headers=notion_headers, json=payload)
                    response.raise_for_status()
                    self.sync_stats["updated"] += 1
                else:
                    # Create new page
                    url = "https://api.notion.com/v1/pages"
                    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties}
                    response = requests.post(url, headers=notion_headers, json=payload)
                    response.raise_for_status()
                    
                    # Prepare batch update for new page ID
                    new_page_id = response.json()['id']
                    batch_updates.append({
                        'range': f'{chr(65 + id_column_index)}{row_index}',
                        'values': [[new_page_id]]
                    })
                    self.sync_stats["created"] += 1
                
                # Rate limiting
                if RATE_LIMIT_DELAY > 0:
                    time.sleep(RATE_LIMIT_DELAY)
                    
            except requests.exceptions.RequestException as e:
                error_text = e.response.text if hasattr(e, "response") and e.response is not None else str(e)
                logger.error(f"Failed to sync row {row_index} to Notion. Error: {error_text}")
                self.sync_stats["errors"] += 1
                continue
            except Exception as e:
                logger.error(f"Unexpected error processing row {row_index}: {e}")
                self.sync_stats["errors"] += 1
                continue

        # Batch update new page IDs
        if batch_updates:
            self._update_progress("Updating sheet with new page IDs...")
            try:
                for update in batch_updates:
                    self.sheet.update(update['range'], update['values'])
                    if RATE_LIMIT_DELAY > 0:
                        time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.warning(f"Failed to update some page IDs in sheet: {e}")

    def _build_notion_properties_from_row(self, row, headers):
        """Constructs a Notion API properties object from a sheet row with improved validation."""
        properties = {}
        for i, header in enumerate(headers):
            if header == NOTION_ID_COLUMN or i >= len(row):
                continue
            
            cell_value = row[i].strip() if i < len(row) else ""
            if header not in self.notion_db_schema or not cell_value:
                continue
                
            prop_schema = self.notion_db_schema[header]
            prop_type = prop_schema['type']
            
            try:
                # Based on the schema, construct the correct object structure
                if prop_type == "title":
                    properties[header] = {"title": [{"text": {"content": cell_value[:2000]}}]}  # Notion title limit
                elif prop_type == "rich_text":
                    properties[header] = {"rich_text": [{"text": {"content": cell_value[:2000]}}]}  # Notion text limit
                elif prop_type == "number" and cell_value:
                    try:
                        # Handle different number formats
                        clean_value = cell_value.replace(',', '').replace('$', '').strip()
                        properties[header] = {"number": float(clean_value)}
                    except ValueError:
                        logger.warning(f"Invalid number format for {header}: {cell_value}")
                        continue
                elif prop_type == "select" and cell_value:
                    # Validate against available options
                    available_options = [opt['name'] for opt in prop_schema.get('select', {}).get('options', [])]
                    if not available_options or cell_value in available_options:
                        properties[header] = {"select": {"name": cell_value}}
                elif prop_type == "status" and cell_value:
                    properties[header] = {"status": {"name": cell_value}}
                elif prop_type == "multi_select":
                    names = [name.strip() for name in cell_value.split(',') if name.strip()]
                    if names:
                        properties[header] = {"multi_select": [{"name": name} for name in names]}
                elif prop_type == "checkbox":
                    properties[header] = {"checkbox": cell_value.upper() in ["TRUE", "YES", "1", "✓"]}
                elif prop_type == "date" and cell_value:
                    # Basic date validation (assumes YYYY-MM-DD format)
                    if len(cell_value) >= 10 and cell_value[4] == '-' and cell_value[7] == '-':
                        properties[header] = {"date": {"start": cell_value[:10]}}
                elif prop_type == "url" and cell_value:
                    if cell_value.startswith(('http://', 'https://')):
                        properties[header] = {"url": cell_value}
                elif prop_type == "email" and cell_value:
                    if '@' in cell_value:  # Basic email validation
                        properties[header] = {"email": cell_value}
                elif prop_type == "phone_number" and cell_value:
                    properties[header] = {"phone_number": cell_value}
                    
            except Exception as e:
                logger.warning(f"Error processing property {header} with value {cell_value}: {e}")
                continue

        return properties

    def get_sync_summary(self):
        """Returns a summary of the last sync operation."""
        return f"Created: {self.sync_stats['created']}, Updated: {self.sync_stats['updated']}, Errors: {self.sync_stats['errors']}"

# --- FLET APPLICATION ---

def main(page: ft.Page):
    page.title = "Notion ↔ Sheets Sync"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 600
    page.window_height = 700

    # --- UI State ---
    sync_in_progress = ft.Ref[ft.Text]()
    progress_text = ft.Ref[ft.Text]()
    n2s_button = ft.Ref[ft.ElevatedButton]()
    s2n_button = ft.Ref[ft.ElevatedButton]()
    config_status = ft.Ref[ft.Text]()
    last_sync_info = ft.Ref[ft.Text]()

    def update_progress(message: str):
        """Updates the progress text in the UI."""
        if progress_text.current:
            progress_text.current.value = message
            page.update()

    def set_ui_locking(is_locked: bool):
        """Disables buttons and shows progress text to prevent multiple runs."""
        n2s_button.current.disabled = is_locked
        s2n_button.current.disabled = is_locked
        sync_in_progress.current.visible = is_locked
        progress_text.current.visible = is_locked
        page.update()
        
    def notion_to_sheets_task():
        """The actual sync task that runs in a separate thread."""
        set_ui_locking(True)
        try:
            sync_tool = Sync2Sheets(progress_callback=update_progress)
            sync_tool.sync_notion_to_sheets()
            summary = sync_tool.get_sync_summary()
            show_snackbar(page, f"✅ Notion → Sheets sync complete! {summary}", ft.Colors.GREEN)
            last_sync_info.current.value = f"Last sync: {datetime.now().strftime('%Y-%m-%d %H:%M')} - {summary}"
        except Exception as e:
            show_snackbar(page, f"❌ Error: {str(e)[:100]}...", ft.Colors.RED)
            logger.error(f"Notion to Sheets sync error: {e}")
        finally:
            set_ui_locking(False)
            
    def sheets_to_notion_task():
        """The actual sync task that runs in a separate thread."""
        set_ui_locking(True)
        try:
            sync_tool = Sync2Sheets(progress_callback=update_progress)
            sync_tool.sync_sheets_to_notion()
            summary = sync_tool.get_sync_summary()
            show_snackbar(page, f"✅ Sheets → Notion sync complete! {summary}", ft.Colors.GREEN)
            last_sync_info.current.value = f"Last sync: {datetime.now().strftime('%Y-%m-%d %H:%M')} - {summary}"
        except Exception as e:
            show_snackbar(page, f"❌ Error: {str(e)[:100]}...", ft.Colors.RED)
            logger.error(f"Sheets to Notion sync error: {e}")
        finally:
            set_ui_locking(False)

    def handle_notion_to_sheets_click(e):
        threading.Thread(target=notion_to_sheets_task, daemon=True).start()

    def handle_sheets_to_notion_click(e):
        threading.Thread(target=sheets_to_notion_task, daemon=True).start()

    # Verify configuration
    config_status_text = "✅ Configuration loaded successfully"
    config_color = ft.Colors.GREEN
    buttons_disabled = False
    
    if not all([NOTION_API_KEY, NOTION_DB_ID]):
        config_status_text = "⚠️ Missing Notion configuration in config.json"
        config_color = ft.Colors.ORANGE
        buttons_disabled = True
    elif not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        config_status_text = f"⚠️ Google credentials file not found: {GOOGLE_CREDENTIALS_FILE}"
        config_color = ft.Colors.ORANGE
        buttons_disabled = True

    page.add(
        ft.Column(
            [
                ft.Text("Notion ↔ Google Sheets Sync", size=32, weight=ft.FontWeight.BOLD),
                ft.Text(ref=config_status, value=config_status_text, size=14, color=config_color),
                
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Configuration Details", weight=ft.FontWeight.BOLD, size=16),
                            ft.Text(f"Database ID: {NOTION_DB_ID[:8]}...", size=12, color=ft.Colors.GREY),
                            ft.Text(f"Spreadsheet: {SPREADSHEET_NAME}", size=12, color=ft.Colors.GREY),
                            ft.Text(f"ID Column: {NOTION_ID_COLUMN}", size=12, color=ft.Colors.BLUE_GREY),
                        ]),
                        padding=15,
                    ),
                    elevation=2,
                ),
                
                ft.Divider(),
                
                ft.Text(ref=sync_in_progress, value="🔄 Sync in progress, please wait...", 
                       visible=False, color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD),
                ft.Text(ref=progress_text, value="", visible=False, color=ft.Colors.BLUE_GREY, size=12),
                
                ft.Row(
                    [
                        ft.ElevatedButton(
                            ref=n2s_button,
                            text="Sync Notion → Sheets",
                            icon=ft.Icons.ARROW_DOWNWARD,
                            on_click=handle_notion_to_sheets_click,
                            width=250,
                            height=50,
                            disabled=buttons_disabled,
                            style=ft.ButtonStyle(
                                color=ft.Colors.WHITE,
                                bgcolor=ft.Colors.BLUE,
                            )
                        ),
                        ft.ElevatedButton(
                            ref=s2n_button,
                            text="Sync Sheets → Notion",
                            icon=ft.Icons.ARROW_UPWARD,
                            on_click=handle_sheets_to_notion_click,
                            width=250,
                            height=50,
                            disabled=buttons_disabled,
                            style=ft.ButtonStyle(
                                color=ft.Colors.WHITE,
                                bgcolor=ft.Colors.GREEN,
                            )
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("📋 Usage Notes", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text("• First row in your sheet must match Notion property names", size=11),
                            ft.Text("• New pages created in Notion will get their ID written back to the sheet", size=11),
                            ft.Text("• Large datasets may take several minutes to sync", size=11),
                            ft.Text("• Check the logs for detailed error information", size=11),
                        ]),
                        padding=10,
                    ),
                    elevation=1,
                ),
                
                ft.Text(ref=last_sync_info, value="No recent sync operations", 
                       size=12, color=ft.Colors.GREY_600, italic=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)