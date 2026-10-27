#!/usr/bin/env bash
# Puts this project on GitHub and turns on the phone app.
# Needs the GitHub CLI (https://cli.github.com) — run `gh auth login` first.
set -euo pipefail
REPO="${1:-grandma-squad}"
cd "$(dirname "$0")"

USER=$(gh api user -q .login)
echo "Creating https://github.com/$USER/$REPO ..."
[ -d .git ] || git init -q -b main
git add -A
git commit -qm "Grandma Squad studio" || true
gh repo create "$REPO" --public --source . --remote origin --push

echo "Turning on GitHub Pages for the phone app..."
gh api -X POST "repos/$USER/$REPO/pages" -f build_type=workflow >/dev/null || \
  echo "  (Pages may already be on — check Settings → Pages → Source: GitHub Actions)"

echo
echo "Optional: paste your free Gemini key (press Enter to skip):"
for S in GEMINI_API_KEY; do
  read -r -s -p "  $S: " VAL; echo
  [ -n "$VAL" ] && gh secret set "$S" --repo "$USER/$REPO" --body "$VAL"
done

gh workflow run deploy-app.yml --repo "$USER/$REPO" || true
echo
echo "Done! Your phone app: https://$USER.github.io/$REPO/  (ready in ~2 minutes)"
echo "Open it in Safari → Share → Add to Home Screen."
