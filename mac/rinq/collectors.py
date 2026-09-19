from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
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
        {
            "id": "jina-balance",
            "label": "Jina",
            "vendor": "jina",
            "kind": "balance",
            "usedPercent": clamp_pct(18),
            "remainingPercent": clamp_pct(82),
            "remaining": 8_200_000,
            "currency": "tokens",
            "usedValue": 1_800_000,
            "totalValue": 10_000_000,
            "valueUnit": "tokens",
            "accent": "teal",
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
    if not data:
        return []
    remaining = None
    for info in data.get("balance_infos", []):
        if info.get("currency") == "CNY":
            remaining = _first_number(info, "total_balance")
            if remaining is not None:
                break
    if remaining is None:
        try:
            remaining = _first_number(data.get("balance_infos", [{}])[0], "total_balance")
        except (IndexError, KeyError, TypeError):
            remaining = None
    if remaining is None:
        # A subscription key may return rolling windows instead of a balance.
        windows = _credit_limit_windows(
            data.get("data", data), vid="deepseek", label="DeepSeek", accent="teal"
        )
        if windows:
            return windows
    return [_balance_ring(cfg, vid="deepseek", label="DeepSeek", accent="teal",
                          remaining=remaining, currency="CNY")]


def _moonshot(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "moonshot", "MOONSHOT_API_KEY")
    if not key:
        return []
    data = _get_json("https://api.moonshot.cn/v1/users/me/balance", key)
    if not data:
        return []
    body = data.get("data", data)
    remaining = _first_number(body, "available_balance", "balance", "total_balance")
    if remaining is None:
        windows = _credit_limit_windows(body, vid="moonshot", label="Kimi", accent="purple")
        if windows:
            return windows
    return [_balance_ring(cfg, vid="moonshot", label="Kimi", accent="purple",
                          remaining=remaining, currency="CNY")]


def _zhipu(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "zhipu", "ZHIPU_API_KEY")
    if not key:
        return []
    data = _get_json("https://open.bigmodel.cn/api/monitor/usage/quota/limit", key)
    if not data:
        return []
    body = data.get("data", data) if isinstance(data, dict) else {}
    # Coding-plan / subscription keys return rolling rate-limit windows, not a
    # prepaid CNY balance. Render those as window rings like Codex.
    windows = _credit_limit_windows(body, vid="zhipu", label="GLM", accent="red")
    if windows:
        return windows
    # Fall back to a prepaid balance shape for pay-as-you-go keys.
    remaining = _first_number(body, "balance", "remaining_amount", "available_balance", "total_balance")
    return [_balance_ring(cfg, vid="zhipu", label="GLM", accent="red",
                          remaining=remaining, currency="CNY")]


# Zhipu/GLM report each window as a CREDIT_LIMIT entry with a time unit code and
# a count. Map the common codes to minutes; fall back to the reset horizon.
_CREDIT_UNIT_MINUTES = {1: 1, 2: 60, 3: 60, 4: 1440, 5: 43200, 6: 10080}


def _credit_limit_windows(
    body: dict[str, Any], *, vid: str, label: str, accent: str
) -> list[dict[str, Any]]:
    """Parse a `limits` array of rolling usage windows into window rings.

    Recognizes the shape used by GLM's quota/limit endpoint: each entry carries
    `usage` (window cap), `remaining`, `nextResetTime` (epoch ms) and a
    `unit`/`number` window size. Returns [] when the shape is absent so callers
    can fall back to a balance reading.
    """
    if not isinstance(body, dict):
        return []
    limits = body.get("limits")
    if not isinstance(limits, list) or not limits:
        return []
    rings: list[dict[str, Any]] = []
    now = int(time.time())
    for entry in limits:
        if not isinstance(entry, dict):
            continue
        cap = _first_number(entry, "usage", "limit", "total")
        remaining = _first_number(entry, "remaining", "remaining_amount")
        if cap is None or remaining is None or cap <= 0:
            continue
        used = max(0.0, cap - remaining)
        reset_ms = entry.get("nextResetTime") or entry.get("next_reset_time")
        resets_at = int(reset_ms) // 1000 if isinstance(reset_ms, (int, float)) else None
        unit = entry.get("unit")
        number = entry.get("number") or 1
        if isinstance(unit, int) and unit in _CREDIT_UNIT_MINUTES:
            window_mins = int(_CREDIT_UNIT_MINUTES[unit] * number)
        elif resets_at:
            window_mins = max(1, round((resets_at - now) / 60))
        else:
            window_mins = 300
        if window_mins <= 300:
            rid, suffix, ring_accent = f"{vid}-5h", "5h", accent
        elif window_mins >= 10080:
            rid, suffix, ring_accent = f"{vid}-week", "week", "indigo"
        else:
            rid, suffix, ring_accent = f"{vid}-w{unit}-{number}", f"{number}u{unit}", accent
        rings.append({
            "id": rid,
            "label": f"{label} {suffix}",
            "vendor": vid,
            "kind": "window",
            "usedPercent": clamp_pct(used / cap * 100.0),
            "usedValue": int(used),
            "totalValue": int(cap),
            "valueUnit": "requests",
            "resetsAt": resets_at,
            "windowMins": window_mins,
            "accent": ring_accent,
        })
    return rings


def _first_number(obj: dict[str, Any], *names: str) -> float | None:
    """Return the first field in `names` that parses as a number, else None."""
    if not isinstance(obj, dict):
        return None
    for name in names:
        try:
            return float(obj[name])
        except (KeyError, TypeError, ValueError):
            continue
    return None


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
    models = data.get("model_remains") or []
    general = next((m for m in models if m.get("model_name") == "general"), None)
    # Fall back to the first reported model when a plan exposes no "general" pool.
    if general is None:
        general = models[0] if models else None
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


# Jina's shared token pool (Embeddings/Reranker/Reader/Search) is queried
# through the dashboard key endpoint. The host is overridable for users behind a
# mirror or proxy. Default to the mainland (.cn) dashboard mirror, matching the
# r.jinaai.cn / s.jinaai.cn service family; set hosts.jina (or
# JINA_DASHBOARD_HOST) to "embeddings-dashboard-api.jina.ai" for the intl host.
_JINA_DASHBOARD_HOST_DEFAULT = "embeddings-dashboard-api.jinaai.cn"


def _jina(cfg: dict) -> list[dict[str, Any]]:
    key = sources.vendor_key(cfg, "jina", "JINA_API_KEY")
    if not key:
        return []
    host = ((cfg.get("hosts") or {}).get("jina")
            or os.environ.get("JINA_DASHBOARD_HOST")
            or _JINA_DASHBOARD_HOST_DEFAULT)
    # The dashboard passes the key as a query parameter, not a bearer header.
    url = f"https://{host}/api/v1/api_key/user?api_key={urllib.parse.quote(key, safe='')}"
    data = _get_json(url, key)
    if not isinstance(data, dict):
        return []
    wallet = data.get("wallet") if isinstance(data.get("wallet"), dict) else data
    remaining = _first_number(wallet, "total_balance", "trial_balance", "balance", "remaining_tokens")
    total = _first_number(wallet, "total_amount", "total_tokens", "quota")
    if remaining is None:
        return []
    ring: dict[str, Any] = {
        "id": "jina-balance",
        "label": "Jina",
        "vendor": "jina",
        "kind": "balance",
        "usedPercent": None,
        "remaining": round(remaining, 2),
        "currency": "tokens",
        "accent": "teal",
    }
    if total is not None and total > 0:
        used = max(0.0, total - remaining)
        ring["usedPercent"] = clamp_pct(used / total * 100.0)
        ring["remainingPercent"] = clamp_pct(remaining / total * 100.0)
        ring["usedValue"] = round(used, 2)
        ring["totalValue"] = round(total, 2)
        ring["valueUnit"] = "tokens"
    else:
        ring["remainingPercent"] = None
    return [ring]


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
    "jina": _jina,
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
    "jina": ("Jina AI", "teal"),
}

# Vendors with no implemented live-quota route. Adding a key does not produce a
# ring, so they get an explicit "not supported yet" status instead of the
# misleading "connected, but quota unavailable" wording.
_QUOTA_UNSUPPORTED_VENDORS = {"anthropic", "xiaomi"}


def _status_ring(vendor: str, status: str) -> dict[str, Any]:
    label, _accent = _STATUS_META[vendor]
    detail = {
        "not_connected": "Connect an account or add a credential",
        "quota_unavailable": "Connected, but live quota is unavailable",
        "quota_unsupported": "Live quota not supported for this provider yet",
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
                if not sources.has_vendor_credential(cfg, name):
                    status = "not_connected"
                elif name in _QUOTA_UNSUPPORTED_VENDORS:
                    status = "quota_unsupported"
                else:
                    status = "quota_unavailable"
                rings.append(_status_ring(name, status))
    # Hide rings for vendors the user explicitly turned off.
    rings = [r for r in rings if enabled.get(r.get("vendor"), True) is not False]
    from . import config as _config
    rings.sort(key=_config.ring_sort_key(cfg))
    return rings
