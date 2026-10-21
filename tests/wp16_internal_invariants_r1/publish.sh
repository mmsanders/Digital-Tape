#!/usr/bin/env bash
set -euo pipefail
pkg=tests/wp16_internal_invariants_r1
python3 -B "$pkg/selftest.py"
(cd "$pkg" && sha256sum -c SHA256SUMS)
mkdir -p /tmp/internal239
git fetch --depth=1 origin "$SOURCE_HEAD"
git archive --format=zip "$SOURCE_HEAD" "$pkg" > /tmp/internal239/wp16-internal-invariants-r1.zip
cd /tmp/internal239
sha256sum wp16-internal-invariants-r1.zip > SHA256SUMS
tag="package-239-internal-$SOURCE_HEAD"
if ! gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  gh release create "$tag" --repo "$GITHUB_REPOSITORY" --target "$SOURCE_HEAD" --title "Verification239 finite INTERNAL subproof method" --notes "25 frozen challenges, source assumptions and controls. Authoring only; no actual admitted witness, global proof or integration clearance." wp16-internal-invariants-r1.zip SHA256SUMS
fi
mkdir fetched
gh release download "$tag" --repo "$GITHUB_REPOSITORY" --dir fetched
(cd fetched && sha256sum -c SHA256SUMS)
cmp wp16-internal-invariants-r1.zip fetched/wp16-internal-invariants-r1.zip
python3 -c "import zipfile;zipfile.ZipFile('fetched/wp16-internal-invariants-r1.zip').extractall('replay')"
cd replay/tests/wp16_internal_invariants_r1
sha256sum -c SHA256SUMS
python3 -B selftest.py
