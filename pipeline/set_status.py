"""Mark a video as rejected, posted (published by hand from the phone) or back to review."""
import argparse

from .common import update_item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--slot", required=True)
    ap.add_argument("--status", required=True, choices=["rejected", "review", "published"])
    a = ap.parse_args()
    kind = "weekly" if a.id.startswith("week-") else "daily"
    extra = {"posted_by_hand": True} if a.status == "published" else {}
    update_item(a.id, a.slot, kind=kind, status=a.status, error="", **extra)


if __name__ == "__main__":
    main()
