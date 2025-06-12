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

## 🤩 Project Structure

```
.
├── main.py         # Flet UI interface
├── sync.py         # Sync logic (Notion ↔ Sheets)
├── config.py       # Configuration & secrets
├── config.json     # User-defined settings (Not committed)
├── creds.json      # Google Service Account credentials (Not committed)
├── Makefile        # Run and manage the project
```

---

## 🔧 Setup Instructions

### 1. Clone & Create Virtual Environment

This projects uses uv as package manager,
Make sure you have `uv` installed (`pip install uv`),
otherwise this will just be a sad moment in your life.

```bash
make venv
```

### 2. Install Dependencies

```bash
source .venv/bin/activate
make install
```

### 3. Create `config.json`

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

### 4. Get Google Service Account Credentials

- Create a service account in Google Cloud Console
- Share your Google Sheet with the service account email
- Save the credentials as `creds.json` in the root directory

---

## ▶️ Run the App

```bash
make start
```

Or if you like doing things the long, inefficient way:

```bash
flet run main.py
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

## 📚 Makefile Usage

```bash
make help
```

This will show you all the available make commands:

- `make venv` — Create a virtual environment using `uv`
- `make install` — Sync dependencies from `pyproject.toml`
- `make start` — Launch the app
- `make clean` — Delete `.venv`, caches, and other junk

Don't forget to activate the virtual environment:

```bash
source .venv/bin/activate
```

To deactivate:

```bash
deactivate
```

---

## License

MIT – but you break it, you buy it.
