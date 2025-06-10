import os
import threading
import requests
import gspread
from google.oauth2.service_account import Credentials
import flet as ft
import json

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

    def __init__(self):
        self.gs_client = self._get_gs_client()
        self.sheet = self._get_sheet()
        self.notion_db_schema = self._fetch_notion_db_schema()

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

    def sync_notion_to_sheets(self):
        """
        Fetches all pages from the Notion database and intelligently updates or appends
        them to the Google Sheet.
        """
        # 1. Fetch all data from Notion
        notion_pages = self._fetch_all_notion_pages()

        # 2. Get current state of Google Sheet
        sheet_data = self.sheet.get_all_records(head=1) # Get as a list of dictionaries
        sheet_by_notion_id = {row[NOTION_ID_COLUMN]: row for row in sheet_data if NOTION_ID_COLUMN in row}
        
        headers = list(self.notion_db_schema.keys()) + [NOTION_ID_COLUMN]
        
        # Ensure sheet has the correct headers
        if self.sheet.row_count < 1 or self.sheet.row_values(1) != headers:
            self.sheet.clear()
            self.sheet.append_row(headers)

        updates = []
        for page in notion_pages:
            page_id = page['id']
            row_data = self._format_notion_page_for_sheet(page, headers)

            # Check if this page ID already exists in our sheet data
            if page_id in sheet_by_notion_id:
                # Update existing row if data differs (more efficient)
                # This check can be expanded to be more granular
                pass # For simplicity, we will just overwrite
            
            # For this simplified example, we'll just write all rows.
            # A more advanced version would use gspread's batch_update for efficiency.
            updates.append(row_data)
        
        # Clear all but header and batch write
        self.sheet.clear()
        self.sheet.append_row(headers)
        if updates:
            self.sheet.append_rows(updates)

    def _fetch_all_notion_pages(self):
        """Fetches all pages from a Notion database, handling pagination."""
        all_results = []
        url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
        payload = {}
        has_more = True
        
        while has_more:
            response = requests.post(url, headers=notion_headers, json=payload)
            response.raise_for_status()
            data = response.json()
            all_results.extend(data["results"])
            has_more = data["has_more"]
            payload["start_cursor"] = data.get("next_cursor")
            
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
            return val.get("start", "")
        if prop_type in ["url", "email", "phone_number"]:
            return val
        if prop_type == "formula":
            return self._extract_value_from_prop(val)
        if prop_type == "relation":
            # For simplicity, we don't resolve relations here.
            return f"{len(val)} relations"
        if prop_type == "people":
            return ", ".join(person.get('name', 'Unknown User') for person in val)
        return str(val) # Fallback for unhandled types

    def sync_sheets_to_notion(self):
        """
        Reads rows from Google Sheets and creates or updates corresponding pages in Notion.
        """
        rows = self.sheet.get_all_values()
        if not rows:
            raise Exception("Sheet is empty.")
            
        headers = rows[0]
        id_column_index = headers.index(NOTION_ID_COLUMN) if NOTION_ID_COLUMN in headers else -1
        
        if id_column_index == -1:
            raise Exception(f"'{NOTION_ID_COLUMN}' column not found in sheet.")

        for row_index, row in enumerate(rows[1:], start=2):
            properties = self._build_notion_properties_from_row(row, headers)
            notion_page_id = row[id_column_index] if len(row) > id_column_index else None

            try:
                if notion_page_id:
                    # Update existing page
                    url = f"https://api.notion.com/v1/pages/{notion_page_id}"
                    payload = {"properties": properties}
                    response = requests.patch(url, headers=notion_headers, json=payload)
                    response.raise_for_status()
                else:
                    # Create new page
                    url = "https://api.notion.com/v1/pages"
                    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties}
                    response = requests.post(url, headers=notion_headers, json=payload)
                    response.raise_for_status()
                    # Write the new page ID back to the sheet
                    new_page_id = response.json()['id']
                    self.sheet.update_cell(row_index, id_column_index + 1, new_page_id)
            except requests.exceptions.RequestException as e:
                # Log error and continue with next row
                error_text = e.response.text if hasattr(e, "response") and e.response is not None else str(e)
                print(f"Failed to sync row {row_index} to Notion. Error: {error_text}")
                continue # Don't let one bad row stop the whole sync

    def _build_notion_properties_from_row(self, row, headers):
        """Constructs a Notion API properties object from a sheet row."""
        properties = {}
        for i, header in enumerate(headers):
            if header == NOTION_ID_COLUMN or i >= len(row):
                continue
            
            cell_value = row[i]
            if header not in self.notion_db_schema:
                continue # Skip columns in sheet that aren't in Notion DB
                
            prop_schema = self.notion_db_schema[header]
            prop_type = prop_schema['type']
            
            # Based on the schema, construct the correct object structure
            if prop_type == "title":
                properties[header] = {"title": [{"text": {"content": cell_value}}]}
            elif prop_type == "rich_text":
                properties[header] = {"rich_text": [{"text": {"content": cell_value}}]}
            elif prop_type == "number" and cell_value:
                try:
                    properties[header] = {"number": float(cell_value)}
                except ValueError:
                    properties[header] = {"number": None} # Or handle error
            elif prop_type == "select" and cell_value:
                properties[header] = {"select": {"name": cell_value}}
            elif prop_type == "status" and cell_value:
                properties[header] = {"status": {"name": cell_value}}
            elif prop_type == "multi_select":
                names = [name.strip() for name in cell_value.split(',') if name.strip()]
                properties[header] = {"multi_select": [{"name": name} for name in names]}
            elif prop_type == "checkbox":
                properties[header] = {"checkbox": cell_value.upper() == "TRUE"}
            elif prop_type == "date" and cell_value:
                 properties[header] = {"date": {"start": cell_value, "end": None}}
            elif prop_type == "url" and cell_value:
                properties[header] = {"url": cell_value}
            elif prop_type == "email" and cell_value:
                properties[header] = {"email": cell_value}
            elif prop_type == "phone_number" and cell_value:
                properties[header] = {"phone_number": cell_value}
            # People and Relation properties are read-only from Sheets in this version
            # as they require mapping to Notion-specific IDs.

        return properties

