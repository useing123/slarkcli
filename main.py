import argparse
import asyncio
from pathlib import Path

from agents.loop import start


def parse_args() -> Path:
    parser = argparse.ArgumentParser(prog="slark")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("."),
        help="Working directory (default: current directory)",
    )
    args = parser.parse_args()
    return args.dir.resolve()


if __name__ == "__main__":
    working_dir = parse_args()
    asyncio.run(start(working_dir))
