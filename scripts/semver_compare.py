# SPDX-License-Identifier: Apache-2.0
"""Semver 2.0.0 comparison utility.

Standalone version of the inline comparator used in
reusable_release_preflight.yml. Implements section 11
pre-release precedence rules.

Usage:
    python3 scripts/semver_compare.py <version_a> <version_b>

Exit codes:
    0: version_a < version_b (a has lower precedence)
    1: version_a >= version_b (a has equal or higher precedence)
"""

import sys
from typing import Optional, Union


def parse_semver(
    v: str,
) -> tuple[int, int, int, Optional[list[Union[int, str]]]]:
    """Parse semver string into (major, minor, patch, pre_ids).

    Strips leading 'v' prefix if present.
    """
    v = v.lstrip("v")
    if "-" in v:
        core, pre = v.split("-", 1)
    else:
        core, pre = v, None
    major, minor, patch = (int(x) for x in core.split("."))
    if pre is None:
        return (major, minor, patch, None)
    ids: list[Union[int, str]] = []
    for ident in pre.split("."):
        ids.append(int(ident) if ident.isdigit() else ident)
    return (major, minor, patch, ids)


def cmp_semver(
    a: tuple[int, int, int, Optional[list[Union[int, str]]]],
    b: tuple[int, int, int, Optional[list[Union[int, str]]]],
) -> int:
    """Compare two semver tuples per semver 2.0.0 section 11.

    Returns:
        -1 if a < b, 0 if a == b, 1 if a > b
    """
    for i in range(3):
        if a[i] != b[i]:
            return -1 if a[i] < b[i] else 1
    # Pre-release precedence
    if a[3] is None and b[3] is None:
        return 0
    if a[3] is None:
        return 1  # release > pre-release
    if b[3] is None:
        return -1  # pre-release < release
    for x, y in zip(a[3], b[3]):
        if type(x) is type(y):
            if x != y:
                return -1 if x < y else 1
        else:
            # Numeric identifiers have lower precedence
            # than alphanumeric
            return -1 if isinstance(x, int) else 1
    if len(a[3]) != len(b[3]):
        return -1 if len(a[3]) < len(b[3]) else 1
    return 0


def main() -> None:
    """Compare two semver versions from CLI args."""
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <version_a> <version_b>",
            file=sys.stderr,
        )
        sys.exit(2)
    a = parse_semver(sys.argv[1])
    b = parse_semver(sys.argv[2])
    result = cmp_semver(a, b)
    if result < 0:
        print(f"{sys.argv[1]} < {sys.argv[2]}")
        sys.exit(0)
    elif result == 0:
        print(f"{sys.argv[1]} == {sys.argv[2]}")
        sys.exit(1)
    else:
        print(f"{sys.argv[1]} > {sys.argv[2]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
