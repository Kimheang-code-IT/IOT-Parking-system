"""Bump when parking data changes so the dashboard can poll and auto-refresh."""

import time

_revision: float = time.time()


def bump_parking_revision() -> float:
    global _revision
    _revision = time.time()
    return _revision


def get_parking_revision() -> float:
    return _revision
