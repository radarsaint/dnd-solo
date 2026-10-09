#!/usr/bin/env python3
"""Read-only Discord history exporter for the Kit training-corpus project.

The script uses Discord's REST API with a bot token. It never sends messages.
For a historical export the bot only needs View Channel and Read Message History
in the channels you want to archive.

Roanoke Season 3 preset:
    2020-07-18 00:00 through 2020-08-21 23:59:59 America/Los_Angeles
represented as a half-open interval ending 2020-08-22 00:00 -07:00.

Examples:
    DISCORD_BOT_TOKEN=... python3 scripts/export_discord_history.py \
        --guild 123456789012345678 --list-channels

    DISCORD_BOT_TOKEN=... python3 scripts/export_discord_history.py \
        --guild 123456789012345678 --preset roanoke-s3 \
        --channel 234567890123456789

    DISCORD_BOT_TOKEN=... python3 scripts/export_discord_history.py \
        --guild 123456789012345678 --preset roanoke-s3 \
        --all-readable --download-attachments
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "KitDiscordArchive/0.1 (+https://github.com/radarsaint/dnd-solo)"
DISCORD_EPOCH_MS = 1420070400000
TEXT_CHANNEL_TYPES = {0, 5}  # guild text, guild announcement

PRESETS = {
    "roanoke-s3": {
        "label": "Roanoke Season 3",
        "since": "2020-07-18T00:00:00-07:00",
        "until": "2020-08-22T00:00:00-07:00",
    }
}


class DiscordAPIError(RuntimeError):
    """Raised when Discord's API cannot satisfy a request."""


@dataclass
class ExportResult:
    channel_id: str
    channel_name: str
    message_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    output_file: str
    attachment_count: int


class DiscordAPI:
    def __init__(self, token: str, *, timeout: int = 30, max_retries: int = 8) -> None:
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{API_BASE}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

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
                if exc.code == 429:
                    retry_after = 1.0
                    try:
                        payload = json.loads(body)
                        retry_after = float(payload.get("retry_after", retry_after))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass
                    time.sleep(max(retry_after, 0.25))
                    continue
                if 500 <= exc.code < 600 and attempt + 1 < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise DiscordAPIError(
                    f"Discord API {exc.code} for {path}: {body[:500]}"
                ) from exc
            except URLError as exc:
                if attempt + 1 >= self.max_retries:
                    raise DiscordAPIError(f"Network error for {path}: {exc}") from exc
                time.sleep(min(2**attempt, 10))

        raise DiscordAPIError(f"Discord API retry limit exceeded for {path}")


def safe_name(value: str, fallback: str = "channel") -> str:
    cleaned = re.sub(r"[^\w.-]+", "-", value.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-.")
    return cleaned[:80] or fallback


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise SystemExit(
            f"Timestamp must include a timezone offset "
            f"(example: 2020-07-18T00:00:00-07:00): {value}"
        )
    return parsed.astimezone(timezone.utc)


def snowflake_for_datetime(value: datetime) -> str:
    ms = int(value.timestamp() * 1000)
    return str(max(0, ms - DISCORD_EPOCH_MS) << 22)


def compact_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "discriminator": user.get("discriminator"),
        "bot": bool(user.get("bot", False)),
        "system": bool(user.get("system", False)),
    }


def normalize_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "filename",
        "description",
        "content_type",
        "size",
        "url",
        "proxy_url",
        "height",
        "width",
        "ephemeral",
        "duration_secs",
        "waveform",
        "flags",
    )
    return {key: attachment.get(key) for key in keys if key in attachment}


def normalize_reaction(reaction: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": reaction.get("count"),
        "count_details": reaction.get("count_details"),
        "me": reaction.get("me"),
        "me_burst": reaction.get("me_burst"),
        "emoji": reaction.get("emoji"),
        "burst_colors": reaction.get("burst_colors"),
    }


def compact_referenced_message(message: dict[str, Any] | None) -> dict[str, Any] | None:
    if not message:
        return None
    return {
        "id": message.get("id"),
        "channel_id": message.get("channel_id"),
        "author": compact_user(message.get("author")),
        "timestamp": message.get("timestamp"),
        "edited_timestamp": message.get("edited_timestamp"),
        "content": message.get("content", ""),
    }


