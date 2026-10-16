import email.message
import io
import json
import os
import tempfile
import unittest
import urllib.error
import zipfile
from unittest import mock

import oreilly_downloader as od


def http_error(code, retry_after=None):
    headers = email.message.Message()
    if retry_after is not None:
        headers['Retry-After'] = retry_after
    return urllib.error.HTTPError('https://example.com', code, 'error', headers, io.BytesIO())


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SafeFilenameTests(unittest.TestCase):
    def test_keeps_existing_colon_and_slash_rules(self):
        self.assertEqual(od.safe_filename('Foo: Bar/Baz', 'id'), 'Foo - Bar-Baz.epub')

    def test_removes_windows_reserved_characters(self):
        name = od.safe_filename('Foo <v2> | Q? *"x"* back\\slash', 'id')
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, name)
        self.assertEqual(name, "Foo v2 Q 'x' back-slash.epub")

    def test_removes_control_characters(self):
        self.assertEqual(od.safe_filename('A\tB\x00C', 'id'), 'A B C.epub')

    def test_strips_trailing_dots_and_spaces(self):
        self.assertEqual(od.safe_filename('Wait for it... ', 'id'), 'Wait for it.epub')

    def test_reserved_device_names(self):
        self.assertEqual(od.safe_filename('CON', 'id'), 'CON_.epub')
        self.assertEqual(od.safe_filename('lpt1', 'id'), 'lpt1_.epub')

    def test_limits_length(self):
        name = od.safe_filename('x' * 500, 'id')
        self.assertLessEqual(len(name), od.MAX_FILENAME_LENGTH)
        self.assertTrue(name.endswith('.epub'))

    def test_limits_length_in_bytes(self):
        name = od.safe_filename('\u00e9' * 500, 'id')
        self.assertLessEqual(len(name.encode('utf-8')), od.MAX_FILENAME_LENGTH)
        self.assertTrue(name.endswith('.epub'))

    def test_falls_back_to_book_id(self):
        self.assertEqual(od.safe_filename('???', '978123'), '978123.epub')


class RetryTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(od.time, 'sleep')
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def urlopen(self, *outcomes):
        def side_effect(*args, **kwargs):
            outcome = outcomes_iter.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return FakeResponse(outcome)

        outcomes_iter = list(outcomes)
        return mock.patch.object(od.urllib.request, 'urlopen', side_effect=side_effect)

    def test_retries_transient_errors(self):
        errors = [http_error(429), http_error(403), http_error(503), urllib.error.URLError('down')]
        with self.urlopen(*errors, b'ok') as urlopen:
            self.assertEqual(od.make_getter(None)('https://example.com'), b'ok')
        self.assertEqual(urlopen.call_count, 5)

    def test_honours_retry_after(self):
        with self.urlopen(http_error(429, retry_after='7'), b'ok'):
            od.make_getter(None)('https://example.com')
        self.sleep.assert_called_once_with(7)

    def test_gives_up_after_max_retries(self):
        errors = [http_error(500)] * (od.MAX_RETRIES + 1)
        with self.urlopen(*errors), self.assertRaises(urllib.error.HTTPError):
            od.make_getter(None)('https://example.com')
        self.assertEqual(self.sleep.call_count, od.MAX_RETRIES)

    def test_does_not_retry_permanent_errors(self):
        with self.urlopen(http_error(404)) as urlopen, self.assertRaises(urllib.error.HTTPError):
            od.make_getter(None)('https://example.com')
        self.assertEqual(urlopen.call_count, 1)

    def test_check_auth_does_not_retry(self):
        with self.urlopen(http_error(403)) as urlopen:
            self.assertFalse(od.check_auth(od.make_getter('jwt')))
        self.assertEqual(urlopen.call_count, 1)

    def test_pool_size_is_bounded(self):
        with mock.patch.object(od, 'ThreadPoolExecutor', wraps=od.ThreadPoolExecutor) as pool:
            with zipfile.ZipFile(io.BytesIO(), 'w') as zfh:
                od.fetch_book('1', zfh, fake_book_getter())
        pool.assert_called_once_with(max_workers=od.MAX_WORKERS)


def fake_book_getter(fail_on=None):
    root = od.BASE_URL + '/api/v2/epubs/urn:orm:book:1/files/'
    listing = {'results': [
        {'url': 'https://x/opf', 'full_path': 'content.opf', 'media_type': 'application/oebps-package+xml'},
        {'url': 'https://x/ch1', 'full_path': 'ch1.html', 'media_type': 'text/html'},
    ]}
    pages = {root: json.dumps(listing).encode(), 'https://x/opf': b'<package/>', 'https://x/ch1': b'<p>hi</p>'}

    def get(url, **kwargs):
        if url == fail_on:
            raise http_error(403)
        return pages[url]

    return get


class WriteBookTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.filename = os.path.join(tmp.name, 'book.epub')

    def test_success_creates_final_file_only(self):
        od.write_book('1', self.filename, fake_book_getter())
        self.assertTrue(os.path.exists(self.filename))
        self.assertFalse(os.path.exists(self.filename + '.partial'))
        with zipfile.ZipFile(self.filename) as zfh:
            self.assertIn('EPUB/ch1.html', zfh.namelist())

    def test_failure_leaves_no_file(self):
        with self.assertRaises(urllib.error.HTTPError):
            od.write_book('1', self.filename, fake_book_getter(fail_on='https://x/ch1'))
        self.assertEqual(os.listdir(os.path.dirname(self.filename)), [])

    def test_failure_keeps_existing_file(self):
        with open(self.filename, 'wb') as fh:
            fh.write(b'previous')
        with self.assertRaises(urllib.error.HTTPError):
            od.write_book('1', self.filename, fake_book_getter(fail_on='https://x/ch1'))
        with open(self.filename, 'rb') as fh:
            self.assertEqual(fh.read(), b'previous')


if __name__ == '__main__':
    unittest.main()
