"""Goldscale's deterministic magic item pricing, vendored from Brendon's Goldscale bot.

Source: radarsaint/goldscale@a0a18c6, files goldscale/{parser,pricing,formatting,clarification}.py,
copied verbatim except that package imports are relative. The Discord bot (bot.py) is not
vendored: it needs discord.py. Everything here is stdlib only. Credit: Goldscale.
Kit's DM-assistant side calls it through runtime/kit_appraise.py.
"""
SOURCE = 'radarsaint/goldscale@a0a18c6'
