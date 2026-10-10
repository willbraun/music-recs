import argparse

from appdb import AppDb
from pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Find new studio songs on YouTube Music and rank them against your taste.")
    parser.add_argument("query", nargs="?", help="Search query; omit to generate queries from your taste")
    parser.add_argument("--count", type=int, default=3, help="Number of recommended songs to return")
    parser.add_argument(
        "--exploration", type=int, default=50, choices=range(101), metavar="0-100", help="0 = familiar, 100 = adventurous"
    )
    args = parser.parse_args()

    appdb = AppDb()
    if appdb.get_current_taste() is None:
        print("No taste set. Open the app to set one.")
        return

    results = []
    analyzed = 0
    for event in run(args.query, args.count, args.exploration, appdb):
        if event["type"] == "queries":
            for q in event["queries"]:
                print(f"Query ({q['tier']}): {q['query']}", flush=True)
        elif event["type"] == "downloading_model":
            print(f"Downloading model {event['model']}...", flush=True)
        elif event["type"] == "seeding":
            print(f"Learning songs by {event['artist']}...", flush=True)
        elif event["type"] == "fetching":
            print("Fetching songs...", flush=True)
        elif event["type"] == "analyzing":
            print(
                f"Analyzed {event['index']} songs; {event['recommended_count']}/{args.count} recommended: "
                f"{event['artist']} - {event['title']}",
                flush=True,
            )
        elif event["type"] == "scored":
            results.append(event)
        elif event["type"] == "done":
            analyzed = event["analyzed"]

    recommended = [r for r in results if r["recommended"]]

    print(f"\nRecommended ({len(recommended)} of {args.count} requested; analyzed {analyzed} songs):")
    for r in recommended:
        print(f"  {r['artist']} - {r['title']}  {r['url']}")


if __name__ == "__main__":
    main()
