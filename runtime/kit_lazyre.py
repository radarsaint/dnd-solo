"""Compile a regular expression the first time it is used.

Importing Kit used to compile patterns before a command ran. A LazyPattern
stands in for a compiled pattern: search, match, sub, and the other methods
compile on first use and then call the real pattern. It is not a re.Pattern,
so do not pass one to re.search or re.sub. Call the method on it instead.
"""
from __future__ import annotations

import re


class LazyPattern:
    def __init__(self, pattern: str, flags: int = 0) -> None:
        self.pattern = pattern
        self.flags = flags
        self._compiled: re.Pattern[str] | None = None

    def _re(self) -> re.Pattern[str]:
        if self._compiled is None:
            self._compiled = re.compile(self.pattern, self.flags)
        return self._compiled

    def __getattr__(self, name: str):
        return getattr(self._re(), name)


def compile(pattern: str, flags: int = 0) -> LazyPattern:
    return LazyPattern(pattern, flags)
