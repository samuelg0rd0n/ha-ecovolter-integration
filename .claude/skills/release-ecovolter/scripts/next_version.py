#!/usr/bin/env python3
"""Compute the next semantic version for this repo's manifest.json.

Usage:
  next_version.py <current> major|minor|patch [--pre LABEL]
  next_version.py <current> --finalize

Examples:
  next_version.py 1.0.0 minor            -> 1.1.0
  next_version.py 1.0.0 minor --pre beta -> 1.1.0-beta.0
  next_version.py 1.1.0-beta.0 --pre beta -> 1.1.0-beta.1   (same base, bumps prerelease counter)
  next_version.py 1.1.0-beta.1 --finalize -> 1.1.0          (drop the prerelease suffix)
"""

import argparse
import re
import sys

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z]+)\.(\d+))?$")


def parse(version):
    m = VERSION_RE.match(version.strip())
    if not m:
        sys.exit(f"error: '{version}' is not a valid semver (expected X.Y.Z or X.Y.Z-label.N)")
    major, minor, patch, pre_label, pre_num = m.groups()
    return int(major), int(minor), int(patch), pre_label, (int(pre_num) if pre_num else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("current", help="current version from manifest.json, e.g. 1.0.0")
    parser.add_argument("bump", nargs="?", choices=["major", "minor", "patch"], help="version part to bump")
    parser.add_argument("--pre", metavar="LABEL", help="make this a prerelease, e.g. --pre beta")
    parser.add_argument("--finalize", action="store_true", help="drop the prerelease suffix from `current` as-is")
    args = parser.parse_args()

    major, minor, patch, pre_label, pre_num = parse(args.current)

    if args.finalize:
        if pre_label is None:
            sys.exit(f"error: '{args.current}' has no prerelease suffix to finalize")
        print(f"{major}.{minor}.{patch}")
        return

    if args.pre:
        if args.bump is None and pre_label == args.pre:
            # Same base version, already a prerelease of this label -> bump the counter.
            print(f"{major}.{minor}.{patch}-{args.pre}.{pre_num + 1}")
            return
        if args.bump is None:
            sys.exit("error: pass a bump type (major/minor/patch) to start a new prerelease series")
        major, minor, patch = _bump(major, minor, patch, args.bump)
        print(f"{major}.{minor}.{patch}-{args.pre}.0")
        return

    if args.bump is None:
        sys.exit("error: pass a bump type (major/minor/patch), --pre LABEL, or --finalize")

    major, minor, patch = _bump(major, minor, patch, args.bump)
    print(f"{major}.{minor}.{patch}")


def _bump(major, minor, patch, kind):
    if kind == "major":
        return major + 1, 0, 0
    if kind == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


if __name__ == "__main__":
    main()
