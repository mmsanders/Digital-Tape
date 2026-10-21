#!/usr/bin/env bash
set -euo pipefail
pkg=tests/wp16_join_boundary_r1
python3 -B "$pkg/selftest.py"
(cd "$pkg" && sha256sum -c SHA256SUMS)
mkdir -p /tmp/boundary240
git fetch --depth=1 origin "$SOURCE_HEAD"
git archive --format=zip "$SOURCE_HEAD" "$pkg" > /tmp/boundary240/wp16-join-boundary-r1.zip
cd /tmp/boundary240
sha256sum wp16-join-boundary-r1.zip > SHA256SUMS
tag="package-240-boundary-$SOURCE_HEAD"
if ! gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  gh release create "$tag" --repo "$GITHUB_REPOSITORY" --target "$SOURCE_HEAD" --title "Verification240 fixed join-boundary method" --notes "18 fixed admitted PCM WAVE families and independent reference facts. Authoring only; no actual production witness or global peak theorem." wp16-join-boundary-r1.zip SHA256SUMS
fi
mkdir fetched
gh release download "$tag" --repo "$GITHUB_REPOSITORY" --dir fetched
(cd fetched && sha256sum -c SHA256SUMS)
cmp wp16-join-boundary-r1.zip fetched/wp16-join-boundary-r1.zip
python3 -c "import zipfile;zipfile.ZipFile('fetched/wp16-join-boundary-r1.zip').extractall('replay')"
cd replay/tests/wp16_join_boundary_r1
sha256sum -c SHA256SUMS
python3 -B selftest.py
