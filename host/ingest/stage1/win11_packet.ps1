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
    [string]$Out = "$env:USERPROFILE\Desktop"
)
$ErrorActionPreference = "Stop"

# Pinned identities. tools/check_win11_script.py proves in CI that these equal the
# committed transport files, so this script cannot silently go stale.
$ProcmonZipSha256 = "80a6442b46af762ed1432f6fec3f7e20366bed62a2522b3486503398a40a1128"
$Transport = @{
    "host/ingest/stage1/run_packet.py" = "bde40fda7f38a4ef468d6a652e1e8d44c088e8c0f809d180d164c4cbc0d38e12"
    "host/ingest/stage1/observers.py" = "7d3b0994f3449161b0b7b38d7f8f0a457977e7aabf23f6b444c3f9b6225e9da1"
    "host/ingest/stage1/summarize_packet.py" = "48c175cf962542de3a43495067aaeee48c9099098e3bdbde0bcbeb4dbfd9e1e9"
}

function Fail($msg) { Write-Host "STOPPED: $msg" -ForegroundColor Red; exit 1 }
function Sha($path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower() }

# 1. This must be the real platform: Administrator, Windows 11 client, x64.
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Fail "open PowerShell with 'Run as administrator'" }
$os = Get-CimInstance Win32_OperatingSystem
if ($os.ProductType -ne 1 -or [int]$os.BuildNumber -lt 22000) { Fail "not a Windows 11 client: $($os.Caption) build $($os.BuildNumber)" }
if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") { Fail "not x64: $env:PROCESSOR_ARCHITECTURE" }
$free = (Get-PSDrive ($Work.Substring(0, 1))).Free
if ($free -lt 25GB) { Fail "need 25 GB free on $($Work.Substring(0, 2)) (the census writes two 4 GiB WAVs); free: $([math]::Round($free / 1GB)) GB" }
Write-Host "Windows 11 $($os.Version) build $($os.BuildNumber), Administrator, x64"

$py = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $py) { Fail "Python 3.12 is missing: run 'winget install -e --id Python.Python.3.12', then run this again" }
& py -3.12 -c "import sys; print(sys.version)"
if ($LASTEXITCODE -ne 0) { Fail "Python 3.12 is missing: run 'winget install -e --id Python.Python.3.12', then run this again" }

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

# 5. A private Python environment with the package's pinned requirements.
& py -3.12 -m venv (Join-Path $Work "venv")
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
Compress-Archive -Path (Join-Path $packet "*") -DestinationPath $zip -Force
Write-Host ""
Write-Host "PACKET: $zip"
Write-Host "SHA256: $(Sha $zip)"
Write-Host "Send this zip and its SHA256 to Verification. This run is an observation, not a PASS."
