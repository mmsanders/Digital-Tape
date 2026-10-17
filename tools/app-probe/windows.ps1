# APP-1 capability probes on hosted Windows (#444). Windows Server here is
# supplementary: it is not Windows 11. The runner account is an elevated
# administrator; "unelevated" steps run as a standard local user created for
# this job. Fixtures are two 8 GiB expandable VHDs attached by diskpart and
# provisioned through tapectl-test with injected "is a card" facts.
#   windows.ps1 -TapectlTest PATH -Out DIR
param([Parameter(Mandatory)] [string] $TapectlTest, [Parameter(Mandatory)] [string] $Out)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force $Out | Out-Null
$Here = $PSScriptRoot
$Py = (Get-Command python).Source
function Log($s) { Write-Host "== $s =="; Add-Content "$Out\steps.txt" "$(Get-Date -Format o) $s" }
function Probe { & $Py -I "$Here\probe.py" @args }

Log 'environment'
$os = Get-CimInstance Win32_OperatingSystem
"$($os.Caption) $($os.Version) build $($os.BuildNumber)" | Tee-Object "$Out\env.txt"
$uac = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
"EnableLUA=$($uac.EnableLUA) ConsentPromptBehaviorAdmin=$($uac.ConsentPromptBehaviorAdmin) PromptOnSecureDesktop=$($uac.PromptOnSecureDesktop) FilterAdministratorToken=$($uac.FilterAdministratorToken)" | Tee-Object -Append "$Out\env.txt"
whoami /groups | Select-String 'Mandatory Label' | Tee-Object -Append "$Out\env.txt"
(Get-Service seclogon | Select Name,Status,StartType | Out-String).Trim() | Tee-Object -Append "$Out\env.txt"
Probe env | Tee-Object "$Out\env.jsonl"

