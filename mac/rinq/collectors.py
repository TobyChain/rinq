from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .state import clamp_pct
from . import sources


def _mock(_cfg: dict) -> list[dict[str, Any]]:
    t = int(time.time())
    return [
        {
            "id": "codex-5h",
            "label": "Codex 5h",
            "vendor": "codex",
            "kind": "window",
            "usedPercent": clamp_pct(68),
            "usedValue": 68,
            "totalValue": 100,
            "valueUnit": "percent",
            "resetsAt": t + 176 * 60,
            "windowMins": 300,
            "accent": "blue",
        },
        {
            "id": "codex-week",
            "label": "Codex week",
            "vendor": "codex",
            "kind": "window",
            "usedPercent": clamp_pct(42),
            "usedValue": 42,
            "totalValue": 100,
            "valueUnit": "percent",
            "resetsAt": t + 3 * 86400,
            "windowMins": 10080,
            "accent": "indigo",
        },
        {
            "id": "openai-api",
            "label": "OpenAI API",
            "vendor": "openai",
            "kind": "budget",
            "usedPercent": clamp_pct(37),
            "spentUsd": 7.42,
            "budgetUsd": 20.0,
            "usedValue": 7.42,
            "totalValue": 20.0,
            "valueUnit": "USD",
            "resetsAt": t + 20 * 86400,
            "windowMins": 43200,
            "accent": "green",
        },
        {
            "id": "deepseek-balance",
            "label": "DeepSeek",
            "vendor": "deepseek",
            "kind": "balance",
            "usedPercent": clamp_pct(34),
            "remainingPercent": clamp_pct(66),
            "remaining": 13.2,
            "currency": "CNY",
            "usedValue": 6.8,
            "totalValue": 20.0,
            "valueUnit": "CNY",
            "accent": "teal",
        },
        {
            "id": "moonshot-balance",
            "label": "Kimi",
            "vendor": "moonshot",
            "kind": "balance",
            "usedPercent": clamp_pct(55),
            "remainingPercent": clamp_pct(45),
            "remaining": 22.5,
            "currency": "CNY",
            "usedValue": 27.5,
            "totalValue": 50.0,
            "valueUnit": "CNY",
            "accent": "purple",
        },
        {
            "id": "zhipu-balance",
            "label": "GLM",
            "vendor": "zhipu",
            "kind": "balance",
            "usedPercent": clamp_pct(70),
            "remainingPercent": clamp_pct(30),
            "remaining": 15.0,
            "currency": "CNY",
            "usedValue": 35.0,
            "totalValue": 50.0,
            "valueUnit": "CNY",
            "accent": "red",
        },
        {
            "id": "minimax-balance",
            "label": "MiniMax",
            "vendor": "minimax",
            "kind": "balance",
            "usedPercent": None,
            "remainingPercent": None,
            "status": "unknown",
            "currency": "CNY",
            "accent": "orange",
        },
        {
            "id": "xiaomi-balance",
            "label": "MiMo",
            "vendor": "xiaomi",
            "kind": "balance",
            "usedPercent": None,
            "remainingPercent": None,
            "status": "unknown",
            "currency": "CNY",
            "accent": "orange",
        },
        {
            "id": "anthropic-api",
            "label": "Claude API",
            "vendor": "anthropic",
            "kind": "budget",
            "usedPercent": None,
            "remainingPercent": None,
            "status": "unknown",
            "budgetUsd": 20.0,
            "accent": "orange",
        },
    ]


