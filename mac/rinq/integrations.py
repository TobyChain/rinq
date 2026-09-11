"""Discover local coding IDEs and their account/quota capabilities.

This module intentionally reads metadata only. It never reads browser cookies,
encrypted credential values, prompts, or model responses.
"""

from __future__ import annotations

import json
import plistlib
import re
import subprocess
from pathlib import Path
from typing import Any


APP_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "codex",
        "label": "Codex / ChatGPT",
        "vendor": "codex",
        "app_names": ("Codex.app", "ChatGPT.app"),
        "presence_paths": (".codex",),
        "process_names": ("Codex", "ChatGPT"),
        "connect_url": "https://chatgpt.com/",
        "usage_paths": (".codex/sessions",),
        "usage_support": "structured",
        "quota_support": "verified",
    },
    {
        "id": "claude-code",
        "label": "Claude Code",
        "vendor": "anthropic",
        "app_names": ("Claude.app", "Claude Code.app"),
        "presence_paths": (".claude/projects", ".claude/settings.json", ".claude.json"),
        "process_names": ("claude",),
        "connect_url": "https://claude.ai/",
        "usage_paths": (".claude/projects",),
        "usage_support": "structured",
        "quota_support": "org_only",
    },
    {
        "id": "gemini-cli",
        "label": "Gemini CLI / Code Assist",
        "vendor": "google",
        "app_names": (),
        "presence_paths": (".gemini",),
        "process_names": ("gemini",),
        "connect_url": "https://developers.google.com/gemini-code-assist",
        "usage_support": "cc_switch_or_provider",
        "quota_support": "plan_only",
    },
    {
        "id": "github-copilot",
        "label": "GitHub Copilot",
        "vendor": "github",
        "app_names": (),
        "presence_paths": ("Library/Application Support/Code/User/globalStorage/github.copilot-chat",),
        "presence_globs": (".vscode/extensions/github.copilot-*",),
        "process_names": (),
        "connect_url": "https://github.com/settings/copilot",
        "usage_support": "extension_local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "cursor",
        "label": "Cursor",
        "vendor": "cursor",
        "app_names": ("Cursor.app",),
        "presence_paths": ("Library/Application Support/Cursor",),
        "process_names": ("Cursor",),
        "connect_url": "https://www.cursor.com/settings",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "windsurf",
        "label": "Windsurf",
        "vendor": "windsurf",
        "app_names": ("Windsurf.app",),
        "presence_paths": ("Library/Application Support/Windsurf",),
        "process_names": ("Windsurf",),
        "connect_url": "https://windsurf.com/subscription",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "zed",
        "label": "Zed",
        "vendor": "zed",
        "app_names": ("Zed.app",),
        "presence_paths": ("Library/Application Support/Zed",),
        "process_names": ("Zed",),
        "connect_url": "https://zed.dev/account",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "cline",
        "label": "Cline",
        "vendor": "cline",
        "app_names": (),
        "presence_paths": ("Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev",),
        "presence_globs": (".vscode/extensions/saoudrizwan.claude-dev-*",),
        "process_names": (),
        "connect_url": "https://app.cline.bot/",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "roo-code",
        "label": "Roo Code",
        "vendor": "roo-code",
        "app_names": (),
        "presence_paths": ("Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline",),
        "presence_globs": (".vscode/extensions/rooveterinaryinc.roo-cline-*",),
        "process_names": (),
        "connect_url": "https://roocode.com/",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "kilo-code",
        "label": "Kilo Code",
        "vendor": "kilo-code",
        "app_names": (),
        "presence_paths": ("Library/Application Support/Code/User/globalStorage/kilocode.kilo-code",),
        "presence_globs": (".vscode/extensions/kilocode.kilo-code-*",),
        "process_names": (),
        "connect_url": "https://app.kilo.ai/",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "opencode",
        "label": "OpenCode",
        "vendor": "opencode",
        "app_names": (),
        "presence_paths": (".config/opencode", ".opencode"),
        "process_names": ("opencode",),
        "connect_url": "https://opencode.ai/",
        "usage_support": "cc_switch_or_provider",
        "quota_support": "provider_dependent",
    },
    {
        "id": "qwen-code",
        "label": "Qwen Code",
        "vendor": "qwen",
        "app_names": (),
        "presence_paths": (".qwen",),
        "process_names": ("qwen",),
        "connect_url": "https://qwenlm.github.io/qwen-code-docs/",
        "usage_support": "local_unverified",
        "quota_support": "provider_dependent",
    },
    {
        "id": "kimi-code",
        "label": "Kimi Code",
        "vendor": "moonshot",
        "app_names": (),
        "presence_paths": (".kimi",),
        "process_names": ("kimi",),
        "connect_url": "https://www.kimi.com/code",
        "usage_support": "local_unverified",
        "quota_support": "plan_only",
    },
    {
        "id": "zcode",
        "label": "ZCode",
        "vendor": "zhipu",
        "app_names": ("ZCode.app",),
        "bundle_id": "dev.zcode.app",
        "process_names": ("ZCode",),
        "connect_url": "https://zcode.z.ai/en/docs/configuration",
        "usage_paths": (".zcode/cli/log",),
        "usage_support": "structured",
        "quota_support": "plan_only",
    },
    {
        "id": "mimo",
        "label": "MiMo Code / Desktop",
        "vendor": "xiaomi",
        "app_names": ("MiMo.app", "Mimo.app", "MimoAgent.app", "MiMo Code.app"),
        "bundle_id": None,
        "process_names": ("MiMo", "Mimo", "MimoAgent"),
        "connect_url": "https://mimo.mi.com/docs/zh-CN/tokenplan/integration/mimo-code",
        "usage_support": "provider_dependent",
        "quota_support": "plan_only",
    },
    {
        "id": "trae-cn",
        "label": "Trae CN",
        "vendor": "trae",
        "app_names": ("Trae CN.app", "Trae.app"),
        "bundle_id": "cn.trae.app",
        "process_names": ("Trae CN",),
        "connect_url": "https://www.trae.ai/",
        "usage_paths": (".trae/cli/sessions",),
        "usage_support": "traex_separate",
        "quota_support": "plan_only",
    },
)


