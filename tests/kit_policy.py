"""Test helper: validator probes that submit a rejected performance and expect it to raise.

Since Brendon's 2026-10-14 plan (step 2b), a rejected narration commits the engine's own
public_event sentence instead (kit_agent.ENGINE_LINE_AFTER_REJECTIONS, default 1), so through
the bridge nothing raises. A test that probes WHAT a validator rejects runs with that cap out of
reach, so the rejection still surfaces as an exception and nothing about the validator is
loosened. The engine-line policy itself is tested in test_kit_open_ask."""
from unittest import mock

from runtime import kit_agent


def rejections_raise(test):
    return mock.patch.object(kit_agent, 'ENGINE_LINE_AFTER_REJECTIONS', 10 ** 6)(test)