def _get_json(
    url: str,
    key: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    headers = {"Authorization": f"Bearer {key}"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


def _balance_ring(
    cfg: dict,
    *,
    vid: str,
    label: str,
    accent: str,
    remaining: float | None,
    currency: str,
) -> dict[str, Any]:
    ring: dict[str, Any] = {
        "id": f"{vid}-balance",
        "label": label,
        "vendor": vid,
        "kind": "balance",
        "usedPercent": None,
        "remaining": round(remaining, 2) if remaining is not None else None,
        "currency": currency,
        "accent": accent,
    }
    full = (cfg.get("balanceFull") or {}).get(vid)
    if remaining is not None and isinstance(full, (int, float)) and full > 0:
        remaining_pct = clamp_pct(remaining / full * 100.0)
        ring["remainingPercent"] = remaining_pct
        ring["usedPercent"] = clamp_pct(100 - remaining / full * 100.0)
        ring["usedValue"] = round(max(0.0, float(full) - remaining), 2)
        ring["totalValue"] = round(float(full), 2)
        ring["valueUnit"] = currency
    else:
        ring["remainingPercent"] = None
        if remaining is None:
            ring["status"] = "unknown"
    return ring


def _deepseek(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "deepseek", "DEEPSEEK_API_KEY")
    if not key:
        return []
    data = _get_json("https://api.deepseek.com/user/balance", key)
    remaining = None
    if data:
        for info in data.get("balance_infos", []):
            if info.get("currency") == "CNY":
                try:
                    remaining = float(info.get("total_balance"))
                except (TypeError, ValueError):
                    pass
    if remaining is None and data:
        try:
            remaining = float(data.get("balance_infos", [{}])[0].get("total_balance"))
        except (TypeError, ValueError, IndexError, KeyError):
            remaining = None
    return [_balance_ring(cfg, vid="deepseek", label="DeepSeek", accent="teal",
                          remaining=remaining, currency="CNY")]


def _moonshot(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "moonshot", "MOONSHOT_API_KEY")
    if not key:
        return []
    data = _get_json("https://api.moonshot.cn/v1/users/me/balance", key)
    remaining = None
    if data:
        d = data.get("data", data)
        for field in ("available_balance", "balance", "total_balance"):
            try:
                remaining = float(d.get(field))
                break
            except (TypeError, ValueError):
                continue
    return [_balance_ring(cfg, vid="moonshot", label="Kimi", accent="purple",
                          remaining=remaining, currency="CNY")]


def _zhipu(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "zhipu", "ZHIPU_API_KEY")
    if not key:
        return []
    # No stable documented personal balance route; hit the resource endpoint and
    # degrade to unknown if the shape does not carry a remaining amount.
    data = _get_json("https://open.bigmodel.cn/api/monitor/usage/quota/limit", key)
    remaining = None
    if data:
        d = data.get("data", data)
        for field in ("balance", "remaining_amount", "available_balance", "total_balance"):
            try:
                remaining = float(d.get(field))
                break
            except (TypeError, ValueError):
                continue
    return [_balance_ring(cfg, vid="zhipu", label="GLM", accent="red",
                          remaining=remaining, currency="CNY")]


def _minimax(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "minimax", "MINIMAX_API_KEY")
    if not key:
        return []
    data = _get_json(
        "https://api.minimaxi.com/v1/api/openplatform/coding_plan/remains", key
    )
    if not data:
        return []
    return _minimax_rings(data)


def _minimax_rings(data: dict[str, Any]) -> list[dict[str, Any]]:
    general = next(
        (m for m in data.get("model_remains", []) if m.get("model_name") == "general"),
        None,
    )
    if general is None:
        return []
    interval_used = int(general.get("current_interval_usage_count", 0))
    interval_total = int(general.get("current_interval_total_count", 0))
    weekly_used = int(general.get("current_weekly_usage_count", 0))
    weekly_total = int(general.get("current_weekly_total_count", 0))
    interval_pct = clamp_pct(100 - int(general.get("current_interval_remaining_percent", 0)))
    weekly_pct = clamp_pct(100 - int(general.get("current_weekly_remaining_percent", 0)))
    return [
        {
            "id": "minimax-5h",
            "label": "MiniMax 5h",
            "vendor": "minimax",
            "kind": "window",
            "usedPercent": interval_pct,
            "usedValue": interval_used if interval_total > 0 else interval_pct,
            "totalValue": interval_total if interval_total > 0 else 100,
            "valueUnit": "requests" if interval_total > 0 else "percent",
            "resetsAt": int(general.get("end_time", 0)) // 1000,
            "windowMins": 300,
            "accent": "orange",
        },
        {
            "id": "minimax-week",
            "label": "MiniMax week",
            "vendor": "minimax",
            "kind": "window",
            "usedPercent": weekly_pct,
            "usedValue": weekly_used if weekly_total > 0 else weekly_pct,
            "totalValue": weekly_total if weekly_total > 0 else 100,
            "valueUnit": "requests" if weekly_total > 0 else "percent",
            "resetsAt": int(general.get("weekly_end_time", 0)) // 1000,
            "windowMins": 10080,
            "accent": "red",
        },
    ]


def _codex_rings(data: dict[str, Any]) -> list[dict[str, Any]]:
    rl = data.get("rate_limit", {})
    primary = rl.get("primary_window", {})
    secondary = rl.get("secondary_window", {})
    rings = []
    if primary:
        rings.append(
            {
                "id": "codex-5h",
                "label": "Codex 5h",
                "vendor": "codex",
                "kind": "window",
                "usedPercent": clamp_pct(int(primary.get("used_percent", 0))),
                "usedValue": clamp_pct(int(primary.get("used_percent", 0))),
                "totalValue": 100,
                "valueUnit": "percent",
                "resetsAt": primary.get("reset_at"),
                "windowMins": round(int(primary.get("limit_window_seconds", 18000)) / 60),
                "accent": "blue",
            }
        )
    if secondary:
        rings.append(
            {
                "id": "codex-week",
                "label": "Codex week",
                "vendor": "codex",
                "kind": "window",
                "usedPercent": clamp_pct(int(secondary.get("used_percent", 0))),
                "usedValue": clamp_pct(int(secondary.get("used_percent", 0))),
                "totalValue": 100,
                "valueUnit": "percent",
                "resetsAt": secondary.get("reset_at"),
                "windowMins": round(int(secondary.get("limit_window_seconds", 604800)) / 60),
                "accent": "indigo",
            }
        )
    return rings


def _xiaomi(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "xiaomi", "XIAOMI_API_KEY")
    # No confirmed public balance route; only show when explicitly configured.
    if not key:
        return []
    return []


def _codex(cfg: dict) -> list[dict[str, Any]]:
    token, account = sources.codex_chatgpt_token()
    if not token:
        return []
    data = _get_json(
        "https://chatgpt.com/backend-api/wham/usage",
        token,
        {"ChatGPT-Account-Id": account or ""},
    )
    if not data:
        return []
    return _codex_rings(data)


def _openai(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "openai", "OPENAI_ADMIN_KEY")
    budget = float(cfg.get("budgetUsd", {}).get("openai", 20.0))
    if not key:
        return []
    start = int(datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).timestamp())
    url = f"https://api.openai.com/v1/organization/costs?start_time={start}&bucket_width=1d&limit=31"
    payload = _get_json(url, key) or {}
    spent = 0.0
    for bucket in payload.get("data", []):
        for result in bucket.get("results", []):
            amt = result.get("amount", {})
            if amt.get("currency") == "usd":
                try:
                    spent += float(amt.get("value", 0.0))
                except (TypeError, ValueError):
                    pass
    return [
        {
            "id": "openai-api",
            "label": "OpenAI API",
            "vendor": "openai",
            "kind": "budget",
            "usedPercent": clamp_pct(spent / budget * 100.0 if budget else None),
            "remainingPercent": clamp_pct((budget - spent) / budget * 100.0 if budget else None),
            "spentUsd": round(spent, 2),
            "budgetUsd": budget,
            "usedValue": round(spent, 2),
            "totalValue": round(budget, 2),
            "valueUnit": "USD",
            "resetsAt": _month_end_epoch(),
            "windowMins": 43200,
            "accent": "green",
        }
    ]


def _anthropic(cfg: dict) -> list[dict[str, Any]]:
    # Requires an org Admin key (Usage & Cost API); hide until configured.
    key = sources.vendor_key(cfg, "anthropic", "ANTHROPIC_ADMIN_KEY")
    if not key:
        return []
    return []


def _month_end_epoch() -> int:
    now = datetime.now(timezone.utc)
    nxt = now.replace(year=now.year + 1, month=1, day=1) if now.month == 12 else now.replace(month=now.month + 1, day=1)
    return int(nxt.timestamp())


_COLLECTORS = {
    "mock": _mock,
    "codex": _codex,
    "openai": _openai,
    "anthropic": _anthropic,
    "deepseek": _deepseek,
    "moonshot": _moonshot,
    "zhipu": _zhipu,
    "minimax": _minimax,
    "xiaomi": _xiaomi,
}

_STATUS_META = {
    "codex": ("ChatGPT / Codex", "blue"),
    "minimax": ("MiniMax Coding Plan", "orange"),
    "deepseek": ("DeepSeek", "teal"),
    "openai": ("OpenAI API", "green"),
    "anthropic": ("Claude API", "orange"),
    "moonshot": ("Kimi / Moonshot", "purple"),
    "zhipu": ("GLM / Zhipu", "red"),
    "xiaomi": ("Xiaomi MiMo", "orange"),
}


def _status_ring(vendor: str, status: str) -> dict[str, Any]:
    label, _accent = _STATUS_META[vendor]
    detail = {
        "not_connected": "Connect an account or add a credential",
        "quota_unavailable": "Connected, but live quota is unavailable",
    }[status]
    return {
        "id": f"{vendor}-status",
        "label": label,
        "vendor": vendor,
        "kind": "status",
        "usedPercent": None,
        "usedValue": None,
        "totalValue": None,
        "valueUnit": None,
        "status": status,
        "statusDetail": detail,
        "accent": "gray",
    }


def collect(cfg: dict) -> list[dict[str, Any]]:
    rings: list[dict[str, Any]] = []
    enabled = cfg.get("enabled") or {}
    collector_names = list(cfg.get("collectors", ["mock"]))
    for name, is_enabled in enabled.items():
        if is_enabled is True and name in _COLLECTORS and name not in collector_names:
            collector_names.append(name)
    for name in collector_names:
        if enabled.get(name) is False:
            continue
        fn = _COLLECTORS.get(name)
        if fn:
            collected = [
                ring for ring in fn(cfg)
                if not (
                    ring.get("status") == "unknown"
                    and ring.get("usedPercent") is None
                    and ring.get("remaining") is None
                )
            ]
            rings.extend(collected)
            # Explicitly enabled providers stay visible even when no live quota
            # is available. The status item is not a percentage and does not
            # participate in quota alerts.
            if enabled.get(name) is True and not collected and name in _STATUS_META:
                status = "quota_unavailable" if sources.has_vendor_credential(cfg, name) else "not_connected"
                rings.append(_status_ring(name, status))
    # Hide rings for vendors the user explicitly turned off.
    rings = [r for r in rings if enabled.get(r.get("vendor"), True) is not False]
    from . import config as _config
    rings.sort(key=_config.ring_sort_key(cfg))
    return rings
