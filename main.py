import argparse
import asyncio
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(prog="slark")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("."),
        help="Working directory (default: current directory)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    working_dir = args.dir.resolve()

    from agents.loop import start

    asyncio.run(start(working_dir))
