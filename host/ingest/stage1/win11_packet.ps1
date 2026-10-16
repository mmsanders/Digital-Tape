# INGEST-1 Stage1 native packet on a Windows 11 x64 desktop (Verification #169 / Product #435).
#
# Run in an Administrator PowerShell (Process Monitor needs it):
#
#   powershell -ExecutionPolicy Bypass -File win11_packet.ps1 `
#       -Candidate <exact candidate commit> -Kit <path to win11-kit.zip> `
#       -ShippingSha256 <sha256> -ObserveSha256 <sha256>
#
# Verification gives the four values. win11-kit.zip is the CI artifact of the same
# candidate (the exact shipping and observation ingest.exe and the profile files).
# Nothing is installed except into a scratch folder, apart from Python 3.12 if it is
# missing (then run: winget install -e --id Python.Python.3.12 , and re-run this).
# It reads and writes only under -Work and -Out; it opens no card or disk device
# itself (the observer selftest makes one deliberate, read-nothing open of
# \\.\PhysicalDrive0 to prove the observer sees forbidden opens).
#
# Output: one zip, its path and SHA-256 printed at the end. Send that zip to Verification.

param(
    [Parameter(Mandatory = $true)][string]$Candidate,
    [Parameter(Mandatory = $true)][string]$Kit,
    [Parameter(Mandatory = $true)][string]$ShippingSha256,
    [Parameter(Mandatory = $true)][string]$ObserveSha256,
    [string]$Work = "$env:SystemDrive\ingest-win11-work",
    [string]$Out = "$env:USERPROFILE\Desktop",
    # CI only: rehearse the script end to end on a non-Windows-11 host. The packet still
    # carries its real platform label (run_packet.py reads the edition), so a rehearsal
    # packet can never stand in for the Windows 11 one.
    [switch]$Rehearsal
)
$ErrorActionPreference = "Stop"

# Pinned identities. tools/check_win11_script.py proves in CI that these equal the
# committed transport files, so this script cannot silently go stale.
$ProcmonZipSha256 = "477754bf299c9e5b311c5666f7a4a48dfdb21265eaa8f0cca70ef9d9552e3a10"   # qualified by the CI packet job
$Transport = @{
    "host/ingest/stage1/run_packet.py" = "d37d63e5b13b2fb64750e0f337f468e0f569630a42f1dfac82f9a96475b6dea2"
    "host/ingest/stage1/observers.py" = "3a14d9ffdeb12fd0e59a535524ff6579051451c1a1f6d836eb4053c43f37f437"
    "host/ingest/stage1/summarize_packet.py" = "dd18e797210da43021f1bac187bfdeb7b6a5f6ae7e9ae18d3098de8f9cf79f4a"
}

function Fail($msg) { Write-Host "STOPPED: $msg" -ForegroundColor Red; exit 1 }
function Sha($path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower() }

# 1. This must be the real platform: Administrator, Windows 11 client, x64.
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Fail "open PowerShell with 'Run as administrator'" }
$os = Get-CimInstance Win32_OperatingSystem
if ($os.ProductType -ne 1 -or [int]$os.BuildNumber -lt 22000) {
    if (-not $Rehearsal) { Fail "not a Windows 11 client: $($os.Caption) build $($os.BuildNumber)" }
    Write-Host "REHEARSAL on $($os.Caption) build $($os.BuildNumber): not a Windows 11 packet"
}
if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") { Fail "not x64: $env:PROCESSOR_ARCHITECTURE" }
$free = (Get-PSDrive ($Work.Substring(0, 1))).Free
if ($free -lt 25GB) { Fail "need 25 GB free on $($Work.Substring(0, 2)) (the census writes two 4 GiB WAVs); free: $([math]::Round($free / 1GB)) GB" }
Write-Host "$($os.Caption) $($os.Version) build $($os.BuildNumber), Administrator, x64"

# Python 3.12: the py launcher (python.org) or "python" (python.org or Microsoft Store).
$pyexe = $null; $pyargs = @()
if ((Get-Command py -ErrorAction SilentlyContinue) -and ((& py -3.12 -c "print(1)" 2>$null) -eq "1")) {
    $pyexe = "py"; $pyargs = @("-3.12")
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and
          ((& python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null) -eq "3.12")) {
    $pyexe = "python"
}
if (-not $pyexe) { Fail "Python 3.12 is missing: run 'winget install -e --id Python.Python.3.12', then run this again" }
& $pyexe @pyargs -c "import sys; print('Python', sys.version, sys.executable)"

