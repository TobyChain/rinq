"""Public, key-safe settings surface for the Settings UI.

Vendors carry their discovered credential state so the UI can show which ones
are live without exposing any secrets.
"""

from __future__ import annotations

from typing import Any

from . import config as cfg_mod
from . import integrations
from . import sources

VENDOR_META = {
    "codex": {"label": "ChatGPT / Codex", "accent": "blue", "kind": "subscription"},
    "minimax": {"label": "MiniMax Coding Plan", "accent": "orange", "kind": "subscription"},
    "deepseek": {"label": "DeepSeek", "accent": "teal", "kind": "balance"},
    "openai": {"label": "OpenAI API spend", "accent": "green", "kind": "budget"},
    "anthropic": {"label": "Claude API (org)", "accent": "orange", "kind": "budget"},
    "moonshot": {"label": "Kimi (Moonshot)", "accent": "purple", "kind": "balance"},
    "zhipu": {"label": "GLM (Zhipu)", "accent": "red", "kind": "balance"},
    "xiaomi": {"label": "MiMo (Xiaomi)", "accent": "orange", "kind": "balance"},
    "jina": {"label": "Jina AI (search)", "accent": "teal", "kind": "balance"},
}


def _has_credential(cfg: dict, vendor: str) -> bool:
    return sources.has_vendor_credential(cfg, vendor)


def public_settings(cfg: dict) -> dict[str, Any]:
    keys = cfg.get("keys") or {}
    cancelled = cfg_mod.cancelled_vendors(cfg)
    vendors = []
    for vid in cfg_mod.VENDOR_IDS:
        has = _has_credential(cfg, vid)
        vendors.append({
            "id": vid,
            "label": VENDOR_META[vid]["label"],
            "accent": VENDOR_META[vid]["accent"],
            "kind": VENDOR_META[vid]["kind"],
            # Quota tracking is on while a credential exists and the user has
            # not cancelled this vendor; hasCredential tells the two apart.
            "tracking": has and vid not in cancelled,
            "hasCredential": has,
            "hasKeySet": bool(keys.get(vid)),
        })
    return {
        "ringOrder": cfg.get("ringOrder", []),
        "host": cfg.get("host", "127.0.0.1"),
        "port": cfg.get("port", cfg_mod.DEFAULT_PORT),
        "vendors": vendors,
        "integrations": integrations.discover_integrations(
            cancelled=cfg_mod.cancelled_integrations(cfg)
        ),
    }


def apply_public_settings(cfg: dict, patch: dict) -> dict:
    """Save keys, per-vendor tracking cancellations, and ring order."""
    if "keys" in patch and isinstance(patch["keys"], dict):
        keys = cfg.setdefault("keys", {})
        for vid, val in patch["keys"].items():
            if vid not in cfg_mod.VENDOR_IDS:
                continue
            val = (val or "").strip()
            if val:
                keys[vid] = val
                # Supplying a credential is an explicit opt-in: drop a stale
                # tracking cancellation so the vendor is tracked right away.
                _set_cancelled(cfg, vid, False)
            elif vid in keys:
                # empty string clears a user-entered key (auto-discovery may still find one)
                del keys[vid]
    if "tracking" in patch and isinstance(patch["tracking"], dict):
        for vid, on in patch["tracking"].items():
            if vid in cfg_mod.VENDOR_IDS and isinstance(on, bool):
                _set_cancelled(cfg, vid, not on)
    if "monitored" in patch and isinstance(patch["monitored"], dict):
        for vid, on in patch["monitored"].items():
            if vid in _integration_ids() and isinstance(on, bool):
                _set_integration_cancelled(cfg, vid, not on)
    if "ringOrder" in patch and isinstance(patch["ringOrder"], list):
        valid = set(_all_ring_ids())
        cfg["ringOrder"] = [r for r in patch["ringOrder"] if r in valid]
    cfg_mod.save_config(cfg)
    return cfg


def _set_cancelled(cfg: dict, vendor: str, cancelled: bool) -> None:
    """Add or remove one vendor in the persisted tracking cancellation list."""
    off = [vid for vid in (cfg.get("trackingOff") or []) if vid in cfg_mod.VENDOR_IDS]
    if cancelled:
        if vendor not in off:
            off.append(vendor)
    else:
        off = [vid for vid in off if vid != vendor]
    cfg["trackingOff"] = off


def _set_integration_cancelled(cfg: dict, integration: str, cancelled: bool) -> None:
    """Add or remove one IDE in the persisted monitoring cancellation list."""
    off = [vid for vid in (cfg.get("integrationOff") or []) if vid in _integration_ids()]
    if cancelled:
        if integration not in off:
            off.append(integration)
    else:
        off = [vid for vid in off if vid != integration]
    cfg["integrationOff"] = off


def _integration_ids() -> set[str]:
    return {item["id"] for item in integrations.APP_DEFINITIONS}


def connect_integration(integration_id: str) -> bool:
    """Start an official browser-based connection without handling secrets."""
    return integrations.open_connect_url(integration_id)


def _all_ring_ids() -> list[str]:
    value_ids = [
        "codex-5h", "codex-week", "minimax-5h", "minimax-week",
        "deepseek-balance", "openai-api", "anthropic-api",
        "moonshot-balance", "zhipu-5h", "zhipu-week", "zhipu-balance",
        "xiaomi-balance", "jina-balance",
    ]
    return value_ids + [f"{vendor}-status" for vendor in cfg_mod.VENDOR_IDS]
