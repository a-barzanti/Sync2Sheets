# Sync2Sheets: Notion ↔ Google Sheets Sync

Easily synchronize data between a Notion database and a Google Sheet using a Flet UI, with two-way sync support.

---

## 🚀 Features

- Sync Notion → Google Sheets without wiping existing data
- Sync Google Sheets → Notion with automatic ID write-back
- Uses Google Service Account (gspread) and Notion public API
- Clean UI built with [Flet](https://flet.dev)
- Logs progress and error details to console
- Modular: `sync.py` (logic), `main.py` (UI), `config.py` (config)

---

## 🧩 Project Structure

```
.
├── main.py         # Flet UI interface
├── sync.py         # Sync logic (Notion ↔ Sheets)
├── config.py       # Configuration & secrets
├── config.json     # User-defined settings (Not committed)
├── creds.json      # Google Service Account credentials
```

---

## 🔧 Setup Instructions

### 1. Install Requirements

```bash
pip install flet gspread google-auth requests
```

### 2. Create `config.json`

```json
{
  "notion": {
    "api_key": "secret_XXXXX",
    "database_id": "XXXXXXXXXXXX"
  },
  "google_sheets": {
    "spreadsheet_name": "My Sheet",
    "notion_id_column": "Notion Page ID"
  },
  "rate_limit_delay": 0.1
}
```

### 3. Get Google Service Account Credentials

- Create a service account in Google Cloud Console
- Share your Google Sheet with the service account email
- Save credentials as `creds.json` in the root directory

---

## ▶️ Run the App

```bash
python main.py
```

---

## 📎 Notes

- First row in your sheet must match Notion property names
- Created pages write their Notion Page ID back into the sheet
- Make backups if your sheet has precious data (because bugs)

---

## 💡 Future Ideas

- Dry-run/preview mode
- Timestamp-based conflict resolution
- CLI version
- Web-deployable version via Flet cloud

---

## License

MIT – but you break it, you buy it.
