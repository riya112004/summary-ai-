import unittest
from unittest.mock import patch

from bson import ObjectId

import main


class StartupDocumentOwnershipTests(unittest.TestCase):
    def test_missing_user_id_is_skipped_and_logged(self):
        document_id = ObjectId()
        with self.assertLogs(main.logger, level="ERROR") as logs:
            user_id = main._document_user_id({"_id": document_id})

        self.assertIsNone(user_id)
        self.assertIn(str(document_id), logs.output[0])

    def test_non_object_id_user_id_is_skipped(self):
        with patch.object(main.logger, "error") as log_error:
            user_id = main._document_user_id({"user_id": "not-an-object-id"})

        self.assertIsNone(user_id)
        log_error.assert_called_once()

    def test_object_id_user_id_is_returned(self):
        expected_user_id = ObjectId()

        self.assertEqual(
            main._document_user_id({"user_id": expected_user_id}),
            expected_user_id,
        )


if __name__ == "__main__":
    unittest.main()
