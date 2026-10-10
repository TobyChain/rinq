#!/usr/bin/env bash
# Release pipeline: test -> bump version -> build DMG -> commit -> tag ->
# push -> GitHub release with the DMG attached.
#
# Usage:
#   scripts/release.sh <version> "<summary fragment>" [options]
#
#   <version>          semver, must be greater than the latest tag
#   <summary fragment> release title fragment, e.g. "dmg distribution";
#                      produces commit "Release Rinq <version> with <summary>"
#                      and release title "Rinq <version>"
#
# Options:
#   --local            build + verify only: no commit/tag/push/GitHub release;
#                      restores the version file afterwards
#   --notes-file FILE  use FILE as the release body instead of the generated one
#   --draft            create the GitHub release as a draft
#   --skip-tests       rehearsal only; do not use for real releases
#
# The DMG is ad-hoc signed (no Developer ID). See docs/cookbook/release.md
# for the full runbook, including token scopes and Gatekeeper notes.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
VERSION_FILE="mac/rinq/__init__.py"

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

[ "${1:-}" != "" ] && [ "${2:-}" != "" ] || usage
VERSION="$1"; SUMMARY="$2"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "bad version: $VERSION" >&2; exit 1; }
shift 2

LOCAL=0; DRAFT=0; SKIP_TESTS=0; NOTES_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --local) LOCAL=1 ;;
    --draft) DRAFT=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    --notes-file) NOTES_FILE="${2:?--notes-file needs a value}"; shift ;;
    *) echo "unknown option: $1" >&2; usage ;;
  esac
  shift
done

[ -z "$(git status --porcelain)" ] || { echo "worktree not clean; commit first" >&2; exit 1; }
[ "$(git branch --show-current)" = "main" ] || { echo "not on main" >&2; exit 1; }

LAST_TAG="$(git describe --tags --abbrev=0 2>/dev/null || true)"
if [ -n "$LAST_TAG" ]; then
  HIGHER="$(printf '%s\n' "${LAST_TAG#v}" "$VERSION" | sort -V | tail -1)"
  [ "$HIGHER" = "$VERSION" ] || { echo "version $VERSION <= latest tag $LAST_TAG" >&2; exit 1; }
fi

if [ "$LOCAL" -eq 0 ]; then
  gh auth status >/dev/null 2>&1 || { echo "gh not authenticated" >&2; exit 1; }
fi

if [ "$SKIP_TESTS" -eq 0 ]; then
  echo "==> python tests"
  make mac-test

  echo "==> swift build + tests"
  cd mac/RinqMenu
  swift build -c release
  if ! swift test 2>&1 | tee /tmp/rinq-swift-test.log; then
    # CLT-only machines have no XCTest; treat that specific failure as a skip.
    if grep -q "no such module 'XCTest'" /tmp/rinq-swift-test.log; then
      echo "warning: XCTest unavailable (Command Line Tools only); skipping swift tests" >&2
    else
      echo "swift tests failed" >&2; exit 1
    fi
  fi
  cd "$REPO"
fi

echo "==> bump version to $VERSION"
sed -i '' -E "s/^__version__ = \".*\"$/__version__ = \"$VERSION\"/" "$VERSION_FILE"

./scripts/build-dmg.sh
DMG="dist/RinqMenu-$VERSION-$(uname -m).dmg"
[ -f "$DMG" ] || { echo "DMG missing: $DMG" >&2; exit 1; }

if [ "$LOCAL" -eq 1 ]; then
  git checkout -- "$VERSION_FILE"
  echo
  echo "local build verified: $DMG"
  echo "next: install it (open dist/, drag to Applications), then re-run"
  echo "      scripts/release.sh $VERSION \"$SUMMARY\" without --local"
  exit 0
fi

if [ -n "$NOTES_FILE" ]; then
  NOTES="$(cat "$NOTES_FILE")"
else
  RANGE="${LAST_TAG:+$LAST_TAG..}HEAD"
  CHANGELOG="$(git log --oneline "$RANGE" | sed 's/^/- /')"
  NOTES="## Highlights

- **${SUMMARY}**

## Changes

${CHANGELOG}

## Install

Download \`RinqMenu-${VERSION}-arm64.dmg\`, open it, and drag Rinq into
Applications. On first launch the app installs and starts the local daemon
(needs python3) and shows quota rings once provider keys are configured in
Settings. The app is ad-hoc signed: if Gatekeeper prompts on first launch,
right-click the app and choose Open. Repo installs via \`./install.sh\` keep
working unchanged."
fi

echo "==> commit + tag"
git add "$VERSION_FILE"
git -c user.name=TobyChain -c user.email=g787796121@163.com commit -m "Release Rinq $VERSION with $SUMMARY"
git tag -a "v$VERSION" -m "Rinq $VERSION"

echo "==> push"
git push origin main --follow-tags

echo "==> github release"
DRAFT_FLAG=""
[ "$DRAFT" -eq 1 ] && DRAFT_FLAG="--draft"
gh release create "v$VERSION" "$DMG" --title "Rinq $VERSION" --notes "$NOTES" $DRAFT_FLAG
