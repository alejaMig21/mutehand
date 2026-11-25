"""Where the person's data lives by default."""

import os
from pathlib import Path


def _data_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", ".")) / "workflow-factory"


def default_user_db() -> Path:
    """The user database: WORKFLOW_FACTORY_USER_DB, else %LOCALAPPDATA%/workflow-factory/user.db."""
    return Path(os.environ.get("WORKFLOW_FACTORY_USER_DB", _data_root() / "user.db"))


def default_report_dir() -> Path:
    """Where workday reports go: WORKFLOW_FACTORY_REPORT_DIR, else %LOCALAPPDATA%/workflow-factory/reports."""
    return Path(os.environ.get("WORKFLOW_FACTORY_REPORT_DIR", _data_root() / "reports"))
