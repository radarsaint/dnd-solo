"""Tiny lazy helpers: a module imported, or a pattern compiled, on first use, so a command that
never touches combat, chargen, or a module's phrase tables does not pay for them at startup.
Local stand-in: swap regex() for kit_lazyre when that lands (refactor stack #151-156)."""
import importlib
import re


class _Module:
    __slots__ = ('_name', '_package', '_mod')

    def __init__(self, name, package):
        object.__setattr__(self, '_name', name)
        object.__setattr__(self, '_package', package)
        object.__setattr__(self, '_mod', None)

    def __getattr__(self, attr):  # never caches attributes: patches on the module are seen
        mod = object.__getattribute__(self, '_mod')
        if mod is None:
            mod = importlib.import_module(object.__getattribute__(self, '_name'),
                                          object.__getattribute__(self, '_package'))
            object.__setattr__(self, '_mod', mod)
        return getattr(mod, attr)


def module(name, package=None):
    """``kit_combat = module('.kit_combat', __package__)``: imported at the first attribute read."""
    return _Module(name, package)


class _Pattern:
    __slots__ = ('_args', '_re')

    def __init__(self, pattern, flags):
        self._args, self._re = (pattern, flags), None

    def _compiled(self):
        if self._re is None:
            self._re = re.compile(*self._args)
        return self._re

    def __getattr__(self, attr):
        return getattr(self._compiled(), attr)


def regex(pattern, flags=0):
    """A compiled pattern made on first use. Supports the Pattern methods and attributes
    (search, match, sub, finditer, pattern...); pass ``.pattern`` where a str is needed."""
    return _Pattern(pattern, flags)