function Invoke-DiskPart([string[]] $lines) {
  $f = New-TemporaryFile; Set-Content $f $lines -Encoding ascii
  $r = diskpart.exe /s $f; Remove-Item $f; return $r
}
function Attach($vhd) {
  Invoke-DiskPart @("select vdisk file=`"$vhd`"", 'attach vdisk') | Out-Null
  Start-Sleep 2
  return '\\.\PhysicalDrive' + (Get-DiskImage -ImagePath $vhd | Get-Disk).Number
}
function Detach($vhd) { Invoke-DiskPart @("select vdisk file=`"$vhd`"", 'detach vdisk') | Out-Null }
function Provision($dev, $label, $uuid) {
  $size = (& $TapectlTest probe $dev | Select-String '^bytes=').ToString().Substring(6)
  Set-Content "$Out\facts" @('whole=1', 'removable=1', 'sd_bus=0', "bytes=$size", 'holds_os=0', 'layout_ok=0') -Encoding ascii
  $env:TAPECTL_TEST_FACTS = "$Out\facts"
  & $TapectlTest provision $dev --label $label --erase $dev --uuid $uuid --epoch 1760659200
  Remove-Item Env:TAPECTL_TEST_FACTS
}

Log 'fixtures'
$VA = "$env:RUNNER_TEMP\A.vhd"; $VB = "$env:RUNNER_TEMP\B.vhd"
foreach ($v in $VA, $VB) { Invoke-DiskPart @("create vdisk file=`"$v`" maximum=8192 type=expandable") | Out-Null }
$A = Attach $VA; Provision $A probeA aaaaaaaa000000000000000000000001; Detach $VA
$B = Attach $VB; Provision $B probeB bbbbbbbb000000000000000000000002; Detach $VB
$A = Attach $VA; Start-Sleep 3
"A attached as $A"; Get-Disk | Select Number,BusType,Size,PartitionStyle,IsSystem,IsBoot | Format-Table | Out-String | Write-Host

Log "F1 unelevated: a standard local user"
$dir = 'C:\dtprobe'; New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item "$Here\probe.py", $TapectlTest $dir
icacls $dir /grant 'Users:(OI)(CI)M' | Out-Null
$pw = 'Dt!' + [guid]::NewGuid().ToString('N').Substring(0, 16)
net user dtprobe $pw /add /y | Out-Null
$cred = New-Object PSCredential('dtprobe', (ConvertTo-SecureString $pw -AsPlainText -Force))
$tt = Join-Path $dir (Split-Path $TapectlTest -Leaf)
function AsUser($name, [string[]] $argv, $exe = $Py) {
  try {
    $p = Start-Process -FilePath $exe -ArgumentList $argv -Credential $cred -WorkingDirectory $dir `
      -RedirectStandardOutput "$dir\$name.out" -RedirectStandardError "$dir\$name.err" -Wait -PassThru -LoadUserProfile
    "exit $($p.ExitCode)" | Add-Content "$dir\$name.err"
  } catch { "Start-Process failed: $_" | Tee-Object "$dir\$name.err" }
  Copy-Item "$dir\$name.out", "$dir\$name.err" $Out -ErrorAction SilentlyContinue
  Get-Content "$dir\$name.out", "$dir\$name.err" -ErrorAction SilentlyContinue
}
AsUser 'f1-user-env' @('-I', "$dir\probe.py", 'env')
AsUser 'f1-whoami' @('/user', '/groups') 'whoami.exe'
AsUser 'f1-unelevated' @('-I', "$dir\probe.py", 'read-facts', $A)
AsUser 'f1-tapectl-probe-unelevated' @('probe', $A) $tt
Log 'F1 elevated control'
Probe read-facts $A | Tee-Object "$Out\f1-elevated.jsonl" | Select-String '"probe": "(open|read-lba0)"'
& $TapectlTest probe $A | Tee-Object "$Out\f1-tapectl-probe-elevated.txt"

Log 'F2 elevated one open across the provision/load/verify write pattern'
Probe one-open $A | Tee-Object "$Out\f2-one-open.jsonl"
$env:TAPECTL_TEST_FACTS = "$Out\facts"; & $TapectlTest verify $A 2>&1 | Tee-Object "$Out\f2-verify.txt"; Remove-Item Env:TAPECTL_TEST_FACTS

function HoldCase($name, $secs, [scriptblock] $action) {
  Log "F3 $name"
  $j = Start-Process -FilePath $Py -ArgumentList @('-I', "$Here\probe.py", 'hold', $A, $secs) `
    -RedirectStandardOutput "$Out\f3-$name.jsonl" -RedirectStandardError "$Out\f3-$name.err" -PassThru -NoNewWindow
  Start-Sleep 3; & $action; $j.WaitForExit()
  Get-Content "$Out\f3-$name.jsonl", "$Out\f3-$name.err"
}
HoldCase 'no-change' 12 { }
HoldCase 'remove-reinsert' 18 {
  Add-Content "$Out\f3-events.txt" "detach $A"; Detach $VA; Start-Sleep 3
  $script:A2 = Attach $VA; Add-Content "$Out\f3-events.txt" "reattach A as $script:A2"
  Start-Sleep 3; Probe sig $script:A2 | Tee-Object -Append "$Out\f3-events.txt"
}
$A = $A2
HoldCase 'equal-size-swap' 15 {
  Add-Content "$Out\f3-events.txt" "detach $A, attach B"; Detach $VA; Start-Sleep 1
  $script:B = Attach $VB; Add-Content "$Out\f3-events.txt" "B attached as $script:B"
  Start-Sleep 3; Probe sig $script:B | Tee-Object -Append "$Out\f3-events.txt"
}
Get-Content "$Out\f3-events.txt"
Log 'F3 identity fields an app could compare (A vs B)'
$A = Attach $VA
foreach ($d in $A, $B) {
  $n = $d.Substring(17)
  Get-Disk -Number $n | Select Number,UniqueId,Guid,Signature,SerialNumber,Size,BusType,FriendlyName,Location |
    ConvertTo-Json -Compress | Tee-Object -Append "$Out\f3-identity.jsonl"
}

Log 'G1 runtime observation: WPR FileIO on a control that opens a disk and one that does not'
wpr -start FileIO -filemode; "wpr-start $LASTEXITCODE" | Tee-Object "$Out\g1-exits.txt"
Probe touch $A | Tee-Object "$Out\g1-negative.jsonl"
Probe touch $VA | Tee-Object "$Out\g1-positive.jsonl"
Start-Sleep 2
wpr -stop "$Out\g1.etl" | Out-Null; "wpr-stop $LASTEXITCODE" | Tee-Object -Append "$Out\g1-exits.txt"
tracerpt "$Out\g1.etl" -o "$Out\g1.xml" -of XML -y | Out-Null; "tracerpt $LASTEXITCODE" | Tee-Object -Append "$Out\g1-exits.txt"
$neg = (Get-Content "$Out\g1-negative.jsonl" | ConvertFrom-Json).pid
$pos = (Get-Content "$Out\g1-positive.jsonl" | ConvertFrom-Json).pid
& $Py -I "$Here\g1_etw.py" "$Out\g1.xml" $neg $pos | Tee-Object "$Out\g1-summary.json"
Remove-Item "$Out\g1.etl", "$Out\g1.xml" -ErrorAction SilentlyContinue

Log 'G1 runtime observation, second tracer: Microsoft-Windows-Kernel-File (FILENAME|CREATE|CREATE_NEW_FILE)'
logman create trace dtkf -p Microsoft-Windows-Kernel-File 0x1090 0x5 -o "$Out\g1kf.etl" -ets | Out-Null; "logman-start $LASTEXITCODE" | Tee-Object -Append "$Out\g1-exits.txt"
Probe touch $A | Tee-Object "$Out\g1kf-negative.jsonl"
Probe touch $VA | Tee-Object "$Out\g1kf-positive.jsonl"
Start-Sleep 2
logman stop dtkf -ets | Out-Null; "logman-stop $LASTEXITCODE" | Tee-Object -Append "$Out\g1-exits.txt"
tracerpt "$Out\g1kf.etl" -o "$Out\g1kf.xml" -of XML -y | Out-Null; "tracerpt-kf $LASTEXITCODE" | Tee-Object -Append "$Out\g1-exits.txt"
$neg = (Get-Content "$Out\g1kf-negative.jsonl" | ConvertFrom-Json).pid
$pos = (Get-Content "$Out\g1kf-positive.jsonl" | ConvertFrom-Json).pid
& $Py -I "$Here\g1_etw.py" "$Out\g1kf.xml" $neg $pos | Tee-Object "$Out\g1kf-summary.json"
Remove-Item "$Out\g1kf.etl", "$Out\g1kf.xml" -ErrorAction SilentlyContinue

Log 'done'
Detach $VA; Detach $VB
net user dtprobe /delete | Out-Null
