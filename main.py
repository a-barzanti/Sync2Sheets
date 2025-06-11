import os
import threading
import flet as ft
import logging
from datetime import datetime

from config import (
    NOTION_API_KEY,
    NOTION_DB_ID,
    GOOGLE_CREDENTIALS_FILE,
)

from sync import Sync2Sheets

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def show_snackbar(page: ft.Page, message: str, color: str = ft.Colors.GREEN):
    snackbar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
    page.overlay.append(snackbar)
    snackbar.open = True
    page.update()

# --- MAIN FLET APPLICATION ---
def main(page: ft.Page):
    page.title = "Notion ↔ Sheets Sync"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 600
    page.window.height = 400
    page.window.resizable = False

    sync_in_progress = ft.Ref[ft.Text]()
    progress_text = ft.Ref[ft.Text]()
    n2s_button = ft.Ref[ft.ElevatedButton]()
    s2n_button = ft.Ref[ft.ElevatedButton]()
    config_status = ft.Ref[ft.Text]()
    last_sync_info = ft.Ref[ft.Text]()

    def update_progress(message: str):
        if progress_text.current:
            progress_text.current.value = message
            page.update()

    def set_ui_locking(is_locked: bool):
        n2s_button.current.disabled = is_locked
        s2n_button.current.disabled = is_locked
        sync_in_progress.current.visible = is_locked
        progress_text.current.visible = is_locked
        page.update()

    def notion_to_sheets_task():
        set_ui_locking(True)
        try:
            sync_tool = Sync2Sheets(progress_callback=update_progress)
            sync_tool.sync_notion_to_sheets()
            summary = sync_tool.sync_stats
            show_snackbar(page, f"✅ Notion → Sheets sync complete! {summary}", ft.Colors.GREEN)
            last_sync_info.current.value = f"Last sync: {datetime.now().strftime('%Y-%m-%d %H:%M')} - {summary}"
        except Exception as e:
            show_snackbar(page, f"❌ Error: {str(e)[:100]}...", ft.Colors.RED)
            logger.error(f"Notion to Sheets sync error: {e}")
        finally:
            set_ui_locking(False)

    def sheets_to_notion_task():
        set_ui_locking(True)
        try:
            sync_tool = Sync2Sheets(progress_callback=update_progress)
            sync_tool.sync_sheets_to_notion()
            summary = sync_tool.sync_stats
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
        ft.Column([
            ft.Text(ref=config_status, value=config_status_text, size=14, color=config_color),
            ft.Text(ref=sync_in_progress, value="🔄 Sync in progress, please wait...", visible=False, color=ft.Colors.BLUE),
            ft.Text(ref=progress_text, value="", visible=False, color=ft.Colors.BLUE_GREY, size=12),
            ft.Row([
                ft.ElevatedButton(ref=n2s_button, text="Sync Notion → Sheets", on_click=handle_notion_to_sheets_click, width=250, height=50, disabled=buttons_disabled),
                ft.ElevatedButton(ref=s2n_button, text="Sync Sheets → Notion", on_click=handle_sheets_to_notion_click, width=250, height=50, disabled=buttons_disabled),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
            ft.Text(ref=last_sync_info, value="No recent sync operations", size=12, color=ft.Colors.GREY_600, italic=True),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)
    )

if __name__ == "__main__":
    ft.app(target=main)