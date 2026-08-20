import argparse
import json

from app.services.trash_lifecycle_service import TrashPurgeRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge eligible Trash entries")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    result = TrashPurgeRunner(batch_limit=args.limit).run()
    print(json.dumps(result, sort_keys=True))
    if int(result["failed"]) > 0:
        raise RuntimeError("Trash purge completed with runner failures")


if __name__ == "__main__":
    main()
