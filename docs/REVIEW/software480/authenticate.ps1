param([Parameter(Mandatory=$true)][string]$VerificationRepository)
$ErrorActionPreference = 'Stop'
$product = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$verification = (Resolve-Path $VerificationRepository).Path
function Read-Git([string]$repo, [string[]]$arguments) {
    $output = & git -C $repo @arguments
    if ($LASTEXITCODE -ne 0) { throw "git failed: $arguments" }
    return ($output -join "`n")
}
function Assert-Ancestor([string]$repo, [string]$ancestor, [string]$descendant) {
    & git -C $repo merge-base --is-ancestor $ancestor $descendant
    if ($LASTEXITCODE -ne 0) { throw "Not an ancestor: $ancestor -> $descendant" }
}
$main = '5c17314af51ac22e8729d474f2a4d2edd756daef'
$vmain = '929c02f35aed6bad05d708d33ebff0cfb35ccc37'
$heads = [ordered]@{
    '443' = '85b7c3fd0b123ae7e5d54cb9f7bb424fbc613542'
    '454' = 'b9f430c8c9b33532abf07eea0ed2653310639f2d'
    '455' = 'ecca8c1304ba9511d78791e92ed35fac494f2a27'
    '459' = '50bc4160f6da527da8c684d05264f99815aaa870'
    '469' = '1ad813d86d094a3702a03e3b2e602c221855a9ca'
}
$candidates = foreach ($number in $heads.Keys) {
    $head = $heads[$number]
    $snapshot = Get-Content -Raw (Join-Path $PSScriptRoot "pr-$number.json") | ConvertFrom-Json
    if ($snapshot.headRefOid -cne $head) { throw "PR $number pin mismatch" }
    $branchHead = Read-Git $product @('rev-parse', "origin/$(switch ($number) {
        '443' {'software/p2-wp10-subset-binding'}
        '454' {'software/p2-452-ingest-report'}
        '455' {'software/p2-452-app-shell'}
        '459' {'software/p2-457-ingest-exhaustion'}
        '469' {'software/p2-465-cards'}
    })")
    if ($branchHead -cne $head) { throw "Fetched PR $number branch mismatch" }
    $imports = (Read-Git $product @('show', "${head}:tests/IMPORTS.json") | ConvertFrom-Json).packages
    $packages = foreach ($package in $imports | Where-Object { $_.path -match 'wp15|wp10_subset|wp16_ingest' }) {
        Assert-Ancestor $verification $package.source_commit $vmain
        $imported = Read-Git $product @('rev-parse', "${head}:$($package.path)")
        $published = Read-Git $verification @('rev-parse', "$($package.source_commit):$($package.path)")
        if ($imported -cne $published -or $imported -cne $package.tree) { throw "Import mismatch: $($package.path)" }
        [ordered]@{path=$package.path; tree=$imported; publication=$package.source_commit}
    }
    $engine = Read-Git $product @('rev-parse', "${head}:engine")
    if ($engine -cne 'd96b4245e04d74078f8938744b1394c3018516f7') { throw 'Engine changed' }
    [ordered]@{
        pr=[int]$number; head=$head; tree=(Read-Git $product @('rev-parse', "${head}^{tree}"))
        engine=$engine; merge_base=(Read-Git $product @('merge-base', $main, $head))
        main_head_counts=(Read-Git $product @('rev-list','--left-right','--count',"${main}...${head}"))
        imports=@($packages)
        checks=@($snapshot.statusCheckRollup | Group-Object conclusion | ForEach-Object { [ordered]@{conclusion=$_.Name; count=$_.Count} })
    }
}
$publications = foreach ($commit in @(
    '42f169f1b5448bc646a2b181ced51c14e385017c',
    '9997bc1c388796283dc138d8bf6e6200e02cc390',
    'e1f4bd72f2a6be75cfd8ebe8edb93ed534cfca1e',
    '937dee3', '99df7f8c67627c13b33d0d55b5ba74ae2d43d699',
    'c5e28b80a0e505a295fa71daaef7a6d2c6f411c6',
    '32c6f245eaced5db063e80faf172090b2e7825f1', $vmain
)) {
    $full = Read-Git $verification @('rev-parse', $commit)
    Assert-Ancestor $verification $full $vmain
    [ordered]@{commit=$full; tree=(Read-Git $verification @('rev-parse', "${full}^{tree}")); on_verification_main=$true}
}
Assert-Ancestor $product $heads['459'] $heads['454']
Assert-Ancestor $product '6126d04050133cacb9a1960a0bc13c9ee93130e5' $heads['459']
$childPin = Read-Git $product @('rev-parse', '35b23ca:host/ingest')
$s1 = Read-Git $product @('rev-parse', "$($heads['454']):host/ingest")
if ($childPin -cne $s1) { throw 'S4 historical child source differs from S1' }
$normative = foreach ($path in @('spec/VERSION.md','spec/tapefs-v1.md','spec/engine-api.md','spec/acceptance.md','docs/WP14-CLI-CONTRACT.md','docs/WP15-APP-CONTRACT.md','docs/WP15-APP-ANNEX.md')) {
    [ordered]@{path=$path; blob=(Read-Git $product @('rev-parse', "${main}:$path"))}
}
$result = [ordered]@{
    product_main=$main; verification_main=$vmain
    scope='Git object/ancestry/import and saved GitHub check authentication only; no Product execution or independent acceptance'
    candidates=@($candidates); publications=@($publications); normative=@($normative)
    s4_child_pin_and_s1_ingest_tree=$s1
    corrected459_contains_obsolete436=$true; s1_contains_corrected459=$true
}
$json = $result | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'authentication.json'), $json + "`n")
Write-Output 'PASS: five candidate pins, relevant import trees, eight main publications, engine identity and dependency ancestry'
