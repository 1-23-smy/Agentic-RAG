from pathlib import Path
import unittest


class StreamlitUploadUiTest(unittest.TestCase):
    def test_ui_contains_upload_polling_and_existing_chat_flow(self):
        source = Path("ui/app.py").read_text()

        self.assertIn("st.file_uploader", source)
        self.assertIn("/ingest/upload", source)
        self.assertIn("/ingest/status/", source)
        self.assertIn("st.toast", source)
        self.assertIn("active_ingestion", source)
        self.assertIn("http://127.0.0.1:8000/chat", source)


if __name__ == "__main__":
    unittest.main()
