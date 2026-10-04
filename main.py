import argparse

from appdb import AppDb
from cache import Cache
from pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Find new studio songs on YouTube Music and rank them against your taste.")
    parser.add_argument("query", nargs="?", help="Search query; omit to generate queries from your taste")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument(
        "--exploration", type=int, default=50, choices=range(101), metavar="0-100", help="0 = familiar, 100 = adventurous"
    )
    args = parser.parse_args()

    results = []
    for event in run(args.query, args.count, args.exploration, Cache(), AppDb()):
        if event["type"] == "queries":
            for q in event["queries"]:
                print(f"Query ({q['tier']}): {q['query']}", flush=True)
        elif event["type"] == "analyzing":
            print(f"[{event['index']}/{args.count}] {event['artist']} - {event['title']}", flush=True)
        elif event["type"] == "scored":
            results.append(event)

    recommended = [r for r in results if r["recommended"]]

    print(f"\nRecommended ({len(recommended)} of {len(results)} new songs):")
    for r in recommended:
        print(f"  {r['artist']} - {r['title']}  {r['url']}")


if __name__ == "__main__":
    main()
