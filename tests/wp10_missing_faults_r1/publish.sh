#!/usr/bin/env bash
set -euo pipefail
pkg=tests/wp10_missing_faults_r1
python3 -B "$pkg/selftest.py"
(cd "$pkg" && sha256sum -c SHA256SUMS)
mkdir -p /tmp/fault241
git fetch --depth=1 origin "$SOURCE_HEAD"
git archive --format=zip "$SOURCE_HEAD" "$pkg" > /tmp/fault241/wp10-missing-faults-r1.zip
cd /tmp/fault241
sha256sum wp10-missing-faults-r1.zip > SHA256SUMS
tag="package-241-fault-$SOURCE_HEAD"
if ! gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  gh release create "$tag" --repo "$GITHUB_REPOSITORY" --target "$SOURCE_HEAD" --title "Verification241 costed missing-fault schedule" --notes "25 new operation-relative fault coordinates, retained baseline/history and budget controls. Authoring only; no new executed coverage or integration clearance." wp10-missing-faults-r1.zip SHA256SUMS
fi
mkdir fetched
gh release download "$tag" --repo "$GITHUB_REPOSITORY" --dir fetched
(cd fetched && sha256sum -c SHA256SUMS)
cmp wp10-missing-faults-r1.zip fetched/wp10-missing-faults-r1.zip
python3 -c "import zipfile;zipfile.ZipFile('fetched/wp10-missing-faults-r1.zip').extractall('replay')"
cd replay/tests/wp10_missing_faults_r1
sha256sum -c SHA256SUMS
python3 -B selftest.py
