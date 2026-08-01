#!/usr/bin/env python3
"""
ablesign_setup.py — one-time AbleSign setup helper.

1) List your screens (so we can confirm the TV1/TV3/TV5 -> screen mapping,
   and check whether every class uses the same 3 screens or different ones):

     python3 ablesign_setup.py --list-screens

2) Create an AbleSign folder tree that mirrors your Drive structure
   (e.g. "Claude" > "8. August" containing one subfolder per class),
   reading class names from a plain text file, one per line
   (classes.txt provided):

     python3 ablesign_setup.py --create-tree "Claude/8. August" --classes-file classes.txt

Safe to re-run: it looks for an existing folder with the same name/parent
before creating a new one, so running it twice won't create duplicates.
"""

import argparse
import sys

import requests

ABLESIGN_API_KEY = "ak_1c9d0575130dabc8d361567017896164eae8c52c"
ABLESIGN_BASE = "https://api.ablesign.tv/api/v1"


def headers():
    return {"Authorization": f"Bearer {ABLESIGN_API_KEY}"}


def list_screens():
    r = requests.get(f"{ABLESIGN_BASE}/screens", headers=headers(), params={"limit": 200}, timeout=30)
    r.raise_for_status()
    data = r.json()["data"]
    if not data:
        print("No screens found.")
        return
    print(f"{'ID':>6}  Title")
    for s in data:
        print(f"{s['id']:>6}  {s['title']}")


def list_child_folders(parent_id):
    r = requests.get(
        f"{ABLESIGN_BASE}/folders",
        headers=headers(),
        params={"limit": 200},
        timeout=30,
    )
    r.raise_for_status()
    return [f for f in r.json()["data"] if f.get("parentFolderId") == parent_id]


def delete_folder(folder_id):
    # NOTE: this endpoint is not confirmed against the real AbleSign API docs.
    # Test it on one throwaway folder before trusting it against the real tree.
    r = requests.delete(f"{ABLESIGN_BASE}/folders/{folder_id}", headers=headers(), timeout=30)
    r.raise_for_status()


def reset_children(parent_id):
    children = list_child_folders(parent_id)
    if not children:
        print("No existing child folders to remove.")
        return
    print(f"About to delete {len(children)} existing folder(s):")
    for f in children:
        print(f"  {f['title']} (id {f['id']})")
    for f in children:
        delete_folder(f["id"])
        print(f"  deleted {f['title']} (id {f['id']})")


def get_or_create_folder(title, parent_id=None):
    r = requests.get(
        f"{ABLESIGN_BASE}/folders",
        headers=headers(),
        params={"title": title, "limit": 200},
        timeout=30,
    )
    r.raise_for_status()
    for f in r.json()["data"]:
        same_parent = f.get("parentFolderId") == parent_id
        if f["title"].strip().lower() == title.strip().lower() and same_parent:
            return f["id"], False
    r2 = requests.post(
        f"{ABLESIGN_BASE}/folders",
        headers=headers(),
        json={"title": title, "parentFolderId": parent_id},
        timeout=30,
    )
    r2.raise_for_status()
    return r2.json()["data"]["id"], True


def create_tree(root_path, classes, reset=False):
    """root_path is a '/'-separated chain of folders, e.g. 'Claude/8. August'.
    Each segment is created (or reused) under the previous one."""
    parent_id = None
    for segment in root_path.split("/"):
        segment = segment.strip()
        parent_id, created = get_or_create_folder(segment, parent_id)
        print(f"Folder '{segment}' -> id {parent_id} {'(created)' if created else '(already existed)'}")

    if reset:
        print(f"\nResetting existing class folders under '{root_path}'...")
        reset_children(parent_id)
        print()

    for c in classes:
        cid, created = get_or_create_folder(c, parent_id)
        print(f"  {c} -> id {cid} {'(created)' if created else '(already existed)'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list-screens", action="store_true", help="Print all AbleSign screens (id + title)")
    parser.add_argument(
        "--create-tree", metavar="ROOT_PATH",
        help='"/"-separated folder chain, e.g. "Claude/8. August"',
    )
    parser.add_argument("--classes-file", help="Text file, one class name per line")
    parser.add_argument(
        "--reset-tree", action="store_true",
        help="Delete every existing child folder under ROOT_PATH before recreating from --classes-file. "
             "UNVERIFIED: the delete endpoint this calls has not been confirmed against AbleSign's docs. "
             "Test on a throwaway folder first. Requires --yes-really-delete.",
    )
    parser.add_argument(
        "--yes-really-delete", action="store_true",
        help="Required alongside --reset-tree, confirms you mean it",
    )
    args = parser.parse_args()

    if args.list_screens:
        list_screens()
        return

    if args.create_tree:
        if not args.classes_file:
            sys.exit("--classes-file is required with --create-tree")
        if args.reset_tree and not args.yes_really_delete:
            sys.exit("--reset-tree also requires --yes-really-delete, refusing to guess that you meant it")
        with open(args.classes_file) as f:
            classes = [line.strip() for line in f if line.strip()]
        create_tree(args.create_tree, classes, reset=args.reset_tree)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
