#!/usr/bin/env python3
"""Least-privilege setup/probe helper for the Roanoke Discord archive bot.

This helper deliberately does not fetch message content. It exists to:
- generate a bot install URL requesting only View Channel + Read Message History;
- verify a bot token from an environment variable without printing it;
- verify guild membership;
- compute effective per-channel permissions from roles/overwrites;
- list which text channels the bot can view and read history from.

Message export remains in scripts/export_discord_history.py and is gated by the
Discord Developer Policy for AI/ML training use.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "KitDiscordArchiveSetup/0.1 (+https://github.com/radarsaint/dnd-solo)"

PERMISSION_ADMINISTRATOR = 1 << 3
PERMISSION_VIEW_CHANNEL = 1 << 10
PERMISSION_READ_MESSAGE_HISTORY = 1 << 16
ARCHIVE_PERMISSIONS = PERMISSION_VIEW_CHANNEL | PERMISSION_READ_MESSAGE_HISTORY
TEXT_CHANNEL_TYPES = {0, 5}  # guild text, guild announcement
CATEGORY_TYPE = 4


class DiscordAPIError(RuntimeError):
    pass


class DiscordAPI:
    def __init__(self, token: str, *, timeout: int = 30, max_retries: int = 5) -> None:
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries

    def get(self, path: str) -> Any:
        url = f"{API_BASE}{path}"
        for attempt in range(self.max_retries):
            request = Request(
                url,
                headers={
                    "Authorization": f"Bot {self.token}",
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
                method="GET",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    return json.loads(body.decode("utf-8")) if body else None
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt + 1 < self.max_retries:
                    retry_after = 1.0
                    try:
                        retry_after = float(json.loads(body).get("retry_after", 1.0))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass
                    time.sleep(max(retry_after, 0.25))
                    continue
                if 500 <= exc.code < 600 and attempt + 1 < self.max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise DiscordAPIError(
                    f"Discord API {exc.code} for {path}: {body[:300]}"
                ) from exc
            except URLError as exc:
                if attempt + 1 >= self.max_retries:
                    raise DiscordAPIError(f"Network error for {path}: {exc}") from exc
                time.sleep(min(2**attempt, 8))
        raise DiscordAPIError(f"Discord API retry limit exceeded for {path}")


def build_install_url(client_id: str, guild_id: str | None = None) -> str:
    params = {
        "client_id": str(client_id),
        "scope": "bot",
        "permissions": str(ARCHIVE_PERMISSIONS),
    }
    if guild_id:
        params["guild_id"] = str(guild_id)
        params["disable_guild_select"] = "true"
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"


def _perm(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def base_permissions(
    guild_id: str, member: dict[str, Any], roles: list[dict[str, Any]]
) -> int:
    role_map = {str(role.get("id")): role for role in roles}
    everyone = role_map.get(str(guild_id), {})
    permissions = _perm(everyone.get("permissions"))
    for role_id in member.get("roles", []) or []:
        role = role_map.get(str(role_id))
        if role:
            permissions |= _perm(role.get("permissions"))
    return permissions


def channel_permissions(
    guild_id: str,
    bot_user_id: str,
    member: dict[str, Any],
    roles: list[dict[str, Any]],
    channel: dict[str, Any],
) -> int:
    permissions = base_permissions(guild_id, member, roles)
    if permissions & PERMISSION_ADMINISTRATOR:
        return (1 << 63) - 1

    overwrites = channel.get("permission_overwrites", []) or []

    everyone = next(
        (
            ow
            for ow in overwrites
            if str(ow.get("id")) == str(guild_id) and int(ow.get("type", 0)) == 0
        ),
        None,
    )
    if everyone:
        permissions &= ~_perm(everyone.get("deny"))
        permissions |= _perm(everyone.get("allow"))

    member_role_ids = {str(role_id) for role_id in member.get("roles", []) or []}
    role_allow = 0
    role_deny = 0
    for overwrite in overwrites:
        if int(overwrite.get("type", 0)) != 0:
            continue
        if str(overwrite.get("id")) in member_role_ids:
            role_allow |= _perm(overwrite.get("allow"))
            role_deny |= _perm(overwrite.get("deny"))
    permissions &= ~role_deny
    permissions |= role_allow

    member_overwrite = next(
        (
            ow
            for ow in overwrites
            if str(ow.get("id")) == str(bot_user_id) and int(ow.get("type", 0)) == 1
        ),
        None,
    )
    if member_overwrite:
        permissions &= ~_perm(member_overwrite.get("deny"))
        permissions |= _perm(member_overwrite.get("allow"))

    return permissions


def permission_status(permissions: int) -> tuple[bool, bool, str]:
    can_view = bool(permissions & PERMISSION_VIEW_CHANNEL)
    can_history = bool(permissions & PERMISSION_READ_MESSAGE_HISTORY)
    if can_view and can_history:
        status = "OK"
    elif not can_view and not can_history:
        status = "NO_VIEW+NO_HISTORY"
    elif not can_view:
        status = "NO_VIEW"
    else:
        status = "NO_HISTORY"
    return can_view, can_history, status


def channel_rows(
    guild_id: str,
    bot_user_id: str,
    member: dict[str, Any],
    roles: list[dict[str, Any]],
    channels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    categories = {
        str(channel.get("id")): str(channel.get("name", ""))
        for channel in channels
        if channel.get("type") == CATEGORY_TYPE
    }
    rows: list[dict[str, Any]] = []
    for channel in channels:
        if channel.get("type") not in TEXT_CHANNEL_TYPES:
            continue
        permissions = channel_permissions(
            guild_id, bot_user_id, member, roles, channel
        )
        can_view, can_history, status = permission_status(permissions)
        rows.append(
            {
                "id": str(channel.get("id", "")),
                "name": str(channel.get("name", "")),
                "category": categories.get(str(channel.get("parent_id")), ""),
                "position": int(channel.get("position", 0) or 0),
                "can_view": can_view,
                "can_read_history": can_history,
                "status": status,
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["position"], row["category"], row["name"], row["id"]),
    )


def run_probe(token: str, guild_id: str, *, json_output: bool = False) -> int:
    api = DiscordAPI(token)
    bot = api.get("/users/@me")
    application = api.get("/oauth2/applications/@me")
    guild = api.get(f"/guilds/{guild_id}")
    member = api.get(f"/guilds/{guild_id}/members/{bot['id']}")
    roles = api.get(f"/guilds/{guild_id}/roles")
    channels = api.get(f"/guilds/{guild_id}/channels")

    if not isinstance(roles, list) or not isinstance(channels, list):
        raise DiscordAPIError("Discord did not return expected guild roles/channels.")

    base = base_permissions(guild_id, member, roles)
    rows = channel_rows(guild_id, str(bot["id"]), member, roles, channels)
    payload = {
        "application": {
            "id": str(application.get("id", "")),
            "name": application.get("name"),
        },
        "bot": {
            "id": str(bot.get("id", "")),
            "username": bot.get("username"),
        },
        "guild": {
            "id": str(guild.get("id", guild_id)),
            "name": guild.get("name"),
        },
        "requested_permissions": ARCHIVE_PERMISSIONS,
        "base_has_administrator": bool(base & PERMISSION_ADMINISTRATOR),
        "channels": rows,
    }

    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            f"Application: {payload['application']['name']} "
            f"({payload['application']['id']})"
        )
        print(f"Bot: {payload['bot']['username']} ({payload['bot']['id']})")
        print(f"Guild: {payload['guild']['name']} ({payload['guild']['id']})")
        print(f"Requested permission bitfield: {ARCHIVE_PERMISSIONS}")
        if payload["base_has_administrator"]:
            print("WARNING: bot currently has Administrator; remove it before archival use.")
        print()
        for row in rows:
            prefix = f"{row['category']} / " if row["category"] else ""
            print(f"{row['status']:<18} {row['id']}\t{prefix}#{row['name']}")

        ok = sum(1 for row in rows if row["status"] == "OK")
        blocked = len(rows) - ok
        print(
            f"\nReadable history: {ok}/{len(rows)} text channels; "
            f"blocked/incomplete: {blocked}."
        )

    if payload["base_has_administrator"]:
        return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Configure/probe the least-privilege Discord archive bot "
            "without reading messages."
        )
    )
    parser.add_argument("--guild", default=os.environ.get("DISCORD_GUILD_ID"))
    parser.add_argument(
        "--client-id", default=os.environ.get("DISCORD_APPLICATION_ID")
    )
    parser.add_argument("--token-env", default="DISCORD_BOT_TOKEN")
    parser.add_argument("--install-url", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.install_url:
        client_id = args.client_id
        if not client_id:
            token = os.environ.get(args.token_env)
            if not token:
                raise SystemExit(
                    "Missing application ID. Set DISCORD_APPLICATION_ID/--client-id, "
                    f"or set {args.token_env} so the application ID can be read safely."
                )
            application = DiscordAPI(token).get("/oauth2/applications/@me")
            client_id = str(application.get("id", ""))
            if not client_id:
                raise SystemExit("Discord did not return the bot application ID.")
        print(build_install_url(client_id, args.guild))
        if not args.probe:
            return 0

    if args.probe:
        if not args.guild:
            raise SystemExit("Missing --guild (or DISCORD_GUILD_ID).")
        token = os.environ.get(args.token_env)
        if not token:
            raise SystemExit(
                f"Missing bot token. Set {args.token_env} locally; "
                "never paste it into chat or git."
            )
        return run_probe(token, str(args.guild), json_output=args.json)

    raise SystemExit("Choose --install-url and/or --probe.")


if __name__ == "__main__":
    sys.exit(main())
