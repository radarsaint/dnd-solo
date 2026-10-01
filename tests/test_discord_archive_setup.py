import importlib.util
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "discord_archive_setup.py"
spec = importlib.util.spec_from_file_location("discord_archive_setup", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class SetupTests(unittest.TestCase):
    def test_install_url_is_least_privilege(self):
        url = mod.build_install_url("123", "456")
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["123"])
        self.assertEqual(query["scope"], ["bot"])
        self.assertEqual(query["permissions"], ["66560"])
        self.assertEqual(query["guild_id"], ["456"])
        self.assertEqual(query["disable_guild_select"], ["true"])
        self.assertEqual(mod.ARCHIVE_PERMISSIONS, (1 << 10) | (1 << 16))

    def test_base_permissions_union_roles(self):
        roles = [
            {"id": "g", "permissions": str(1 << 10)},
            {"id": "r", "permissions": str(1 << 16)},
        ]
        member = {"roles": ["r"]}
        self.assertEqual(mod.base_permissions("g", member, roles), 66560)

    def test_channel_everyone_deny_then_role_allow(self):
        roles = [
            {"id": "g", "permissions": str(66560)},
            {"id": "r", "permissions": "0"},
        ]
        member = {"roles": ["r"]}
        channel = {
            "permission_overwrites": [
                {"id": "g", "type": 0, "allow": "0", "deny": str(1 << 10)},
                {"id": "r", "type": 0, "allow": str(1 << 10), "deny": "0"},
            ]
        }
        permissions = mod.channel_permissions("g", "bot", member, roles, channel)
        self.assertTrue(permissions & mod.PERMISSION_VIEW_CHANNEL)
        self.assertTrue(permissions & mod.PERMISSION_READ_MESSAGE_HISTORY)

    def test_member_deny_wins_last(self):
        roles = [{"id": "g", "permissions": str(66560)}]
        member = {"roles": []}
        channel = {
            "permission_overwrites": [
                {"id": "bot", "type": 1, "allow": "0", "deny": str(1 << 16)}
            ]
        }
        permissions = mod.channel_permissions("g", "bot", member, roles, channel)
        self.assertTrue(permissions & mod.PERMISSION_VIEW_CHANNEL)
        self.assertFalse(permissions & mod.PERMISSION_READ_MESSAGE_HISTORY)
        self.assertEqual(mod.permission_status(permissions)[2], "NO_HISTORY")

    def test_admin_is_detectable(self):
        roles = [{"id": "g", "permissions": str(1 << 3)}]
        member = {"roles": []}
        permissions = mod.base_permissions("g", member, roles)
        self.assertTrue(permissions & mod.PERMISSION_ADMINISTRATOR)


if __name__ == "__main__":
    unittest.main()
