import unittest
from unittest.mock import patch, MagicMock, call
import os

# Important: You need to import the script you are testing.
# For this to work, save your main script as 'notion_sync_app.py'
# in the same directory as this test file.
from main import Sync2Sheets

class TestSync2Sheets(unittest.TestCase):
    """Unit tests for the NotionSync class."""

    def setUp(self):
        """Set up mock environment for each test."""
        # Mock environment variables
        os.environ["NOTION_API_KEY"] = "test_key"
        os.environ["NOTION_DB_ID"] = "test_db_id"

        # --- Mock Data ---
        self.mock_db_schema = {
            "Name": {"id": "title", "type": "title", "title": {}},
            "Status": {"id": "status_id", "type": "status", "status": {}},
            "Tags": {"id": "tags_id", "type": "multi_select", "multi_select": {}},
            "Link": {"id": "link_id", "type": "url", "url": {}},
            "Contact": {"id": "email_id", "type": "email", "email": {}},
            "Cost": {"id": "cost_id", "type": "number", "number": {}},
        }

        self.mock_notion_pages = [
            {
                "id": "page-id-1",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Task A"}]},
                    "Status": {"type": "status", "status": {"name": "In Progress"}},
                    "Tags": {"type": "multi_select", "multi_select": [{"name": "Urgent"}, {"name": "ProjectX"}]},
                    "Link": {"type": "url", "url": "https://example.com"},
                    "Contact": {"type": "email", "email": "a@example.com"},
                    "Cost": {"type": "number", "number": 100},
                }
            },
            {
                "id": "page-id-2",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Task B"}]},
                    "Status": {"type": "status", "status": {"name": "Done"}},
                    "Tags": {"type": "multi_select", "multi_select": []},
                    "Link": {"type": "url", "url": None},
                    "Contact": {"type": "email", "email": None},
                    "Cost": {"type": "number", "number": 25.5},
                }
            }
        ]
        
        # We patch the external dependencies for the duration of the test.
        # This prevents any real network calls from being made.
        self.patcher_gspread = patch('notion_sync_app.gspread.authorize')
        self.patcher_requests_get = patch('notion_sync_app.requests.get')
        self.patcher_requests_post = patch('notion_sync_app.requests.post')
        self.patcher_requests_patch = patch('notion_sync_app.requests.patch')
        self.patcher_creds = patch('notion_sync_app.Credentials.from_service_account_file')
        
        self.mock_gspread_authorize = self.patcher_gspread.start()
        self.mock_requests_get = self.patcher_requests_get.start()
        self.mock_requests_post = self.patcher_requests_post.start()
        self.mock_requests_patch = self.patcher_requests_patch.start()
        self.mock_creds = self.patcher_creds.start()

        # Configure the mock return values
        self.mock_sheet = MagicMock()
        self.mock_gs_client = MagicMock()
        self.mock_gs_client.open.return_value.sheet1 = self.mock_sheet
        self.mock_gspread_authorize.return_value = self.mock_gs_client

        # Mock for fetching the Notion DB schema
        mock_schema_response = MagicMock()
        mock_schema_response.json.return_value = {"properties": self.mock_db_schema}
        self.mock_requests_get.return_value = mock_schema_response

        # Instantiate the class we are testing
        self.sync_tool = Sync2Sheets()
        
    def tearDown(self):
        """Clean up patches after each test."""
        self.patcher_gspread.stop()
        self.patcher_requests_get.stop()
        self.patcher_requests_post.stop()
        self.patcher_requests_patch.stop()
        self.patcher_creds.stop()

    def test_extract_value_from_prop(self):
        """Test the extraction of values from various Notion property types."""
        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "title", "title": [{"plain_text": "Hello World"}]}
        ), "Hello World")
        
        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "status", "status": {"name": "Done"}}
        ), "Done")

        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "multi_select", "multi_select": [{"name": "A"}, {"name": "B"}]}
        ), "A, B")

        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "number", "number": 123}
        ), "123")

        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "url", "url": "https://notion.so"}
        ), "https://notion.so")

        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "checkbox", "checkbox": True}
        ), "TRUE")
        
        self.assertEqual(self.sync_tool._extract_value_from_prop(
            {"type": "checkbox", "checkbox": False}
        ), "FALSE")

    def test_build_notion_properties_from_row(self):
        """Test the construction of a Notion API payload from a sheet row."""
        headers = ["Name", "Status", "Tags", "Link", "Cost", "Notion Page ID"]
        row = ["New Task", "To Do", "Urgent, High-Priority", "https://notion.so", "99.99", "page-id-3"]
        
        properties = self.sync_tool._build_notion_properties_from_row(row, headers)
        
        self.assertIn("Name", properties)
        self.assertEqual(properties["Name"]["title"][0]["text"]["content"], "New Task")
        
        self.assertIn("Status", properties)
        self.assertEqual(properties["Status"]["status"]["name"], "To Do")

        self.assertIn("Tags", properties)
        self.assertEqual(len(properties["Tags"]["multi_select"]), 2)
        self.assertEqual(properties["Tags"]["multi_select"][0]["name"], "Urgent")
        
        self.assertIn("Link", properties)
        self.assertEqual(properties["Link"]["url"], "https://notion.so")

        self.assertIn("Cost", properties)
        self.assertEqual(properties["Cost"]["number"], 99.99)
        
        self.assertNotIn("Notion Page ID", properties) # Should be skipped

    def test_sync_notion_to_sheets(self):
        """Test the full flow from Notion to Sheets."""
        # Mock the Notion API response for fetching pages
        mock_pages_response = MagicMock()
        mock_pages_response.json.return_value = {"results": self.mock_notion_pages, "has_more": False}
        self.mock_requests_post.return_value = mock_pages_response

        # Mock the sheet's current state (empty)
        self.mock_sheet.get_all_records.return_value = []
        self.mock_sheet.row_count = 0
        
        # Run the sync
        self.sync_tool.sync_notion_to_sheets()
        
        # Assert that the sheet was cleared and headers were written
        self.mock_sheet.clear.assert_called_once()
        
        # Check that headers were written correctly
        expected_headers = list(self.mock_db_schema.keys()) + ["Notion Page ID"]
        self.mock_sheet.append_row.assert_called_with(expected_headers)
        
        # Check that the page data was appended correctly
        self.mock_sheet.append_rows.assert_called_once()
        appended_data = self.mock_sheet.append_rows.call_args[0][0]
        
        # Verify data for the first page
        self.assertEqual(len(appended_data), 2)
        self.assertEqual(appended_data[0][0], "Task A") # Name
        self.assertEqual(appended_data[0][1], "In Progress") # Status
        self.assertEqual(appended_data[0][2], "Urgent, ProjectX") # Tags
        self.assertEqual(appended_data[0][-1], "page-id-1") # Notion Page ID

    def test_sync_sheets_to_notion_update_and_create(self):
        """Test the full flow from Sheets to Notion, handling both updates and creations."""
        # Mock sheet data: one row with an ID (update) and one without (create)
        headers = ["Name", "Status", "Notion Page ID"]
        # Manually adjust schema for this test to match headers
        self.sync_tool.notion_db_schema = {
            "Name": {"type": "title"}, "Status": {"type": "status"}
        }
        rows = [
            headers,
            ["Updated Task", "Done", "page-to-update-id"],
            ["New Task", "To Do", ""],
        ]
        self.mock_sheet.get_all_values.return_value = rows

        # Mock the response for the "create" call
        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {'id': 'new-page-id'}
        
        # Set up side effects for API calls
        # requests.post will be called for the new task
        # requests.patch will be called for the updated task
        self.mock_requests_post.return_value = mock_create_response
        self.mock_requests_patch.return_value = MagicMock() # Just a successful patch

        # Run the sync
        self.sync_tool.sync_sheets_to_notion()
        
        # Assert PATCH was called for the existing page
        self.mock_requests_patch.assert_called_once()
        patch_call_args = self.mock_requests_patch.call_args
        self.assertIn("page-to-update-id", patch_call_args[0][0]) # Check URL
        self.assertEqual(patch_call_args[1]['json']['properties']['Name']['title'][0]['text']['content'], 'Updated Task')

        # Assert POST was called for the new page
        self.mock_requests_post.assert_called_once()
        post_call_args = self.mock_requests_post.call_args
        self.assertIn("https://api.notion.com/v1/pages", post_call_args[0][0])
        self.assertEqual(post_call_args[1]['json']['properties']['Name']['title'][0]['text']['content'], 'New Task')
        
        # Assert that the new ID was written back to the sheet
        self.mock_sheet.update_cell.assert_called_once_with(3, 3, 'new-page-id')


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
