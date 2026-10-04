import argparse

from appdb import AppDb
from cache import Cache
from pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Find new studio songs on YouTube Music and rank them against your taste.")
    parser.add_argument("query")
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    results = []
    for event in run(args.query, args.count, Cache(), AppDb()):
        if event["type"] == "analyzing":
            print(f"[{event['index']}/{args.count}] {event['artist']} - {event['title']}", flush=True)
        elif event["type"] == "scored":
            results.append(event)

    recommended = [r for r in results if r["recommended"]]

    print(f"\nRecommended ({len(recommended)} of {len(results)} new tracks):")
    for r in recommended:
        print(f"  {r['artist']} - {r['title']}  {r['url']}")


if __name__ == "__main__":
    main()
