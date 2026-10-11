"""Environment-derived settings. Secrets are read here and never logged or returned."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

FIXTURE_EMPLOYEES = ("emp_asha", "emp_ben", "emp_casey")


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str
    mode: str
    db_demo: str
    db_eval: str
    org_id: str
    compiler: str
    port: int

    @property
    def atlas_configured(self) -> bool:
        return self.mongodb_uri.startswith(("mongodb+srv://", "mongodb://"))

    def db_name(self, mode: str) -> str:
        if mode == "demo":
            return self.db_demo
        if mode == "eval":
            return self.db_eval
        raise ValueError("live mode is disabled for this build")


def settings() -> Settings:
    mode = os.getenv("MARCH_MODE", "demo")
    if mode not in {"demo", "eval"}:
        raise ValueError("MARCH_MODE must be demo or eval; live is not authorized")
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI", ""),
        mode=mode,
        db_demo=os.getenv("MARCH_DB_DEMO", "march_demo"),
        db_eval=os.getenv("MARCH_DB_EVAL", "march_eval"),
        org_id=os.getenv("MARCH_ORG_ID", "demo_office"),
        compiler=os.getenv("MARCH_COMPILER", "live"),
        port=int(os.getenv("PORT", "8780")),
    )
