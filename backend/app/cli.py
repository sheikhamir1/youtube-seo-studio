"""Small maintenance CLI (optional - nothing core depends on it).

Usage::

    python -m app.cli seed       # ensure the seeded prompt templates exist
    python -m app.cli status     # print system + quota status
    python -m app.cli cleanup    # abort stale uploads, delete leftover temp files
    python -m app.cli orphans    # list job directories with no database row
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_scope
from app.services.cleanup import CleanupService
from app.services.system_service import SystemService
from app.templates.seed_data import seed_all


async def _seed() -> int:
    async with session_scope() as session:
        result = await seed_all(session)
    print(json.dumps(result, indent=2))
    return 0


async def _status() -> int:
    async with session_scope() as session:
        service = SystemService(session)
        status = await service.status()
        quota = await service.quota()
        storage = await service.storage_usage()
    print(json.dumps({"status": status, "quota": quota, "storage": storage}, indent=2, default=str))
    return 0


async def _cleanup() -> int:
    service = CleanupService()
    result = await service.cleanup_stale_uploads()
    orphans = await service.find_orphan_directories()
    print(json.dumps({**result, "orphan_directories": orphans}, indent=2, default=str))
    return 0


async def _orphans() -> int:
    orphans = await CleanupService().find_orphan_directories()
    print(json.dumps({"orphan_directories": orphans}, indent=2))
    return 0


COMMANDS = {
    "seed": _seed,
    "status": _status,
    "cleanup": _cleanup,
    "orphans": _orphans,
}


async def _main(command: str) -> int:
    configure_logging(settings.log_level)
    try:
        return await COMMANDS[command]()
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()
    return asyncio.run(_main(args.command))


if __name__ == "__main__":
    sys.exit(main())
