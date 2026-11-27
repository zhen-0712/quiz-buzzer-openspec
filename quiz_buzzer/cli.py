"""Command-line options for starting the local Flask server."""

import argparse


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the classroom quiz buzzer")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="interface to bind (default: 0.0.0.0 for local network access)",
    )
    parser.add_argument("--port", type=int, default=5000, help="HTTP port (default: 5000)")
    return parser
