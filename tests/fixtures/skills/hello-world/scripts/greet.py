#!/usr/bin/env python3
"""Print the deterministic hello-world skill greeting."""

from __future__ import annotations

import argparse


def greeting(name: str) -> str:
    """Return a greeting for *name*."""
    return f"Hello, {name}! This greeting comes from the hello-world skill."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="World", help="name to greet")
    args = parser.parse_args()
    print(greeting(args.name))


if __name__ == "__main__":
    main()
