import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
import json
import sys
import os
from datetime import datetime
import requests

# Add the main module to the path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the flet import since it's not needed for testing the core logic
sys.modules['flet'] = MagicMock()

# Import the main module after mocking flet
from notion_sheets_sync import load_config, Sync2Sheets, show_snackbar

class TestConfigLoader(unittest.TestCase):
    """Test configuration loading functionality."""
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"notion": {"api_key": "test_key", "database_id": "test_db"}, "google_sheets": {"spreadsheet_name": "test_sheet"}}')
    def test_load_config_success(self):
        """Test successful configuration loading."""
        config = load_config()
        self.assertEqual(config["notion"]["api_key"], "test_key")
        self.assertEqual(config["notion"]["database_id"], "test_db")
        self.assertEqual(config["google_sheets"]["spreadsheet_name"], "test_sheet")
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_config_file_not_found(self):
        """Test configuration loading when file doesn't exist."""
        with self.assertRaises(Exception) as context:
            load_config()
        self.assertIn("config.json file not found", str(context.exception))
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_load_config_invalid_json(self):
        """Test configuration loading with invalid JSON."""
        with self.assertRaises(Exception) as context:
            load_config()
        self.assertIn("Invalid JSON format", str(context.exception))


class TestSync2Sheets(unittest.TestCase):
    """Test the main Sync2Sheets class functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = {
            "notion": {
                "api_key": "test_api_key",
                "database_id": "test_db_id"
            },
            "google_sheets": {
                "spreadsheet_name": "test_spreadsheet",
                "notion_id_column": "Notion Page ID",
                "credentials_file": "test_credentials.json"
            },
            "rate_limit_delay": 0.1
        }
        
        # Mock the global CONFIG
        with patch('notion_sheets_sync.CONFIG', self.mock_config):
            with patch('notion_sheets_sync.NOTION_API_KEY', 'test_api_key'):
                with patch('notion_sheets_sync.NOTION_DB_ID', 'test_db_id'):
                    with patch('notion_sheets_sync.SPREADSHEET_NAME', 'test_spreadsheet'):
                        with patch('notion_sheets_sync.NOTION_ID_COLUMN', 'Notion Page ID'):
                            with patch('notion_sheets_sync.GOOGLE_CREDENTIALS_FILE', 'test_credentials.json'):
                                with patch.object(Sync2Sheets, '_get_gs_client'):
                                    with patch.object(Sync2Sheets, '_get_sheet'):
                                        with patch.object(Sync2Sheets, '_fetch_notion_db_schema'):
                                            self.sync_tool = Sync2Sheets()
        
        # Mock the dependencies
        self.sync_tool.gs_client = Mock()
        self.sync_tool.sheet = Mock()
        self.sync_tool.notion_db_schema = {
            "Title": {"type": "title"},
            "Status": {"type": "select", "select": {"options": [{"name": "Active"}, {"name": "Inactive"}]}},
            "Number": {"type": "number"},
            "Date": {"type": "date"},
            "Checkbox": {"type": "checkbox"},
            "Rich Text": {"type": "rich_text"},
            "Multi Select": {"type": "multi_select"},
            "URL": {"type": "url"},
            "Email": {"type": "email"}
        }
    
    @patch('notion_sheets_sync.Credentials')
    @patch('notion_sheets_sync.gspread')
    def test_get_gs_client_success(self, mock_gspread, mock_credentials):
        """Test successful Google Sheets client initialization."""
        mock_creds = Mock()
        mock_credentials.from_service_account_file.return_value = mock_creds
        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client
        
        with patch('notion_sheets_sync.GOOGLE_CREDENTIALS_FILE', 'test_creds.json'):
            sync_tool = Sync2Sheets.__new__(Sync2Sheets)
            result = sync_tool._get_gs_client()
        
        mock_credentials.from_service_account_file.assert_called_once()
        mock_gspread.authorize.assert_called_once_with(mock_creds)
        self.assertEqual(result, mock_client)
    
    @patch('notion_sheets_sync.Credentials')
    def test_get_gs_client_file_not_found(self, mock_credentials):
        """Test Google Sheets client initialization with missing credentials file."""
        mock_credentials.from_service_account_file.side_effect = FileNotFoundError()
        
        sync_tool = Sync2Sheets.__new__(Sync2Sheets)
        with self.assertRaises(Exception) as context:
            sync_tool._get_gs_client()
        
        self.assertIn("Google credentials file not found", str(context.exception))
    
    def test_get_sheet_success(self):
        """Test successful sheet access."""
        mock_spreadsheet = Mock()
        mock_sheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet
        self.sync_tool.gs_client.open.return_value = mock_spreadsheet
        
        with patch('notion_sheets_sync.SPREADSHEET_NAME', 'test_sheet'):
            result = self.sync_tool._get_sheet()
        
        self.sync_tool.gs_client.open.assert_called_once_with('test_sheet')
        self.assertEqual(result, mock_sheet)
    
    def test_get_sheet_not_found(self):
        """Test sheet access when spreadsheet doesn't exist."""
        import gspread
        self.sync_tool.gs_client.open.side_effect = gspread.exceptions.SpreadsheetNotFound()
        
        with self.assertRaises(Exception) as context:
            self.sync_tool._get_sheet()
        
        self.assertIn("Spreadsheet", str(context.exception))
        self.assertIn("not found", str(context.exception))
    
    @patch('notion_sheets_sync.requests.get')
    def test_fetch_notion_db_schema_success(self, mock_get):
        """Test successful Notion database schema fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "properties": {
                "Title": {"type": "title"},
                "Status": {"type": "select"}
            }
        }
        mock_get.return_value = mock_response
        
        sync_tool = Sync2Sheets.__new__(Sync2Sheets)
        with patch('notion_sheets_sync.NOTION_DB_ID', 'test_db_id'):
            result = sync_tool._fetch_notion_db_schema()
        
        expected_url = "https://api.notion.com/v1/databases/test_db_id"
        mock_get.assert_called_once()
        self.assertEqual(result["Title"]["type"], "title")
        self.assertEqual(result["Status"]["type"], "select")
    
    @patch('notion_sheets_sync.requests.get')
    def test_fetch_notion_db_schema_failure(self, mock_get):
        """Test Notion database schema fetching failure."""
        mock_get.side_effect = requests.exceptions.RequestException("API Error")
        
        sync_tool = Sync2Sheets.__new__(Sync2Sheets)
        with self.assertRaises(Exception) as context:
            sync_tool._fetch_notion_db_schema()
        
        self.assertIn("Failed to fetch Notion database schema", str(context.exception))
    
    def test_extract_value_from_prop_title(self):
        """Test value extraction from title property."""
        prop = {
            "type": "title",
            "title": [{"plain_text": "Test Title"}]
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "Test Title")
    
    def test_extract_value_from_prop_rich_text(self):
        """Test value extraction from rich text property."""
        prop = {
            "type": "rich_text",
            "rich_text": [
                {"plain_text": "Hello "},
                {"plain_text": "World"}
            ]
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "Hello World")
    
    def test_extract_value_from_prop_select(self):
        """Test value extraction from select property."""
        prop = {
            "type": "select",
            "select": {"name": "Active"}
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "Active")
    
    def test_extract_value_from_prop_multi_select(self):
        """Test value extraction from multi-select property."""
        prop = {
            "type": "multi_select",
            "multi_select": [
                {"name": "Tag1"},
                {"name": "Tag2"}
            ]
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "Tag1, Tag2")
    
    def test_extract_value_from_prop_number(self):
        """Test value extraction from number property."""
        prop = {
            "type": "number",
            "number": 42.5
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "42.5")
    
    def test_extract_value_from_prop_checkbox(self):
        """Test value extraction from checkbox property."""
        prop_true = {
            "type": "checkbox",
            "checkbox": True
        }
        prop_false = {
            "type": "checkbox",
            "checkbox": False
        }
        
        result_true = self.sync_tool._extract_value_from_prop(prop_true)
        result_false = self.sync_tool._extract_value_from_prop(prop_false)
        
        self.assertEqual(result_true, "TRUE")
        self.assertEqual(result_false, "FALSE")
    
    def test_extract_value_from_prop_date(self):
        """Test value extraction from date property."""
        prop = {
            "type": "date",
            "date": {"start": "2023-12-01", "end": "2023-12-02"}
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "2023-12-01 to 2023-12-02")
    
    def test_extract_value_from_prop_empty(self):
        """Test value extraction from empty property."""
        prop = {
            "type": "title",
            "title": None
        }
        result = self.sync_tool._extract_value_from_prop(prop)
        self.assertEqual(result, "")
    
    def test_format_notion_page_for_sheet(self):
        """Test formatting Notion page data for sheet row."""
        page = {
            "id": "page123",
            "properties": {
                "Title": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}]
                },
                "Status": {
                    "type": "select",
                    "select": {"name": "Active"}
                }
            }
        }
        
        headers = ["Title", "Status", "Notion Page ID"]
        result = self.sync_tool._format_notion_page_for_sheet(page, headers)
        
        expected = ["Test Page", "Active", "page123"]
        self.assertEqual(result, expected)
    
    def test_build_notion_properties_from_row_title(self):
        """Test building Notion properties from sheet row - title."""
        row = ["Test Title", "Active", "page123"]
        headers = ["Title", "Status", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_title = {"title": [{"text": {"content": "Test Title"}}]}
        self.assertEqual(result["Title"], expected_title)
    
    def test_build_notion_properties_from_row_number(self):
        """Test building Notion properties from sheet row - number."""
        self.sync_tool.notion_db_schema["Price"] = {"type": "number"}
        row = ["Test", "42.5", "page123"]
        headers = ["Title", "Price", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_price = {"number": 42.5}
        self.assertEqual(result["Price"], expected_price)
    
    def test_build_notion_properties_from_row_checkbox(self):
        """Test building Notion properties from sheet row - checkbox."""
        self.sync_tool.notion_db_schema["Completed"] = {"type": "checkbox"}
        row = ["Test", "TRUE", "page123"]
        headers = ["Title", "Completed", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_checkbox = {"checkbox": True}
        self.assertEqual(result["Completed"], expected_checkbox)
    
    def test_build_notion_properties_from_row_select(self):
        """Test building Notion properties from sheet row - select."""
        row = ["Test", "Active", "page123"]
        headers = ["Title", "Status", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_select = {"select": {"name": "Active"}}
        self.assertEqual(result["Status"], expected_select)
    
    def test_build_notion_properties_from_row_multi_select(self):
        """Test building Notion properties from sheet row - multi-select."""
        self.sync_tool.notion_db_schema["Tags"] = {"type": "multi_select"}
        row = ["Test", "Tag1, Tag2", "page123"]
        headers = ["Title", "Tags", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_multi_select = {"multi_select": [{"name": "Tag1"}, {"name": "Tag2"}]}
        self.assertEqual(result["Tags"], expected_multi_select)
    
    def test_build_notion_properties_from_row_date(self):
        """Test building Notion properties from sheet row - date."""
        self.sync_tool.notion_db_schema["Due Date"] = {"type": "date"}
        row = ["Test", "2023-12-01", "page123"]
        headers = ["Title", "Due Date", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_date = {"date": {"start": "2023-12-01"}}
        self.assertEqual(result["Due Date"], expected_date)
    
    def test_build_notion_properties_from_row_url(self):
        """Test building Notion properties from sheet row - URL."""
        self.sync_tool.notion_db_schema["Website"] = {"type": "url"}
        row = ["Test", "https://example.com", "page123"]
        headers = ["Title", "Website", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_url = {"url": "https://example.com"}
        self.assertEqual(result["Website"], expected_url)
    
    def test_build_notion_properties_from_row_email(self):
        """Test building Notion properties from sheet row - email."""
        self.sync_tool.notion_db_schema["Contact"] = {"type": "email"}
        row = ["Test", "test@example.com", "page123"]
        headers = ["Title", "Contact", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        expected_email = {"email": "test@example.com"}
        self.assertEqual(result["Contact"], expected_email)
    
    def test_build_notion_properties_invalid_number(self):
        """Test building Notion properties with invalid number."""
        self.sync_tool.notion_db_schema["Price"] = {"type": "number"}
        row = ["Test", "invalid_number", "page123"]
        headers = ["Title", "Price", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        # Should skip invalid number
        self.assertNotIn("Price", result)
    
    def test_build_notion_properties_invalid_url(self):
        """Test building Notion properties with invalid URL."""
        self.sync_tool.notion_db_schema["Website"] = {"type": "url"}
        row = ["Test", "not_a_url", "page123"]
        headers = ["Title", "Website", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        # Should skip invalid URL
        self.assertNotIn("Website", result)
    
    def test_build_notion_properties_invalid_email(self):
        """Test building Notion properties with invalid email."""
        self.sync_tool.notion_db_schema["Contact"] = {"type": "email"}
        row = ["Test", "not_an_email", "page123"]
        headers = ["Title", "Contact", "Notion Page ID"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        # Should skip invalid email
        self.assertNotIn("Contact", result)
    
    @patch('notion_sheets_sync.requests.post')
    def test_fetch_all_notion_pages_single_page(self, mock_post):
        """Test fetching Notion pages without pagination."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [{"id": "page1"}, {"id": "page2"}],
            "has_more": False,
            "next_cursor": None
        }
        mock_post.return_value = mock_response
        
        result = self.sync_tool._fetch_all_notion_pages()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "page1")
        self.assertEqual(result[1]["id"], "page2")
        mock_post.assert_called_once()
    
    @patch('notion_sheets_sync.requests.post')
    @patch('notion_sheets_sync.time.sleep')
    def test_fetch_all_notion_pages_with_pagination(self, mock_sleep, mock_post):
        """Test fetching Notion pages with pagination."""
        # First call - has more pages
        first_response = Mock()
        first_response.json.return_value = {
            "results": [{"id": "page1"}],
            "has_more": True,
            "next_cursor": "cursor1"
        }
        
        # Second call - last page
        second_response = Mock()
        second_response.json.return_value = {
            "results": [{"id": "page2"}],
            "has_more": False,
            "next_cursor": None
        }
        
        mock_post.side_effect = [first_response, second_response]
        
        result = self.sync_tool._fetch_all_notion_pages()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "page1")
        self.assertEqual(result[1]["id"], "page2")
        self.assertEqual(mock_post.call_count, 2)
        
        # Verify second call includes cursor
        second_call_args = mock_post.call_args_list[1]
        self.assertEqual(second_call_args[1]["json"]["start_cursor"], "cursor1")
    
    @patch('notion_sheets_sync.requests.post')
    def test_fetch_all_notion_pages_api_error(self, mock_post):
        """Test fetching Notion pages with API error."""
        mock_post.side_effect = requests.exceptions.RequestException("API Error")
        
        with self.assertRaises(Exception) as context:
            self.sync_tool._fetch_all_notion_pages()
        
        self.assertIn("Failed to fetch Notion pages", str(context.exception))
    
    @patch.object(Sync2Sheets, '_fetch_all_notion_pages')
    def test_sync_notion_to_sheets(self, mock_fetch_pages):
        """Test syncing from Notion to Sheets."""
        # Mock Notion pages
        mock_pages = [
            {
                "id": "page1",
                "properties": {
                    "Title": {
                        "type": "title",
                        "title": [{"plain_text": "Page 1"}]
                    }
                }
            }
        ]
        mock_fetch_pages.return_value = mock_pages
        
        # Mock sheet operations
        self.sync_tool.sheet.clear = Mock()
        self.sync_tool.sheet.update = Mock()
        
        # Run sync
        self.sync_tool.sync_notion_to_sheets()
        
        # Verify operations
        self.sync_tool.sheet.clear.assert_called_once()
        self.sync_tool.sheet.update.assert_called_once()
        
        # Check that update was called with correct data structure
        update_call = self.sync_tool.sheet.update.call_args
        self.assertEqual(update_call[1]["range_name"], "A1")
        self.assertIsInstance(update_call[1]["values"], list)
        self.assertEqual(self.sync_tool.sync_stats["updated"], 1)
    
    def test_sync_sheets_to_notion_empty_sheet(self):
        """Test syncing from Sheets to Notion with empty sheet."""
        self.sync_tool.sheet.get_all_values.return_value = []
        
        with self.assertRaises(Exception) as context:
            self.sync_tool.sync_sheets_to_notion()
        
        self.assertIn("Sheet is empty", str(context.exception))
    
    def test_sync_sheets_to_notion_missing_id_column(self):
        """Test syncing from Sheets to Notion without ID column."""
        self.sync_tool.sheet.get_all_values.return_value = [
            ["Title", "Status"],
            ["Page 1", "Active"]
        ]
        
        with self.assertRaises(Exception) as context:
            self.sync_tool.sync_sheets_to_notion()
        
        self.assertIn("Notion Page ID", str(context.exception))
        self.assertIn("not found", str(context.exception))
    
    @patch('notion_sheets_sync.requests.post')
    @patch('notion_sheets_sync.requests.patch')
    @patch('notion_sheets_sync.time.sleep')
    def test_sync_sheets_to_notion_success(self, mock_sleep, mock_patch, mock_post):
        """Test successful syncing from Sheets to Notion."""
        # Mock sheet data
        self.sync_tool.sheet.get_all_values.return_value = [
            ["Title", "Status", "Notion Page ID"],
            ["New Page", "Active", ""],  # New page
            ["Existing Page", "Inactive", "existing_id"]  # Existing page
        ]
        
        # Mock API responses
        mock_post_response = Mock()
        mock_post_response.json.return_value = {"id": "new_page_id"}
        mock_post.return_value = mock_post_response
        
        mock_patch_response = Mock()
        mock_patch.return_value = mock_patch_response
        
        # Mock sheet update for new page ID
        self.sync_tool.sheet.update = Mock()
        
        # Run sync
        self.sync_tool.sync_sheets_to_notion()
        
        # Verify API calls
        mock_post.assert_called_once()  # Create new page
        mock_patch.assert_called_once()  # Update existing page
        
        # Verify sheet update with new page ID
        self.sync_tool.sheet.update.assert_called_once()
        
        # Check sync stats
        self.assertEqual(self.sync_tool.sync_stats["created"], 1)
        self.assertEqual(self.sync_tool.sync_stats["updated"], 1)
        self.assertEqual(self.sync_tool.sync_stats["errors"], 0)
    
    def test_get_sync_summary(self):
        """Test sync summary generation."""
        self.sync_tool.sync_stats = {"created": 2, "updated": 3, "errors": 1}
        
        summary = self.sync_tool.get_sync_summary()
        
        expected = "Created: 2, Updated: 3, Errors: 1"
        self.assertEqual(summary, expected)
    
    def test_update_progress_with_callback(self):
        """Test progress update with callback."""
        progress_messages = []
        
        def mock_callback(message):
            progress_messages.append(message)
        
        sync_tool = Sync2Sheets.__new__(Sync2Sheets)
        sync_tool.progress_callback = mock_callback
        sync_tool._update_progress("Test message")
        
        self.assertEqual(len(progress_messages), 1)
        self.assertEqual(progress_messages[0], "Test message")
    
    def test_update_progress_without_callback(self):
        """Test progress update without callback."""
        sync_tool = Sync2Sheets.__new__(Sync2Sheets)
        sync_tool.progress_callback = None
        
        # Should not raise an exception
        sync_tool._update_progress("Test message")


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def test_show_snackbar(self):
        """Test snackbar display function."""
        mock_page = Mock()
        mock_page.overlay = []
        
        show_snackbar(mock_page, "Test message", "green")
        
        # Verify snackbar was added to overlay
        self.assertEqual(len(mock_page.overlay), 1)
        snackbar = mock_page.overlay[0]
        self.assertTrue(snackbar.open)
        mock_page.update.assert_called_once()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch.object(Sync2Sheets, '_get_gs_client'):
            with patch.object(Sync2Sheets, '_get_sheet'):
                with patch.object(Sync2Sheets, '_fetch_notion_db_schema'):
                    self.sync_tool = Sync2Sheets()
        
        self.sync_tool.gs_client = Mock()
        self.sync_tool.sheet = Mock()
        self.sync_tool.notion_db_schema = {
            "Title": {"type": "title"},
            "Rich Text": {"type": "rich_text"}
        }
    
    def test_extract_value_very_long_text(self):
        """Test value extraction with very long text."""
        long_text = "x" * 2000
        prop = {
            "type": "title",
            "title": [{"plain_text": long_text}]
        }
        
        result = self.sync_tool._extract_value_from_prop(prop)
        
        # Should truncate or handle long text appropriately
        self.assertIsInstance(result, str)
        self.assertLessEqual(len(result), 2100)  # With "..." suffix
    
    def test_build_properties_with_empty_row(self):
        """Test building properties with empty row data."""
        row = []
        headers = ["Title", "Status"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        # Should handle empty row gracefully
        self.assertIsInstance(result, dict)
    
    def test_build_properties_with_none_values(self):
        """Test building properties with None values in row."""
        row = [None, "Active"]
        headers = ["Title", "Status"]
        
        result = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        # Should handle None values gracefully
        self.assertIsInstance(result, dict)
    
    def test_extract_value_from_malformed_prop(self):
        """Test value extraction from malformed property."""
        prop = {
            "type": "title",
            # Missing the actual title data
        }
        
        result = self.sync_tool._extract_value_from_prop(prop)
        
        # Should return empty string for malformed property
        self.assertEqual(result, "")
    
    def test_checkbox_variations(self):
        """Test checkbox property with various input formats."""
        test_cases = [
            ("TRUE", True),
            ("true", True),
            ("YES", True),
            ("yes", True),
            ("1", True),
            ("✓", True),
            ("FALSE", False),
            ("false", False),
            ("NO", False),
            ("0", False),
            ("", False),
            ("random", False)
        ]
        
        self.sync_tool.notion_db_schema["Checkbox"] = {"type": "checkbox"}
        
        for input_val, expected in test_cases:
            row = ["Title", input_val]
            headers = ["Title", "Checkbox"]
            
            result = self.sync_tool._build_notion_properties_from_row(row, headers)
            
            if "Checkbox" in result:
                self.assertEqual(result["Checkbox"]["checkbox"], expected, 
                               f"Failed for input: {input_val}")


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestConfigLoader,
        TestSync2Sheets,
        TestUtilityFunctions,
        TestEdgeCases
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite