"""Offline S3 inspection checks; no AWS credentials or network needed."""

import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import Mock

from botocore.exceptions import ClientError
from injection.inspect_s3 import inspect


class InspectTests(unittest.TestCase):
    def test_pages_filter_utf8_and_preview(self):
        s3 = Mock()
        s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": "docs/a.txt"}, {"Key": "docs/skip.pdf"}]},
            {"Contents": [{"Key": "docs/b.TXT"}]},
        ]
        bodies = [io.BytesIO(("cafÃ© " * 60).encode()), io.BytesIO(b"one two")]
        s3.get_object.side_effect = [{"Body": body} for body in bodies]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(inspect(s3, "bucket", "docs/"), 0)
        s3.get_paginator.return_value.paginate.assert_called_once_with(Bucket="bucket", Prefix="docs/")
        self.assertEqual(s3.get_object.call_count, 2)
        self.assertIn("Word count: 60", output.getvalue())
        self.assertIn(repr(("cafÃ© " * 60)[:200]), output.getvalue())
        self.assertTrue(all(body.closed for body in bodies))

    def test_read_errors_continue(self):
        s3 = Mock()
        s3.get_paginator.return_value.paginate.return_value = [{"Contents": [
            {"Key": "denied.txt"}, {"Key": "invalid.txt"}, {"Key": "ok.txt"}]}]
        invalid = io.BytesIO(b"\xff")
        s3.get_object.side_effect = [
            ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject"),
            {"Body": invalid}, {"Body": io.BytesIO(b"ok")},
        ]
        errors = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            self.assertEqual(inspect(s3, "bucket", ""), 1)
        self.assertEqual(s3.get_object.call_count, 3)
        self.assertIn("s3:GetObject", errors.getvalue())
        self.assertIn("Invalid UTF-8", errors.getvalue())
        self.assertTrue(invalid.closed)

    def test_listing_denied(self):
        s3 = Mock()
        s3.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListObjectsV2")
        errors = io.StringIO()
        with redirect_stderr(errors):
            self.assertEqual(inspect(s3, "bucket", ""), 1)
        self.assertIn("s3:ListBucket", errors.getvalue())

    def test_empty_listing(self):
        s3 = Mock()
        s3.get_paginator.return_value.paginate.return_value = [{}]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(inspect(s3, "bucket", ""), 0)
        self.assertIn("No .txt files", output.getvalue())
        s3.get_object.assert_not_called()

