"""Durable operation journal for trusted agent workers on one host."""
from contextlib import closing
import hashlib
import json
import sqlite3


class Conflict(ValueError):
    """An operation key was reused with a different tool or arguments."""


class Uncertain(RuntimeError):
    """A previous attempt may have reached the provider."""


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Journal:
    def __init__(self, path):
        self.path = path
        with closing(self.connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS operations (
                key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                result TEXT, completed INTEGER NOT NULL DEFAULT 0
            )""")
            db.commit()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def execute(self, key, tool, arguments, send):
        """Persist intent before dispatch; replay a known result or stop."""
        if not isinstance(key, str) or not key or len(key) > 256:
            raise ValueError("A stable operation key of 1–256 characters is required")
        fingerprint = hashlib.sha256(encode([tool, arguments]).encode()).hexdigest()
        with closing(self.connect()) as db, db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO operations(key,fingerprint) VALUES (?,?)",
                (key, fingerprint),
            ).rowcount
            if not inserted:
                old_fingerprint, result, completed = db.execute(
                    "SELECT fingerprint,result,completed FROM operations WHERE key=?",
                    (key,),
                ).fetchone()
                if old_fingerprint != fingerprint:
                    raise Conflict(key)
                if not completed:
                    raise Uncertain(key)
                return json.loads(result)

        result = encode(send(key, json.loads(encode(arguments))))
        with closing(self.connect()) as db, db:
            db.execute("UPDATE operations SET completed=1,result=? WHERE key=?", (result, key))
        return json.loads(result)

    def status(self, key):
        with closing(self.connect()) as db:
            row = db.execute("SELECT completed FROM operations WHERE key=?", (key,)).fetchone()
        if row is None:
            return "unknown"
        return "completed" if row[0] else "uncertain"
