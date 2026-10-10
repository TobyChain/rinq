# 20261010 — DMG release pipeline

Status: implemented · Date: 2026-10-10

## Problem

Releases were tag-plus-source only: the Mac product had no installable
artifact, and end users had to clone the repo and run `install.sh`. Release
pushes were ad hoc (manual bump, tag, `gh release create` with typed notes),
with no single entry point enforcing tests, version monotonicity, or a
consistent commit/tag/release-notes style.

## Decision

1. Ship `RinqMenu-<version>-<arch>.dmg` as the release asset, built by
   `scripts/build-dmg.sh` (`make dist`): SwiftPM release binary assembled into
   a proper `.app` (LSUIElement, ad-hoc codesign, generated icon), plus an
   `/Applications` symlink in the DMG.
2. Make the DMG self-contained: `Contents/Resources` bundles the Python daemon
   runtime and `install-daemon.sh`. `DaemonSetup.swift` runs it on first
   launch/upgrade/repair so a DMG-only machine needs no repo checkout.
3. Ownership marker: the bundled installer writes
   `~/.rinq/libexec/rinq/.app-managed` (version); `install.sh` never does.
   Repo installs are never modified by the app; app-managed installs upgrade
   with the app.
4. `scripts/release.sh <version> "<summary>"` is the only release path:
   clean-tree/on-main guards, semver monotonicity check, tests (with an
   explicit CLT/no-XCTest tolerance), version bump from the single source
   `mac/rinq/__init__.py`, DMG build, commit `Release Rinq <v> with <summary>`
   (author per AGENTS.md, no AI trailers), annotated tag, push with tags, and
   `gh release create` attaching the DMG with generated notes in the existing
   Highlights/Changes/Install format. `--local` rehearses without git/GitHub
   side effects.
5. Ad-hoc signing only (no Developer ID, no notarization); release notes tell
   users to right-click → Open past Gatekeeper. Notarization is the upgrade
   path once a Developer ID exists.

## Alternatives considered

- Zip of the bare binary (status quo plus packaging): no `.app` structure,
  no icon, no first-run daemon bootstrap — the DMG install would still be
  incomplete without a checkout.
- App spawns the daemon as a child process instead of launchd: changes the
  daemon ownership model (dashboard/CLI would die with the app); rejected to
  keep the launchd deployment contract.
- `create-dmg` for a fancy background layout: extra dependency for cosmetics;
  `hdiutil` + symlink is enough.
- Having the app auto-upgrade repo-managed installs: the app bundle may be
  older than the repo; adopting installs silently would risk downgrades. The
  marker keeps ownership explicit.

## Consequences

- Version bumps live in one place; DMG name, Info.plist, and the marker all
  derive from `__version__`.
- DMG-installed apps upgrade their daemon on app updates; repo installs
  continue via `git pull && ./install.sh`. Switching ownership is manual
  (`rm -rf ~/.rinq/libexec`) and documented in both READMEs.
- A DMG app on a machine whose daemon was deliberately stopped will reinstall
  and restart it (fresh-install detection is "daemon not answering"); accepted
  because a running menu-bar app is useless without the daemon.
- Sandbox-style first-run tests with an overridden HOME still share the real
  `~/.rinq` config/databases because launchd does not inherit the override;
  keep such test windows short (usage events are protected by the
  `(path, byte_offset)` primary key and `event_key` dedup).
- Unsigned DMGs trigger Gatekeeper on download machines until notarization
  is added.
