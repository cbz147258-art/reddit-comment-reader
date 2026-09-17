from __future__ import annotations

import argparse
import logging

from reddit_crawler.config import Settings
from reddit_crawler.crawler import RedditCrawler
from reddit_crawler.db import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Reddit posts and comments for a keyword."
    )
    parser.add_argument("keyword", help="Keyword or Reddit search query")
    parser.add_argument(
        "--subreddit",
        help="Restrict search to one subreddit, for example python or technology",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Exact lookback window in days; default: 7",
    )
    parser.add_argument(
        "--post-limit",
        type=int,
        default=100,
        help="Maximum candidate posts returned by Reddit search; default: 100",
    )
    parser.add_argument(
        "--comment-more-limit",
        type=int,
        default=None,
        help=(
            "Number of MoreComments nodes to expand per post. "
            "Default: all available; use 0 for top-level comments only."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    settings = Settings.from_env()
    crawler = RedditCrawler(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        user_agent=settings.user_agent,
        database=Database(settings.database_path),
    )
    result = crawler.crawl(
        keyword=args.keyword,
        subreddit=args.subreddit,
        days=args.days,
        post_limit=args.post_limit,
        comment_more_limit=args.comment_more_limit,
    )
    print(
        f"crawl_run={result.run_id} posts={result.posts_found} "
        f"comments={result.comments_found} database={settings.database_path}"
    )


if __name__ == "__main__":
    main()

