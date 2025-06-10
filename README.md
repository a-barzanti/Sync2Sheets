# Sync2Sheets: Notion ↔ Google Sheets Sync

Sync2Sheets is a desktop application that provides a simple and powerful way to perform two-way synchronization between a Notion database and a Google Sheet. Built with Python and Flet, it offers a clean user interface to trigger syncs, ensuring your data remains consistent across both platforms.

It's an intelligent tool that updates existing entries rather than creating duplicates, making it ideal for managing workflows, tracking data, or creating backups.

Features
Bi-Directional Sync: Sync your data from Notion to Google Sheets and from Google Sheets back to Notion.

Intelligent Updates: Avoids creating duplicate entries by using a unique Notion Page ID to map records between the two services. Existing records are updated in place.

Dynamic Property Handling: Automatically fetches your Notion database's schema to correctly handle various property types like Text, Number, Select, Status, and more.

Responsive UI: The application's interface remains responsive during sync operations, thanks to multi-threading.

Clear Feedback: Get instant success or error notifications for each sync operation.

Installation & Setup
Follow these steps to get Sync2Sheets up and running on your local machine.

Prerequisites
Python 3.8 or newer

A Notion account with an integration token

A Google Cloud account with a service account

Step 1: Clone or Download the Code
First, get the source code for the application (notion_sync_app.py).

Step 2: Install Dependencies
Open your terminal or command prompt and install the required Python libraries:

pip install flet gspread google-auth-oauthlib requests

Step 3: Configure Notion
Create a Notion Integration: Go to My Integrations and create a new integration. Give it a name (e.g., "Sync2Sheets Integration") and copy the Internal Integration Token.

Share your Database: Open the Notion database you want to sync, click the ••• menu, and under "Add connections", select the integration you just created.

Get Database ID: The ID is part of your database URL. For https://www.notion.so/your-workspace/DATABASE_ID?v=..., the DATABASE_ID is the part you need.

Step 4: Configure Google Cloud & Sheets
Enable APIs: Go to the Google Cloud Console, create a new project, and enable the Google Sheets API and Google Drive API.

Create a Service Account: In the "Credentials" section, create a new Service Account. Give it a name and grant it the "Editor" role.

Generate a Key: After creating the service account, generate a new JSON key for it. A google-credentials.json file will be downloaded. Place this file in the same directory as the application script.

Share your Google Sheet: Create a new Google Sheet (or use an existing one). Click the "Share" button and paste the service account's email address (found in your google-credentials.json file under client_email) into the sharing dialog, giving it "Editor" permissions.

Step 5: Set Environment Variables
The application requires two environment variables to connect to Notion.

NOTION_API_KEY: Your Internal Integration Token from Step 3.1.

NOTION_DB_ID: Your Database ID from Step 3.3.

You can set them in your terminal:

On macOS/Linux:

export NOTION_API_KEY="your_notion_api_key"
export NOTION_DB_ID="your_database_id"

On Windows (Command Prompt):

set NOTION_API_KEY="your_notion_api_key"
set NOTION_DB_ID="your_database_id"

How to Use
Once all the configuration is complete, you can run the application.

Open your terminal in the project directory.

Run the script:

python notion_sync_app.py

The Sync2Sheets window will appear.

Click Sync Notion → Sheets to pull all data from your Notion database into the specified Google Sheet.

Click Sync Sheets → Notion to push all data from the Google Sheet back to Notion.

Supported Property Types
Sync2Sheets can read and write to the following Notion property types:

Title

Rich Text

Number

Select

Status

Multi-select (comma-separated in Sheets)

Checkbox (TRUE/FALSE in Sheets)

Date

URL

Email

Phone Number

The following types are read-only (from Notion to Sheets):

People

Formula

Relation (shows a count of related items)

---

## 💡 Features

- Native GUI using Flet (not another web app in disguise)
- Scrapes job listing text using Playwright (headless browser)
- Uses GPT to extract Company + Role automatically
- Writes to your personal Google Sheet (because yes, you still need hope)
- Minimal, fast, and cross-platform
- One click to parse job postings with GPT
- One click to refresh your existential dread ☠️

---

## 🚀 Requirements

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) or plain `pip`
- A Google Spreadsheet (with at least some hopes and dreams)
- A Google Cloud **Service Account**
- An OpenAI API key
- A basic will to keep applying

---

## 🔧 Setup Instructions

### 1. 📁 Clone this repo

```bash
git clone https://github.com/a-barzanti/gpt-powered-job-applications-tracker.git
cd gpt-powered-job-applications-tracker
```

---

### 2. 🐍 Create a virtual environment

Using `uv` (recommended):

```bash
uv venv
source .venv/bin/activate
```

Or with `venv`:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

---

### 3. 📦 Install dependencies

Using `uv`:

```bash
uv pip install "flet[all]" gspread google-auth openai playwright beautifulsoup4
```

Or with `pip`:

```bash
pip install "flet[all]" gspread google-auth openai playwright beautifulsoup4
```

Then install Playwright’s browser dependencies:

```bash
playwright install
```

---

### 4. 🔐 Set up Google Sheets access

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (e.g., "Job Tracker")
3. Go to **IAM & Admin → Service Accounts**
4. Create a new service account
5. Generate a **JSON key** and download it
6. Place the file in your project folder as `creds.json`
7. Share your Google Sheet with the service account email  
   (e.g., `your-bot@jobtracker.iam.gserviceaccount.com`)

---

### 5. 🧾 Set up your OpenAI API key

1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new key
3. Save it to a text file named `openai_key.txt` in your project root  
   (Yes, just a plain file with the key inside. Nothing fancy.)

---

### 6. 📝 Create your spreadsheet

Create a Google Sheet with **this exact name**:

```
Job Applications Tracker
```

And make sure the first row has these columns:

| Company | Role | Status | Date Applied | URL |
| ------- | ---- | ------ | ------------ | --- |

It must be shared with your service account. Otherwise, your app will silently cry in a corner and do nothing.

---

### 7. 🧪 Run the app

```bash
python app.py
```

A glorious little window will open, scraping job listings and extracting info while you sip your cold brew and question your life choices.

---

## 🛡️ `.gitignore` Safety Reminder

```bash
echo creds.json >> .gitignore
echo openai_key.txt >> .gitignore
```

Because accidentally uploading your keys to GitHub is the fastest way to become poor.

---

## 📦 Optional: Package as Desktop App

You can package this app as a standalone `.exe`, `.app`, or binary using [Flet's packaging guide](https://flet.dev/docs/guides/packaging/overview).

---

## 🧠 Ideas for Future Features

- Form UI to manually submit new job applications
- Filters for status (applied, interviewed, ghosted, rage quit, etc.)
- Email reminders (you asked for this, not me)
- Dashboard showing your ratio of effort vs success
- Built-in coping mechanism

---

## 👨‍💻 Author

Built by someone tired of tracking job apps in spreadsheets — and even more tired of forgetting which companies ghosted them.

---

## 📄 License

MIT. Use it, break it, ignore it — just don’t @ me when it fails.

---

> “Hope is not a strategy, but this app kinda is.” – Alessandro Barzanti
