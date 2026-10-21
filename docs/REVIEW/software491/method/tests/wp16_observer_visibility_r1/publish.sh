#!/usr/bin/env bash
set -euo pipefail
pkg=tests/wp16_observer_visibility_r1
python3 -B "$pkg/selftest.py"
(cd "$pkg" && sha256sum -c SHA256SUMS)
mkdir -p /tmp/observer235
git fetch --depth=1 origin "$SOURCE_HEAD"
git archive --format=zip "$SOURCE_HEAD" "$pkg" > /tmp/observer235/wp16-observer-visibility-r1.zip
cd /tmp/observer235
sha256sum wp16-observer-visibility-r1.zip > SHA256SUMS
tag="package-235-observer-$SOURCE_HEAD"
gh release create "$tag" --repo "$GITHUB_REPOSITORY" --target "$SOURCE_HEAD" --title "Verification235 six-control observer method" --notes "Independent authoring only: six synthetic neighbours and27 detecting controls. No native calls or capture. Fixed off-card method; physical/full-package holds survive." wp16-observer-visibility-r1.zip SHA256SUMS
mkdir fetched
gh release download "$tag" --repo "$GITHUB_REPOSITORY" --dir fetched
(cd fetched && sha256sum -c SHA256SUMS)
cmp wp16-observer-visibility-r1.zip fetched/wp16-observer-visibility-r1.zip
python3 -c "import zipfile;zipfile.ZipFile('fetched/wp16-observer-visibility-r1.zip').extractall('replay')"
cd replay/tests/wp16_observer_visibility_r1
sha256sum -c SHA256SUMS
python3 -B selftest.py
