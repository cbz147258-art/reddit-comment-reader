from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    user_agent: str
    database_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        required = {
            "REDDIT_CLIENT_ID": os.getenv("REDDIT_CLIENT_ID"),
            "REDDIT_CLIENT_SECRET": os.getenv("REDDIT_CLIENT_SECRET"),
            "REDDIT_USER_AGENT": os.getenv("REDDIT_USER_AGENT"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing environment variables: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill them in."
            )

        database_path = Path(os.getenv("DATABASE_PATH", "data/reddit.db"))
        database_path.parent.mkdir(parents=True, exist_ok=True)

        return cls(
            client_id=required["REDDIT_CLIENT_ID"],
            client_secret=required["REDDIT_CLIENT_SECRET"],
            user_agent=required["REDDIT_USER_AGENT"],
            database_path=database_path,
        )

