import time
import requests
import gspread
import logging
from gspread.utils import rowcol_to_a1

from google.oauth2.service_account import Credentials
from config import NOTION_ID_COLUMN, NOTION_DB_ID, SPREADSHEET_NAME, GOOGLE_CREDENTIALS_FILE, SCOPES, RATE_LIMIT_DELAY, notion_headers

logger = logging.getLogger(__name__)

class Sync2Sheets:
    def __init__(self, progress_callback=None):
        self.gs_client = self._get_gs_client()
        self.sheet = self._get_sheet()
        self.notion_db_schema = self._fetch_notion_db_schema()
        self.progress_callback = progress_callback
        self.sync_stats = {"updated": 0, "created": 0, "errors": 0}

    def _get_gs_client(self):
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        return gspread.authorize(creds)

    def _get_sheet(self):
        return self.gs_client.open(SPREADSHEET_NAME).sheet1

    def _fetch_notion_db_schema(self):
        url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}"
        response = requests.get(url, headers=notion_headers)
        response.raise_for_status()
        return response.json()["properties"]

    def _update_progress(self, message):
        if self.progress_callback:
            self.progress_callback(message)
        logger.info(message)

    def sync_notion_to_sheets(self):
        self.sync_stats = {"updated": 0, "created": 0, "errors": 0}
        self._update_progress("Fetching Notion database pages...")
        pages = self._fetch_all_notion_pages()

        headers = list(self.notion_db_schema.keys()) + [NOTION_ID_COLUMN]
        sheet_data = self.sheet.get_all_values()
        if not sheet_data:
            raise Exception("Sheet is empty or missing headers.")
        sheet_headers = sheet_data[0]
        if sheet_headers != headers:
            raise Exception("Sheet headers do not match Notion properties.")
        id_index = headers.index(NOTION_ID_COLUMN)

        existing = {
            row[id_index]: i + 2 for i, row in enumerate(sheet_data[1:])
            if len(row) > id_index and row[id_index]
        }

        update_batch = []
        append_batch = []

        for i, page in enumerate(pages):
            try:
                row_data = self._format_notion_page_for_sheet(page, headers)
                page_id = page["id"]
                if page_id in existing:
                    row_num = existing[page_id]
                    a1 = rowcol_to_a1(row_num, 1)
                    update_batch.append((a1, [row_data]))
                    self.sync_stats["updated"] += 1
                else:
                    append_batch.append(row_data)
                    self.sync_stats["created"] += 1
                if RATE_LIMIT_DELAY:
                    time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.error(f"Error processing Notion page: {e}")
                self.sync_stats["errors"] += 1

        for a1, values in update_batch:
            self.sheet.update(a1, values)

        if append_batch:
            self.sheet.append_rows(append_batch)

    def _fetch_all_notion_pages(self):
        results = []
        url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
        payload = {}
        while True:
            response = requests.post(url, headers=notion_headers, json=payload)
            response.raise_for_status()
            data = response.json()
            results.extend(data["results"])
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data.get("next_cursor")
            if RATE_LIMIT_DELAY:
                time.sleep(RATE_LIMIT_DELAY)
        return results

    def _format_notion_page_for_sheet(self, page, headers):
        row = {}
        for key, val in page["properties"].items():
            row[key] = self._extract_value_from_prop(val)
        row[NOTION_ID_COLUMN] = page["id"]
        return [row.get(h, "") for h in headers]

    def _extract_value_from_prop(self, prop):
        typ = prop.get("type")
        val = prop.get(typ)
        if not val:
            return ""
        if typ in ["title", "rich_text"]:
            return "".join(t.get("plain_text", "") for t in val)
        if typ == "select":
            return val.get("name", "")
        if typ == "multi_select":
            return ", ".join(v.get("name", "") for v in val)
        if typ == "number":
            return str(val)
        if typ == "checkbox":
            return "TRUE" if val else "FALSE"
        if typ == "date":
            return val.get("start", "")
        if typ == "status":
            return val.get("name", "")
        return str(val)

    def sync_sheets_to_notion(self):
        self.sync_stats = {"updated": 0, "created": 0, "errors": 0}
        rows = self.sheet.get_all_values()
        if not rows:
            raise Exception("Sheet is empty.")
        headers = rows[0]
        id_index = headers.index(NOTION_ID_COLUMN)

        batch_updates = []

        for i, row in enumerate(rows[1:], start=2):
            try:
                props = self._build_notion_properties_from_row(row, headers)
                page_id = row[id_index] if len(row) > id_index and row[id_index] else None
                if page_id:
                    url = f"https://api.notion.com/v1/pages/{page_id}"
                    response = requests.patch(url, headers=notion_headers, json={"properties": props})
                    response.raise_for_status()
                    self.sync_stats["updated"] += 1
                else:
                    url = "https://api.notion.com/v1/pages"
                    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": props}
                    response = requests.post(url, headers=notion_headers, json=payload)
                    response.raise_for_status()
                    new_id = response.json()["id"]
                    cell_range = rowcol_to_a1(i, id_index + 1)
                    batch_updates.append((cell_range, [[new_id]]))
                    self.sync_stats["created"] += 1
                if RATE_LIMIT_DELAY:
                    time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.error(f"Error processing sheet row {i}: {e}")
                self.sync_stats["errors"] += 1

        for rng, val in batch_updates:
            self.sheet.update(rng, val)

    def _build_notion_properties_from_row(self, row, headers):
        props = {}
        for i, header in enumerate(headers):
            if header == NOTION_ID_COLUMN or i >= len(row):
                continue
            val = row[i].strip()
            schema = self.notion_db_schema.get(header)
            if not schema or not val:
                continue
            typ = schema["type"]
            try:
                if typ == "title":
                    props[header] = {"title": [{"text": {"content": val}}]}
                elif typ == "rich_text":
                    props[header] = {"rich_text": [{"text": {"content": val}}]}
                elif typ == "number":
                    props[header] = {"number": float(val.replace(",", ""))}
                elif typ == "checkbox":
                    props[header] = {"checkbox": val.upper() in ["TRUE", "YES", "1", "✓"]}
                elif typ == "select":
                    props[header] = {"select": {"name": val}}
                elif typ == "status":
                    props[header] = {"status": {"name": val}}
                elif typ == "multi_select":
                    props[header] = {"multi_select": [{"name": x.strip()} for x in val.split(",") if x.strip()]}
                elif typ == "date":
                    props[header] = {"date": {"start": val[:10]}}
            except Exception as e:
                logger.warning(f"Skipping cell ({header}): {val} → {e}")
        return props
