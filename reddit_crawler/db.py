from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    keyword TEXT,
    subreddit TEXT NOT NULL,
    author TEXT,
    title TEXT NOT NULL,
    selftext TEXT,
    url TEXT,
    permalink TEXT NOT NULL,
    created_at TEXT NOT NULL,
    score INTEGER,
    upvote_ratio REAL,
    num_comments INTEGER,
    over_18 INTEGER NOT NULL DEFAULT 0,
    spoiler INTEGER NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0,
    stickied INTEGER NOT NULL DEFAULT 0,
    is_self INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    parent_id TEXT,
    author TEXT,
    body TEXT,
    permalink TEXT,
    created_at TEXT NOT NULL,
    edited INTEGER NOT NULL DEFAULT 0,
    distinguished TEXT,
    stickied INTEGER NOT NULL DEFAULT 0,
    is_submitter INTEGER NOT NULL DEFAULT 0,
    score INTEGER,
    depth INTEGER,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments(created_at);

CREATE TABLE IF NOT EXISTS post_keywords (
    post_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (post_id, keyword),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    subreddit TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    posts_found INTEGER NOT NULL DEFAULT 0,
    comments_found INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error TEXT
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reddit_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    def start_run(self, keyword: str, subreddit: str | None) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO crawl_runs (keyword, subreddit, started_at, status)
                VALUES (?, ?, ?, 'running')
                """,
                (keyword, subreddit, utc_now()),
            )
            return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        posts_found: int,
        comments_found: int,
        status: str = "completed",
        error: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE crawl_runs
                SET finished_at = ?, posts_found = ?, comments_found = ?,
                    status = ?, error = ?
                WHERE id = ?
                """,
                (utc_now(), posts_found, comments_found, status, error, run_id),
            )

    def upsert_post(self, post: dict[str, Any]) -> None:
        columns = [
            "id",
            "name",
            "keyword",
            "subreddit",
            "author",
            "title",
            "selftext",
            "url",
            "permalink",
            "created_at",
            "score",
            "upvote_ratio",
            "num_comments",
            "over_18",
            "spoiler",
            "locked",
            "stickied",
            "is_self",
            "fetched_at",
        ]
        values = [post[column] for column in columns]
        update_columns = ", ".join(
            f"{column}=excluded.{column}" for column in columns if column != "id"
        )
        placeholders = ", ".join("?" for _ in columns)

        with self.connection() as connection:
            connection.execute(
                f"""
                INSERT INTO posts ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {update_columns}
                """,
                values,
            )

    def record_post_keyword(self, post_id: str, keyword: str) -> None:
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO post_keywords (post_id, keyword, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(post_id, keyword) DO UPDATE SET last_seen_at=excluded.last_seen_at
                """,
                (post_id, keyword, now, now),
            )

    def upsert_comment(self, comment: dict[str, Any]) -> None:
        columns = [
            "id",
            "post_id",
            "parent_id",
            "author",
            "body",
            "permalink",
            "created_at",
            "edited",
            "distinguished",
            "stickied",
            "is_submitter",
            "score",
            "depth",
            "fetched_at",
        ]
        values = [comment[column] for column in columns]
        update_columns = ", ".join(
            f"{column}=excluded.{column}" for column in columns if column != "id"
        )
        placeholders = ", ".join("?" for _ in columns)

        with self.connection() as connection:
            connection.execute(
                f"""
                INSERT INTO comments ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {update_columns}
                """,
                values,
            )

