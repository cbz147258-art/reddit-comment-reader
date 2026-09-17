from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import praw

from .db import Database, reddit_timestamp, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrawlResult:
    run_id: int
    posts_found: int
    comments_found: int


class RedditCrawler:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        database: Database,
    ):
        self.database = database
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            check_for_async=False,
            read_only=True,
        )

    def crawl(
        self,
        keyword: str,
        subreddit: str | None = None,
        days: int = 7,
        post_limit: int = 100,
        comment_more_limit: int | None = None,
    ) -> CrawlResult:
        if days <= 0:
            raise ValueError("days must be greater than zero")
        if post_limit <= 0:
            raise ValueError("post_limit must be greater than zero")

        self.database.initialize()
        run_id = self.database.start_run(keyword, subreddit)
        posts_found = 0
        comments_found = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        time_filter = self._time_filter(days)

        try:
            search_scope = self.reddit.subreddit(subreddit or "all")
            logger.info(
                "Searching keyword=%r subreddit=%s days=%d limit=%d",
                keyword,
                subreddit or "all",
                days,
                post_limit,
            )

            for submission in search_scope.search(
                query=keyword,
                sort="new",
                time_filter=time_filter,
                limit=post_limit,
            ):
                created_at = datetime.fromtimestamp(
                    submission.created_utc, tz=timezone.utc
                )
                if created_at < cutoff or created_at > datetime.now(timezone.utc):
                    continue

                post = self._post_record(submission, keyword)
                self.database.upsert_post(post)
                self.database.record_post_keyword(submission.id, keyword)
                posts_found += 1

                count = self._crawl_comments(
                    submission,
                    comment_more_limit=comment_more_limit,
                )
                comments_found += count
                logger.info(
                    "Saved post=%s comments=%d title=%r",
                    submission.id,
                    count,
                    submission.title[:80],
                )

            self.database.finish_run(
                run_id,
                posts_found=posts_found,
                comments_found=comments_found,
            )
            return CrawlResult(run_id, posts_found, comments_found)
        except Exception as exc:
            self.database.finish_run(
                run_id,
                posts_found=posts_found,
                comments_found=comments_found,
                status="failed",
                error=repr(exc),
            )
            raise

    def _crawl_comments(
        self,
        submission: Any,
        comment_more_limit: int | None,
    ) -> int:
        submission.comments.replace_more(limit=comment_more_limit)
        count = 0
        for comment in submission.comments.list():
            if not getattr(comment, "id", None):
                continue

            author = getattr(comment.author, "name", None)
            distinguished = getattr(comment, "distinguished", None)
            if isinstance(distinguished, dict):
                distinguished = distinguished.get("by")

            self.database.upsert_comment(
                {
                    "id": comment.id,
                    "post_id": submission.id,
                    "parent_id": getattr(comment, "parent_id", None),
                    "author": author,
                    "body": getattr(comment, "body", None),
                    "permalink": self._absolute_permalink(
                        getattr(comment, "permalink", None)
                    ),
                    "created_at": reddit_timestamp(
                        getattr(comment, "created_utc", None)
                    ),
                    "edited": int(bool(getattr(comment, "edited", False))),
                    "distinguished": distinguished,
                    "stickied": int(bool(getattr(comment, "stickied", False))),
                    "is_submitter": int(bool(getattr(comment, "is_submitter", False))),
                    "score": getattr(comment, "score", None),
                    "depth": getattr(comment, "depth", None),
                    "fetched_at": utc_now(),
                }
            )
            count += 1
        return count

    @staticmethod
    def _post_record(submission: Any, keyword: str) -> dict[str, Any]:
        author = getattr(submission.author, "name", None)
        return {
            "id": submission.id,
            "name": submission.name,
            "keyword": keyword,
            "subreddit": submission.subreddit.display_name,
            "author": author,
            "title": submission.title,
            "selftext": submission.selftext,
            "url": submission.url,
            "permalink": RedditCrawler._absolute_permalink(submission.permalink),
            "created_at": reddit_timestamp(submission.created_utc),
            "score": submission.score,
            "upvote_ratio": getattr(submission, "upvote_ratio", None),
            "num_comments": submission.num_comments,
            "over_18": int(bool(submission.over_18)),
            "spoiler": int(bool(submission.spoiler)),
            "locked": int(bool(submission.locked)),
            "stickied": int(bool(submission.stickied)),
            "is_self": int(bool(submission.is_self)),
            "fetched_at": utc_now(),
        }

    @staticmethod
    def _time_filter(days: int) -> str:
        if days <= 7:
            return "week"
        if days <= 31:
            return "month"
        if days <= 365:
            return "year"
        return "all"

    @staticmethod
    def _absolute_permalink(permalink: str | None) -> str | None:
        if not permalink:
            return None
        if permalink.startswith("http://") or permalink.startswith("https://"):
            return permalink
        return f"https://www.reddit.com{permalink}"