def _app_dirs() -> tuple[Path, ...]:
    return (Path("/Applications"), Path.home() / "Applications")


def _find_app(definition: dict[str, Any], app_dirs: tuple[Path, ...]) -> Path | None:
    for directory in app_dirs:
        for name in definition["app_names"]:
            path = directory / name
            if path.is_dir():
                return path
    return None


def _find_presence(definition: dict[str, Any], home: Path, app_dirs: tuple[Path, ...]) -> Path | None:
    app = _find_app(definition, app_dirs)
    if app:
        return app
    for relative in definition.get("presence_paths", ()):
        path = home / relative
        if path.exists():
            return path
    for pattern in definition.get("presence_globs", ()):
        match = next(home.glob(pattern), None)
        if match:
            return match
    return None


def _has_usage_path(definition: dict[str, Any], home: Path) -> bool:
    return any((home / relative).is_dir() for relative in definition.get("usage_paths", ()))


def _bundle_metadata(app: Path) -> tuple[str | None, str | None]:
    plist = app / "Contents" / "Info.plist"
    try:
        with plist.open("rb") as stream:
            data = plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None, None
    bundle_id = data.get("CFBundleIdentifier")
    version = data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
    return (str(bundle_id) if bundle_id else None, str(version) if version else None)


def _running_processes() -> str:
    try:
        result = subprocess.run(
            ["ps", "-axo", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout


def _is_running(definition: dict[str, Any], process_text: str) -> bool:
    lowered = process_text.lower()
    for name in definition.get("process_names", ()):
        pattern = rf"(?:^|/){re.escape(name.lower())}(?:[ .]|$)"
        if any(re.search(pattern, line) for line in lowered.splitlines()):
            return True
    return False


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _zcode_state(home: Path) -> dict[str, Any]:
    root = home / ".zcode" / "v2"
    setting = _read_json(root / "setting.json") or {}
    cache = _read_json(root / "coding-plan-cache.json") or {}
    modes = setting.get("modelProviderFamilyModes") or {}
    selected = setting.get("modelProviderFamilySelectedKeys") or {}
    items = ((cache.get("entryStatus") or {}).get("items") or {})

    auth_mode = modes.get("zai")
    credentials_path = root / "credentials.json"
    if auth_mode == "oauth" and credentials_path.is_file():
        auth_state, auth_method = "connected", "oauth"
    elif auth_mode == "oauth":
        auth_state, auth_method = "configured", "oauth"
    elif selected.get("zai"):
        auth_state, auth_method = "configured", "api_key"
    else:
        auth_state, auth_method = "not_connected", "none"

    statuses = [item.get("status") for item in items.values() if isinstance(item, dict)]
    if "available" in statuses:
        plan_state = "available"
    elif any(status == "unavailable" for status in statuses):
        plan_state = "unavailable"
    else:
        plan_state = "unknown"
    reasons = [
        item.get("reason")
        for item in items.values()
        if isinstance(item, dict) and item.get("reason")
    ]
    usage_available = any((home / ".zcode" / "cli" / "log").glob("*.jsonl"))
    return {
        "authMethod": auth_method,
        "authState": auth_state,
        "planState": plan_state,
        "planReasons": reasons,
        # An active plan proves entitlement only; it does not prove that a
        # used/remaining quota value was retrieved.
        "quotaState": "unknown",
        "usageAvailable": usage_available,
    }


def _integration(definition: dict[str, Any], app_dirs: tuple[Path, ...], home: Path, process_text: str) -> dict[str, Any]:
    app = _find_app(definition, app_dirs)
    presence = app or next(
        (home / relative for relative in definition.get("presence_paths", ()) if (home / relative).exists()),
        None,
    )
    bundle_id = None
    version = None
    if app:
        bundle_id, version = _bundle_metadata(app)
    state = _zcode_state(home) if definition["id"] == "zcode" else {
        "authMethod": "unknown",
        "authState": "unknown",
        "planState": "unknown",
        "planReasons": [],
        "quotaState": "unknown",
        "usageAvailable": False,
    }
    return {
        "id": definition["id"],
        "label": definition["label"],
        "vendor": definition["vendor"],
        "installed": app is not None,
        "configured": presence is not None,
        "running": _is_running(definition, process_text),
        "version": version,
        "bundleId": bundle_id or definition.get("bundle_id"),
        "appPath": str(app) if app else None,
        "usageAvailable": bool(state["usageAvailable"] or _has_usage_path(definition, home)),
        "usageAdapter": definition["id"] if (state["usageAvailable"] or _has_usage_path(definition, home)) else None,
        "usageSupport": definition.get("usage_support", "none"),
        "quotaSupport": definition.get("quota_support", "unavailable"),
        "authMethod": state["authMethod"],
        "authState": state["authState"],
        "planState": state["planState"],
        "planReasons": state["planReasons"],
        "quotaState": state["quotaState"],
        "connectURL": definition["connect_url"],
    }


def discover_integrations(
    *,
    home: Path | None = None,
    app_dirs: tuple[Path, ...] | None = None,
    process_text: str | None = None,
    include_undetected: bool = False,
) -> list[dict[str, Any]]:
    """Return local IDE metadata without exposing account secrets."""
    home = home or Path.home()
    app_dirs = app_dirs or _app_dirs()
    process_text = _running_processes() if process_text is None else process_text
    result = [_integration(item, app_dirs, home, process_text) for item in APP_DEFINITIONS]
    if include_undetected:
        return result
    return [
        item for item in result
        if item["installed"] or item["configured"] or item["running"] or item["usageAvailable"]
    ]


def open_connect_url(integration_id: str) -> bool:
    """Open a vendor's official account connection page."""
    definition = next((item for item in APP_DEFINITIONS if item["id"] == integration_id), None)
    if not definition:
        return False
    try:
        subprocess.Popen(
            ["/usr/bin/open", definition["connect_url"]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True
