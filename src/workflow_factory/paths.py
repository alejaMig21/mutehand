"""Where the person's data lives by default."""

import os
from pathlib import Path


def default_user_db() -> Path:
    """The user database: WORKFLOW_FACTORY_USER_DB, else %LOCALAPPDATA%/workflow-factory/user.db."""
    default = Path(os.environ.get("LOCALAPPDATA", ".")) / "workflow-factory" / "user.db"
    return Path(os.environ.get("WORKFLOW_FACTORY_USER_DB", default))