# --- FLET APPLICATION ---

def main(page: ft.Page):
    page.title = "Notion ↔ Sheets Sync"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT

    # --- UI State ---
    sync_in_progress = ft.Ref[ft.Text]()
    n2s_button = ft.Ref[ft.ElevatedButton]()
    s2n_button = ft.Ref[ft.ElevatedButton]()
    config_status = ft.Ref[ft.Text]()

    def set_ui_locking(is_locked: bool):
        """Disables buttons and shows progress text to prevent multiple runs."""
        n2s_button.current.disabled = is_locked
        s2n_button.current.disabled = is_locked
        sync_in_progress.current.visible = is_locked
        page.update()
        
    def notion_to_sheets_task():
        """The actual sync task that runs in a separate thread."""
        set_ui_locking(True)
        try:
            sync_tool = Sync2Sheets()
            sync_tool.sync_notion_to_sheets()
            show_snackbar(page, "Successfully synced Notion to Google Sheets!", ft.Colors.GREEN)
        except Exception as e:
            show_snackbar(page, f"Error: {e}", ft.Colors.RED)
        finally:
            set_ui_locking(False)
            
    def sheets_to_notion_task():
        """The actual sync task that runs in a separate thread."""
        set_ui_locking(True)
        try:
            sync_tool = Sync2Sheets()
            sync_tool.sync_sheets_to_notion()
            show_snackbar(page, "Successfully synced Google Sheets to Notion!", ft.Colors.GREEN)
        except Exception as e:
            show_snackbar(page, f"Error: {e}", ft.Colors.RED)
        finally:
            set_ui_locking(False)

    def handle_notion_to_sheets_click(e):
        # Run the sync in a new thread to avoid freezing the UI
        threading.Thread(target=notion_to_sheets_task).start()

    def handle_sheets_to_notion_click(e):
        # Run the sync in a new thread to avoid freezing the UI
        threading.Thread(target=sheets_to_notion_task).start()

    # Verify configuration
    config_status_text = "✅ Configuration loaded successfully"
    if not all([NOTION_API_KEY, NOTION_DB_ID]):
        config_status_text = "⚠️ Missing Notion configuration in config.json"
    elif not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        config_status_text = f"⚠️ Google credentials file not found: {GOOGLE_CREDENTIALS_FILE}"

    page.add(
        ft.Column(
            [
                ft.Text("Notion ↔ Google Sheets Sync", size=32, weight=ft.FontWeight.BOLD),
                ft.Text(ref=config_status, value=config_status_text, size=14, 
                        color=ft.Colors.GREEN if "✅" in config_status_text else ft.Colors.ORANGE),
                ft.Text(f"Syncing database: {NOTION_DB_ID}", size=12, color=ft.Colors.GREY),
                ft.Text(f"Spreadsheet: {SPREADSHEET_NAME}", size=12, color=ft.Colors.GREY),
                ft.Divider(),
                ft.Text(ref=sync_in_progress, value="Sync in progress, please wait...", visible=False, color=ft.Colors.BLUE),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            ref=n2s_button,
                            text="Sync Notion → Sheets",
                            icon=ft.Icons.ARROW_DOWNWARD,
                            on_click=handle_notion_to_sheets_click,
                            width=250,
                            disabled="⚠️" in config_status_text
                        ),
                        ft.ElevatedButton(
                            ref=s2n_button,
                            text="Sync Sheets → Notion",
                            icon=ft.Icons.ARROW_UPWARD,
                            on_click=handle_sheets_to_notion_click,
                            width=250,
                            disabled="⚠️" in config_status_text
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Text("Note: The first row in your sheet must match Notion property names", 
                        size=12, color=ft.Colors.GREY_600, italic=True),
                ft.Text(f"Notion ID Column: {NOTION_ID_COLUMN}", 
                        size=12, color=ft.Colors.BLUE_GREY),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)