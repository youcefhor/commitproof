from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from guard import Conflict, Journal, Uncertain


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.db"
        self.journal = Journal(self.path)

    def test_success_replays_across_instances_and_rejects_changed_arguments(self):
        def send(key, arguments):
            return {"refund": 12}
        self.assertEqual(self.journal.execute("r", "refund", {"amount": 12}, send), {"refund": 12})
        self.assertEqual(Journal(self.path).execute(
            "r", "refund", {"amount": 12}, lambda *_: self.fail("redispatched")
        ), {"refund": 12})
        with self.assertRaises(Conflict):
            self.journal.execute("r", "refund", {"amount": 13}, send)

    def test_concurrent_attempt_cannot_dispatch_twice(self):
        entered, release = threading.Event(), threading.Event()
        def send(*_):
            entered.set()
            if not release.wait(5):
                raise TimeoutError
            return "ok"
        with ThreadPoolExecutor() as pool:
            first = pool.submit(self.journal.execute, "r", "refund", {}, send)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(Uncertain):
                    Journal(self.path).execute("r", "refund", {}, lambda *_: self.fail("redispatched"))
            finally:
                release.set()
            self.assertEqual(first.result(), "ok")

    def test_crash_after_independent_commit(self):
        code = """
import os, sqlite3, sys
from guard import Journal
def send(key, args):
    with sqlite3.connect(sys.argv[2]) as db:
        db.execute('CREATE TABLE IF NOT EXISTS refunds (amount INTEGER)')
        db.execute('INSERT INTO refunds VALUES (12)')
    os._exit(73)
Journal(sys.argv[1]).execute('r','refund',{'amount':12},send)
"""
        provider = self.path.with_name("provider.db")
        result = subprocess.run([sys.executable, "-c", code, str(self.path), str(provider)], timeout=10)
        self.assertEqual(result.returncode, 73)
        restored = Journal(self.path)
        self.assertEqual(restored.status("r"), "uncertain")
        with self.assertRaises(Uncertain):
            restored.execute("r", "refund", {"amount": 12}, lambda *_: self.fail("redispatched"))
        with sqlite3.connect(provider) as db:
            self.assertEqual(db.execute("SELECT amount FROM refunds").fetchall(), [(12,)])


if __name__ == "__main__":
    unittest.main()