if (Test-Path $Work) { Fail "$Work already exists; remove it or pass -Work <new folder>" }
New-Item -ItemType Directory -Path $Work | Out-Null

# 2. The exact candidate's source, checked file by file.
$src = Join-Path $Work "src.zip"
Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/mmsanders/Digital-Tape/zip/$Candidate" -OutFile $src
Expand-Archive -LiteralPath $src -DestinationPath (Join-Path $Work "src")
$repo = (Get-ChildItem (Join-Path $Work "src") -Directory | Select-Object -First 1).FullName
foreach ($k in $Transport.Keys) {
    $got = Sha (Join-Path $repo $k)
    if ($got -ne $Transport[$k]) { Fail "$k is $got, expected $($Transport[$k]) (wrong candidate?)" }
}
Write-Host "candidate $Candidate transport files match"

# 3. The exact binaries.
Expand-Archive -LiteralPath $Kit -DestinationPath (Join-Path $Work "kit")
$kitDir = Join-Path $Work "kit"
$ship = Join-Path $kitDir "ingest.exe"
$obs = Join-Path $kitDir "observe\ingest.exe"
if ((Sha $ship) -ne $ShippingSha256.ToLower()) { Fail "shipping ingest.exe is $(Sha $ship), expected $ShippingSha256" }
if ((Sha $obs) -ne $ObserveSha256.ToLower()) { Fail "observation ingest.exe is $(Sha $obs), expected $ObserveSha256" }
Write-Host "binaries match: shipping $ShippingSha256, observation $ObserveSha256"

# 4. Process Monitor, pinned by hash.
$pmZip = Join-Path $Work "ProcessMonitor.zip"
Invoke-WebRequest -UseBasicParsing -Uri "https://download.sysinternals.com/files/ProcessMonitor.zip" -OutFile $pmZip
if ((Sha $pmZip) -ne $ProcmonZipSha256) {
    Fail "ProcessMonitor.zip is $(Sha $pmZip), expected $ProcmonZipSha256 (Microsoft updated it; ask Software for a re-pinned script)"
}
Expand-Archive -LiteralPath $pmZip -DestinationPath (Join-Path $Work "procmon")
$procmon = Join-Path $Work "procmon\Procmon64.exe"
$sig = Get-AuthenticodeSignature -LiteralPath $procmon
if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "O=Microsoft Corporation") {
    Fail "Procmon64.exe signature is $($sig.Status) by '$($sig.SignerCertificate.Subject)', not a valid Microsoft signature"
}

# 5. A private Python environment with the package's pinned requirements.
& $pyexe @pyargs -m venv (Join-Path $Work "venv")
$python = Join-Path $Work "venv\Scripts\python.exe"
$pkg = Join-Path $repo "tests\wp16_ingest_stage1"
& $python -m pip install --disable-pip-version-check -q -r (Join-Path $pkg "requirements.txt") procmon-parser==0.4.0
if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }

# 6. The imported package's own authentication and source fetch.
& $python -B (Join-Path $pkg "check_pins.py"); if ($LASTEXITCODE -ne 0) { Fail "check_pins.py failed" }
& $python -B (Join-Path $pkg "asset.py") --destination (Join-Path $Work "sources"); if ($LASTEXITCODE -ne 0) { Fail "asset.py failed" }

# 7. Every census case under the observer.
$packet = Join-Path $Work "packet"
$stage1 = Join-Path $repo "host\ingest\stage1"
& $python -B (Join-Path $stage1 "run_packet.py") --package $pkg --sources (Join-Path $Work "sources") `
    --observe-bin $obs --shipping-bin $ship --profile-dir (Join-Path $kitDir "profile") `
    --out $packet --work (Join-Path $Work "cases") --candidate-sha $Candidate --procmon $procmon
if ($LASTEXITCODE -ne 0) { Fail "run_packet.py failed" }
& $python -B (Join-Path $stage1 "summarize_packet.py") $packet --package $pkg

# 8. One zip to send.
$zip = Join-Path $Out "ingest-win11-packet-$($Candidate.Substring(0, 12)).zip"
# .NET's ZipFile writes zip64, so the 4 GiB census WAV and a >2 GiB packet fit
# (Compress-Archive stops at 2 GiB with "Stream was too long").
if (Test-Path $zip) { Remove-Item $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($packet, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $false)
Write-Host ""
Write-Host "PACKET: $zip"
Write-Host "SHA256: $(Sha $zip)"
Write-Host "Send this zip and its SHA256 to Verification. This run is an observation, not a PASS."
