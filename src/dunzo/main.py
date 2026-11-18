"""Command-line entry point: `uv run dunzo [--reload]`."""

import argparse

import uvicorn

from dunzo.config import PROJECT_ROOT, get_settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dunzo", description="Spaced-repetition flashcards")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="restart the server automatically when source files change (development)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    uvicorn.run(
        "dunzo.app:app",
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        reload_dirs=[str(PROJECT_ROOT / "src")] if args.reload else None,
    )


if __name__ == "__main__":
    main()
