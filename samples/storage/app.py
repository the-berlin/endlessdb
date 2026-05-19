import argparse
import json
import sys
from pathlib import Path
from typing import Any

SAMPLES = Path(__file__).resolve().parents[1]
SRC = SAMPLES.parent / "src"
for path in [SAMPLES, SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from common import make_database
from storage import StorageService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EndlessDB storage sample app")
    parser.add_argument("--collection", help="Override the collection from samples/storage/config.yml")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("demo", help="Create, query, export, and clean up sample tasks")

    add_parser = subparsers.add_parser("add", help="Create or patch a storage item")
    add_parser.add_argument("key")
    add_parser.add_argument("title")
    add_parser.add_argument("--notes", default="")
    add_parser.add_argument("--tag", action="append", dest="tags")

    complete_parser = subparsers.add_parser("complete", help="Mark an item complete")
    complete_parser.add_argument("key")

    list_parser = subparsers.add_parser("list", help="List storage items")
    list_parser.add_argument("--state", choices=["all", "open", "done"], default="all")

    subparsers.add_parser("export", help="Print all items as JSON")
    subparsers.add_parser("reset", help="Drop the sample collection")
    return parser


def print_items(items: list[Any]) -> None:
    if not items:
        print("(no items)")
        return

    for item in items:
        state = "done" if item.done else "open"
        print(f"{item.id}: [{state}] {item.title}")


def run_demo(service: StorageService) -> None:
    service.reset()
    service.put("design", "Sketch storage app flow", "Use EndlessDB dynamic documents")
    service.put("docs", "Document storage sample", tags=["docs", "sample"])
    service.complete("design")

    print("collection:", service.collection_name)
    print("open items:")
    print_items(service.list_items(done=False))
    print("done items:")
    print_items(service.list_items(done=True))
    print("export:")
    print(json.dumps(service.export(), indent=2, default=str))

    service.reset()


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    edb = make_database()
    service = StorageService(edb, collection_name=args.collection)

    if args.command in (None, "demo"):
        run_demo(service)
        return

    if args.command == "add":
        service.put(args.key, args.title, args.notes, args.tags)
        print(f"saved {args.key} in {service.collection_name}")
        return

    if args.command == "complete":
        try:
            service.complete(args.key)
        except KeyError as exc:
            parser.exit(1, f"{exc.args[0]}\n")
        print(f"completed {args.key}")
        return

    if args.command == "list":
        states = {"all": None, "open": False, "done": True}
        print_items(service.list_items(done=states[args.state]))
        return

    if args.command == "export":
        print(json.dumps(service.export(), indent=2, default=str))
        return

    if args.command == "reset":
        service.reset()
        print(f"reset {service.collection_name}")
        return


if __name__ == "__main__":
    main()
