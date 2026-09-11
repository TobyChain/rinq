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
}


def _has_credential(cfg: dict, vendor: str) -> bool:
    return sources.has_vendor_credential(cfg, vendor)


def public_settings(cfg: dict) -> dict[str, Any]:
    enabled = cfg.get("enabled") or {}
    keys = cfg.get("keys") or {}
    vendors = []
    for vid in cfg_mod.VENDOR_IDS:
        has = _has_credential(cfg, vid)
        vendors.append({
            "id": vid,
            "label": VENDOR_META[vid]["label"],
            "accent": VENDOR_META[vid]["accent"],
            "kind": VENDOR_META[vid]["kind"],
            # enabled when explicitly true, or implicitly when a credential exists
            "enabled": bool(enabled.get(vid, has)),
            "hasCredential": has,
            "hasKeySet": bool(keys.get(vid)),
        })
    return {
        "ringOrder": cfg.get("ringOrder", []),
        "host": cfg.get("host", "127.0.0.1"),
        "port": cfg.get("port", cfg_mod.DEFAULT_PORT),
        "vendors": vendors,
        "integrations": integrations.discover_integrations(),
    }


def apply_public_settings(cfg: dict, patch: dict) -> dict:
    """Merge a settings patch (keys, enabled, ringOrder) into cfg and persist."""
    if "keys" in patch and isinstance(patch["keys"], dict):
        keys = cfg.setdefault("keys", {})
        for vid, val in patch["keys"].items():
            if vid not in cfg_mod.VENDOR_IDS:
                continue
            val = (val or "").strip()
            if val:
                keys[vid] = val
            elif vid in keys:
                # empty string clears a user-entered key (auto-discovery may still find one)
                del keys[vid]
    if "enabled" in patch and isinstance(patch["enabled"], dict):
        enabled = cfg.setdefault("enabled", {})
        for vid, val in patch["enabled"].items():
            if vid in cfg_mod.VENDOR_IDS:
                enabled[vid] = bool(val)
    if "ringOrder" in patch and isinstance(patch["ringOrder"], list):
        valid = set(_all_ring_ids())
        cfg["ringOrder"] = [r for r in patch["ringOrder"] if r in valid]
    cfg_mod.save_config(cfg)
    return cfg


def connect_integration(integration_id: str) -> bool:
    """Start an official browser-based connection without handling secrets."""
    return integrations.open_connect_url(integration_id)


def _all_ring_ids() -> list[str]:
    value_ids = [
        "codex-5h", "codex-week", "minimax-5h", "minimax-week",
        "deepseek-balance", "openai-api", "anthropic-api",
        "moonshot-balance", "zhipu-balance", "xiaomi-balance",
    ]
    return value_ids + [f"{vendor}-status" for vendor in cfg_mod.VENDOR_IDS]
