# #451: Windows native visibility of device-open ATTEMPTS (Windows Server here:
# supplementary, never Windows 11). Each tracer records one fresh run of the same
# controls; devopen.py says, per control PID, whether a record naming the device
# was attributed to it. No security policy, audit policy or driver is changed; the
# only fixture is an attached 1 GiB VHD. The Windows 11 kit and its pins are untouched.
#   windows_device_open.ps1 -Procmon Procmon64.exe -Out DIR
param([Parameter(Mandatory)] [string] $Procmon, [Parameter(Mandatory)] [string] $Out)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force $Out | Out-Null
$Here = $PSScriptRoot
$Py = (Get-Command python).Source
function Log($s) { Write-Host "== $s ==" }
function Invoke-DiskPart([string[]] $lines) {
  $f = New-TemporaryFile; Set-Content $f $lines -Encoding ascii
  $r = diskpart.exe /s $f; Remove-Item $f; return $r
}

Log 'environment'
$os = Get-CimInstance Win32_OperatingSystem
"$($os.Caption) $($os.Version) build $($os.BuildNumber)" | Tee-Object "$Out\env.txt"
(Get-FileHash $Procmon).Hash + "  $Procmon" | Tee-Object -Append "$Out\env.txt"
(Get-AuthenticodeSignature $Procmon).Status.ToString() | Tee-Object -Append "$Out\env.txt"

Log 'fixture VHD'
$vhd = "$env:RUNNER_TEMP\devopen.vhd"
Invoke-DiskPart @("create vdisk file=`"$vhd`" maximum=1024 type=expandable", "select vdisk file=`"$vhd`"", 'attach vdisk') | Out-Null
Start-Sleep 2
$disk = (Get-DiskImage -ImagePath $vhd | Get-Disk).Number
$dev = "\\.\PhysicalDrive$disk"
"fixture: $dev" | Tee-Object -Append "$Out\env.txt"
$plain = "$env:RUNNER_TEMP\ordinary.txt"; Set-Content $plain 'ordinary file'

Log 'standard local user for the unelevated controls'
$dir = 'C:\dtdevopen'; New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item "$Here\devopen.py" $dir
icacls $dir /grant 'Users:(OI)(CI)M' | Out-Null
$pw = 'Dt!' + [guid]::NewGuid().ToString('N').Substring(0, 16)
net user dtdevopen $pw /add /y | Out-Null
$cred = New-Object PSCredential('dtdevopen', (ConvertTo-SecureString $pw -AsPlainText -Force))

function Controls($tag) {
  # Every control prints one JSON line {pid, mode, path, ok, win32}; the role is added here.
  $f = "$Out\$tag-controls.jsonl"
  Remove-Item $f -ErrorAction SilentlyContinue
  $set = @(
    @{ role = 'neg-admin-open0-transient'; mode = 'open0'; path = $dev },
    @{ role = 'neg-admin-openread'; mode = 'openread'; path = $dev },
    @{ role = 'neg-failed-not-found'; mode = 'open0'; path = '\\.\PhysicalDrive99' },
    @{ role = 'pos-ordinary-file'; mode = 'file'; path = $plain })
  foreach ($c in $set) {
    $j = & $Py -I "$Here\devopen.py" touch $c.mode $c.path | ConvertFrom-Json
    $j | Add-Member role $c.role; ($j | ConvertTo-Json -Compress) | Add-Content $f
  }
  foreach ($c in @(@{ role = 'neg-user-openread-denied'; mode = 'openread' }, @{ role = 'neg-user-open0'; mode = 'open0' })) {
    $o = "$dir\u-$tag-$($c.mode).out"
    $p = Start-Process -FilePath $Py -ArgumentList @('-I', "$dir\devopen.py", 'touch', $c.mode, $dev) -Credential $cred `
      -WorkingDirectory $dir -RedirectStandardOutput $o -RedirectStandardError "$o.err" -Wait -PassThru -LoadUserProfile
    $j = Get-Content $o | Where-Object { $_ -like '{*' } | ConvertFrom-Json
    $j | Add-Member role $c.role; ($j | ConvertTo-Json -Compress) | Add-Content $f
  }
  Get-Content $f
}

Log 'tracer 1: Process Monitor (the pinned build the Windows 11 kit uses)'
& $Py -I "$Here\devopen.py" procmon-config "$Out\procmon.pmc"
$pml = "$env:RUNNER_TEMP\devopen.pml"
Start-Process $Procmon -ArgumentList @('/AcceptEula', '/Quiet', '/Minimized', '/LoadConfig', "$Out\procmon.pmc", '/BackingFile', $pml)
& $Procmon /AcceptEula /WaitForIdle; Start-Sleep 3
Controls 'procmon'
Start-Sleep 2
& $Procmon /AcceptEula /Terminate; Start-Sleep 3
& $Procmon /AcceptEula /Quiet /Minimized /OpenLog $pml /SaveAs "$env:RUNNER_TEMP\devopen.csv" | Out-Null
Start-Sleep 2
& $Py -I "$Here\devopen.py" scan-procmon "$env:RUNNER_TEMP\devopen.csv" "$Out\procmon-controls.jsonl" $disk | Tee-Object "$Out\procmon-summary.json"

function WprRound($tag, $profileArg) {
  Log "tracer: WPR $tag"
  wpr -cancel 2>$null | Out-Null
  wpr -start $profileArg -filemode; "wpr-start $LASTEXITCODE" | Tee-Object -Append "$Out\wpr-exits.txt"
  Controls $tag
  Start-Sleep 2
  $etl = "$env:RUNNER_TEMP\$tag.etl"; $xml = "$env:RUNNER_TEMP\$tag.xml"
  wpr -stop $etl | Out-Null; "wpr-stop $tag $LASTEXITCODE" | Tee-Object -Append "$Out\wpr-exits.txt"
  tracerpt $etl -o $xml -of XML -y | Out-Null; "tracerpt $tag $LASTEXITCODE" | Tee-Object -Append "$Out\wpr-exits.txt"
  & $Py -I "$Here\devopen.py" scan-etw $xml "$Out\$tag-controls.jsonl" $disk | Tee-Object "$Out\$tag-summary.json"
  Remove-Item $etl, $xml -ErrorAction SilentlyContinue
}
WprRound 'wpr-fileio' 'FileIO'
WprRound 'wpr-handle' "$Here\devopen.wprp!DevOpen"

Log 'done'
Invoke-DiskPart @("select vdisk file=`"$vhd`"", 'detach vdisk') | Out-Null
net user dtdevopen /delete | Out-Null