def normalize_message(
    raw: dict[str, Any],
    *,
    guild_id: str,
    channel: dict[str, Any],
) -> dict[str, Any]:
    member = raw.get("member") or {}
    return {
        "schema": "kit_discord_message_v1",
        "guild_id": guild_id,
        "channel": {
            "id": channel.get("id"),
            "name": channel.get("name"),
            "parent_id": channel.get("parent_id"),
            "type": channel.get("type"),
        },
        "id": raw.get("id"),
        "type": raw.get("type"),
        "timestamp": raw.get("timestamp"),
        "edited_timestamp": raw.get("edited_timestamp"),
        "author": compact_user(raw.get("author")),
        "member": {
            "nick": member.get("nick"),
            "roles": member.get("roles", []),
            "joined_at": member.get("joined_at"),
        }
        if member
        else None,
        "content": raw.get("content", ""),
        "tts": raw.get("tts"),
        "mention_everyone": raw.get("mention_everyone"),
        "mentions": [compact_user(user) for user in raw.get("mentions", [])],
        "mention_roles": raw.get("mention_roles", []),
        "attachments": [
            normalize_attachment(item) for item in raw.get("attachments", [])
        ],
        "embeds": raw.get("embeds", []),
        "reactions": [normalize_reaction(item) for item in raw.get("reactions", [])],
        "pinned": raw.get("pinned"),
        "flags": raw.get("flags"),
        "message_reference": raw.get("message_reference"),
        "referenced_message": compact_referenced_message(raw.get("referenced_message")),
        "interaction_metadata": raw.get("interaction_metadata"),
        "application_id": raw.get("application_id"),
        "webhook_id": raw.get("webhook_id"),
        "sticker_items": raw.get("sticker_items", []),
        "components": raw.get("components", []),
    }


def timestamp_of(message: dict[str, Any]) -> datetime:
    value = message.get("timestamp")
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parse_datetime(value) or datetime.min.replace(tzinfo=timezone.utc)


def resolve_channels(
    channels: list[dict[str, Any]], selectors: list[str], all_readable: bool
) -> list[dict[str, Any]]:
    text_channels = [c for c in channels if c.get("type") in TEXT_CHANNEL_TYPES]
    if all_readable:
        return sorted(text_channels, key=lambda c: (c.get("position", 0), c.get("id", "")))
    if not selectors:
        raise SystemExit(
            "Choose at least one --channel, or use --all-readable. "
            "Run --list-channels first to see IDs."
        )

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    by_id = {str(c.get("id")): c for c in text_channels}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for channel in text_channels:
        by_name.setdefault(str(channel.get("name", "")), []).append(channel)

    for selector in selectors:
        channel = by_id.get(selector)
        if channel is None:
            matches = by_name.get(selector, [])
            if len(matches) == 1:
                channel = matches[0]
            elif len(matches) > 1:
                ids = ", ".join(str(c.get("id")) for c in matches)
                raise SystemExit(
                    f"Channel name {selector!r} is ambiguous; use one of these IDs: {ids}"
                )
            else:
                raise SystemExit(f"No text channel matched {selector!r}")
        channel_id = str(channel.get("id"))
        if channel_id not in seen:
            selected.append(channel)
            seen.add(channel_id)
    return selected


def list_channels(channels: list[dict[str, Any]]) -> None:
    categories = {
        str(c.get("id")): str(c.get("name", ""))
        for c in channels
        if c.get("type") == 4
    }
    rows = []
    for channel in channels:
        if channel.get("type") not in TEXT_CHANNEL_TYPES:
            continue
        rows.append(
            (
                channel.get("position", 0),
                categories.get(str(channel.get("parent_id")), ""),
                str(channel.get("name", "")),
                str(channel.get("id", "")),
            )
        )
    for _, category, name, channel_id in sorted(rows):
        prefix = f"{category} / " if category else ""
        print(f"{channel_id}\t{prefix}#{name}")


