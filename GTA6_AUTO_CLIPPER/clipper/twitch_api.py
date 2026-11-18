"""Official Twitch Helix API (app access token injected by the session proxy).

- live_channels(): who is streaming the target game right now, by viewers, per language
- clips(): a channel's clips since a timestamp, with exact game_id (drops IRL/other games)
"""
from __future__ import annotations

import os

import requests

API = "https://api.twitch.tv/helix"


def _headers(cfg: dict) -> dict:
    t = cfg["twitch_api"]
    token = os.environ.get(t.get("token_env", "TWITCH_APP_TOKEN"), "proxy-injected")
    return {"Client-Id": t["client_id"], "Authorization": f"Bearer {token}"}


def enabled(cfg: dict) -> bool:
    return bool((cfg.get("twitch_api") or {}).get("client_id"))


def get(cfg: dict, path: str, params) -> dict:
    r = requests.get(f"{API}/{path}", headers=_headers(cfg), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def live_channels(cfg: dict) -> list[dict]:
    """Top live streams of the target game. Returns [{login, name, lang, viewers}]."""
    t = cfg["twitch_api"]
    out, cursor = [], None
    for _ in range(t.get("live_pages", 3)):
        params = {"game_id": t["game_id"], "first": 100}
        if cursor:
            params["after"] = cursor
        d = get(cfg, "streams", params)
        out += [{"login": s["user_login"], "name": s["user_name"], "id": s["user_id"],
                 "lang": (s.get("language") or "en")[:2], "viewers": s["viewer_count"]} for s in d.get("data", [])]
        cursor = (d.get("pagination") or {}).get("cursor")
        if not cursor:
            break
    picked, per_lang = [], {}
    caps = t.get("live_top_per_lang", {})
    default_cap = caps.get("other", 3)
    for s in sorted(out, key=lambda x: x["viewers"], reverse=True):
        if s["viewers"] < t.get("live_min_viewers", 500):
            continue
        n = per_lang.get(s["lang"], 0)
        if n >= caps.get(s["lang"], default_cap):
            continue
        per_lang[s["lang"]] = n + 1
        picked.append(s)
    return picked


def user_ids(cfg: dict, logins: list[str]) -> dict[str, str]:
    ids = {}
    for i in range(0, len(logins), 100):
        d = get(cfg, "users", [("login", l) for l in logins[i:i + 100]])
        ids.update({u["login"]: u["id"] for u in d.get("data", [])})
    return ids


def clips(cfg: dict, broadcaster_id: str, started_at: str, first: int = 20) -> list[dict]:
    d = get(cfg, "clips", {"broadcaster_id": broadcaster_id, "started_at": started_at, "first": first})
    return d.get("data", [])
