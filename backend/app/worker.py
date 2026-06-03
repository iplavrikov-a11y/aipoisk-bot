from __future__ import annotations

import asyncio

from .jobs import worker_loop


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