def iter_channel_messages(
    api: DiscordAPI,
    channel_id: str,
    *,
    since: datetime | None,
    until: datetime | None,
) -> list[dict[str, Any]]:
    before = snowflake_for_datetime(until) if until else None
    pages: list[list[dict[str, Any]]] = []

    while True:
        params: dict[str, Any] = {"limit": 100}
        if before:
            params["before"] = before
        page = api.get(f"/channels/{channel_id}/messages", params=params)
        if not page:
            break
        pages.append(page)

        oldest = min(timestamp_of(message) for message in page)
        if since and oldest < since:
            break

        before = str(page[-1]["id"])
        if len(page) < 100:
            break

    messages: list[dict[str, Any]] = []
    for page in reversed(pages):
        messages.extend(reversed(page))

    if since:
        messages = [m for m in messages if timestamp_of(m) >= since]
    if until:
        messages = [m for m in messages if timestamp_of(m) < until]
    return messages


def download_file(url: str, destination: Path, timeout: int = 60) -> None:
    request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            destination.write_bytes(response.read())
    except (HTTPError, URLError) as exc:
        raise DiscordAPIError(f"Attachment download failed for {url}: {exc}") from exc


def export_channel(
    api: DiscordAPI,
    guild_id: str,
    channel: dict[str, Any],
    output_root: Path,
    *,
    since: datetime | None,
    until: datetime | None,
    download_attachments: bool,
) -> ExportResult:
    channel_id = str(channel["id"])
    channel_name = str(channel.get("name") or channel_id)
    print(f"Exporting #{channel_name} ({channel_id})...", file=sys.stderr)

    raw_messages = iter_channel_messages(
        api, channel_id, since=since, until=until
    )
    normalized = [
        normalize_message(raw, guild_id=guild_id, channel=channel)
        for raw in raw_messages
    ]

    if normalized and all(
        not message["content"] and not message["attachments"] and not message["embeds"]
        for message in normalized
    ):
        print(
            "  warning: every fetched message has empty content/attachments/embeds. "
            "Check Message Content access in the Discord Developer Portal.",
            file=sys.stderr,
        )

    messages_dir = output_root / "messages"
    messages_dir.mkdir(parents=True, exist_ok=True)
    output_file = messages_dir / f"{channel_id}_{safe_name(channel_name)}.jsonl"

    with output_file.open("w", encoding="utf-8") as handle:
        for message in normalized:
            handle.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    attachment_count = 0
    if download_attachments:
        attachment_dir = (
            output_root / "attachments" / f"{channel_id}_{safe_name(channel_name)}"
        )
        for message in normalized:
            for attachment in message["attachments"]:
                url = attachment.get("url")
                if not url:
                    continue
                filename = safe_name(
                    str(attachment.get("filename") or attachment.get("id") or "attachment")
                )
                target = (
                    attachment_dir
                    / f"{message['id']}_{attachment.get('id', 'x')}_{filename}"
                )
                attachment_dir.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    download_file(str(url), target)
                attachment["local_path"] = str(target.relative_to(output_root))
                attachment_count += 1

        # Rewrite now that local attachment paths have been added.
        with output_file.open("w", encoding="utf-8") as handle:
            for message in normalized:
                handle.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")

    timestamps = [m.get("timestamp") for m in normalized if m.get("timestamp")]
    return ExportResult(
        channel_id=channel_id,
        channel_name=channel_name,
        message_count=len(normalized),
        first_timestamp=timestamps[0] if timestamps else None,
        last_timestamp=timestamps[-1] if timestamps else None,
        output_file=str(output_file.relative_to(output_root)),
        attachment_count=attachment_count,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export historical Discord text channels to JSONL without sending messages."
    )
    parser.add_argument(
        "--guild",
        default=os.environ.get("DISCORD_GUILD_ID"),
        help="Discord guild/server ID (or set DISCORD_GUILD_ID)",
    )
    parser.add_argument(
        "--token-env",
        default="DISCORD_BOT_TOKEN",
        help="Environment variable containing the bot token (default: DISCORD_BOT_TOKEN)",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Apply a known campaign date window; roanoke-s3 covers the 2020 Season 3 play dates.",
    )
    parser.add_argument(
        "--since",
        help="Inclusive ISO-8601 timestamp with timezone; overrides preset start.",
    )
    parser.add_argument(
        "--until",
        help="Exclusive ISO-8601 timestamp with timezone; overrides preset end.",
    )
    parser.add_argument(
        "--channel",
        action="append",
        default=[],
        help="Text channel ID or exact channel name. Repeat for multiple channels.",
    )
    parser.add_argument(
        "--all-readable",
        action="store_true",
        help="Export every text/announcement channel visible to the bot.",
    )
    parser.add_argument(
        "--list-channels",
        action="store_true",
        help="Print visible text channel IDs/names and exit.",
    )
    parser.add_argument(
        "--download-attachments",
        action="store_true",
        help="Download message attachments into the local archive.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".private/discord/roanoke-s3"),
        help="Archive directory (default: .private/discord/roanoke-s3)",
    )
    args = parser.parse_args()

    if not args.guild:
        raise SystemExit("Missing --guild (or DISCORD_GUILD_ID).")

    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(
            f"Missing bot token. Set {args.token_env} in your shell; "
            "do not put the token in git."
        )

    preset = PRESETS.get(args.preset or "", {})
    since = parse_datetime(args.since or preset.get("since"))
    until = parse_datetime(args.until or preset.get("until"))
    if since and until and since >= until:
        raise SystemExit("--since must be earlier than --until.")

    api = DiscordAPI(token)
    guild = api.get(f"/guilds/{args.guild}")
    channels = api.get(f"/guilds/{args.guild}/channels")
    if not isinstance(channels, list):
        raise SystemExit("Discord did not return a channel list.")

    if args.list_channels:
        print(f"{guild.get('name', 'Unknown guild')} ({args.guild})")
        list_channels(channels)
        return 0

    selected = resolve_channels(channels, args.channel, args.all_readable)
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    roles = api.get(f"/guilds/{args.guild}/roles")
    write_json(
        output_root / "guild.json",
        {
            "id": guild.get("id"),
            "name": guild.get("name"),
            "description": guild.get("description"),
            "owner_id": guild.get("owner_id"),
        },
    )
    write_json(output_root / "roles.json", roles)
    write_json(output_root / "channels.json", channels)

    results: list[ExportResult] = []
    failures: list[dict[str, str]] = []
    for channel in selected:
        try:
            result = export_channel(
                api,
                str(args.guild),
                channel,
                output_root,
                since=since,
                until=until,
                download_attachments=args.download_attachments,
            )
            results.append(result)
            suffix = (
                f", {result.attachment_count} attachments"
                if args.download_attachments
                else ""
            )
            print(f"  {result.message_count} messages{suffix}", file=sys.stderr)
        except DiscordAPIError as exc:
            failures.append(
                {
                    "channel_id": str(channel.get("id")),
                    "channel_name": str(channel.get("name")),
                    "error": str(exc),
                }
            )
            print(f"  skipped: {exc}", file=sys.stderr)

    manifest = {
        "schema": "kit_discord_archive_v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "preset": args.preset,
        "preset_label": preset.get("label"),
        "guild": {
            "id": guild.get("id"),
            "name": guild.get("name"),
        },
        "window": {
            "since": since.isoformat() if since else None,
            "until_exclusive": until.isoformat() if until else None,
        },
        "selected_channel_ids": [str(c.get("id")) for c in selected],
        "channels": [result.__dict__ for result in results],
        "failures": failures,
        "notes": [
            "Raw Discord IDs are intentionally preserved so later processing can link identities and replies.",
            "Do not commit this archive. Derive privacy-filtered training data from it separately.",
            "Discord does not expose historical edit versions; edited_timestamp records only that a fetched message was edited.",
        ],
    }
    write_json(output_root / "manifest.json", manifest)

    print(f"\nArchive written to {output_root}")
    print(
        f"Exported {sum(r.message_count for r in results)} messages "
        f"from {len(results)} channels."
    )
    if failures:
        print(f"{len(failures)} channels were skipped; see manifest.json.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
