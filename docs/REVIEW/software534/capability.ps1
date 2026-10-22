$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$start = [DateTime]::UtcNow.ToString('o')
$os = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$facts = [ordered]@{start_utc=$start;parent_pid=$PID;cwd=(Get-Location).Path;os=@{ProductName=$os.ProductName;EditionID=$os.EditionID;DisplayVersion=$os.DisplayVersion;CurrentBuild=$os.CurrentBuild;UBR=$os.UBR;architecture=[Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString();runtime_os=[Runtime.InteropServices.RuntimeInformation]::OSDescription};shell=$PSVersionTable;token=@{effective_admin=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);admin_sid_present=($identity.Groups.Value -contains 'S-1-5-32-544');system= $identity.IsSystem};tools=@();owned_file=$null;child=$null}
foreach ($name in @('git','gh','python','py','node','cmake','ctest','ninja','gcc','clang','cl','msbuild','dotnet','cargo','rustc','Procmon64','wpr','logman','tapectl','ingest')) {
  $found = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
  $facts.tools += @{name=$name;paths=@($found | ForEach-Object Source)}
}
$owned = Join-Path $root 'owned-capability'
New-Item -ItemType Directory -Path $owned | Out-Null
$inputPath = Join-Path $owned 'input.txt'
$renamed = Join-Path $owned 'renamed.txt'
[IO.File]::WriteAllText($inputPath, "Software534 harmless owned-file control`n", [Text.UTF8Encoding]::new($false))
$before=(Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash
$read=[IO.File]::ReadAllText($inputPath)
Move-Item -LiteralPath $inputPath -Destination $renamed
$after=(Get-FileHash -LiteralPath $renamed -Algorithm SHA256).Hash
$facts.owned_file=@{path=$renamed;bytes=(Get-Item -LiteralPath $renamed).Length;before_sha256=$before;after_sha256=$after;read=$read;rename_hash_equal=($before -eq $after)}
$psi=[Diagnostics.ProcessStartInfo]::new()
$psi.FileName=Join-Path $env:SystemRoot 'System32\cmd.exe'
$psi.Arguments='/d /c "echo software534-stdout & echo software534-stderr 1>&2 & exit /b 7"'
$psi.UseShellExecute=$false
$psi.CreateNoWindow=$true
$psi.RedirectStandardOutput=$true
$psi.RedirectStandardError=$true
$childStart=[DateTime]::UtcNow.ToString('o')
try {
 $p=[Diagnostics.Process]::new(); $p.StartInfo=$psi
 [void]$p.Start(); $childPid=$p.Id
 $done=$p.WaitForExit(10000)
 if (!$done) { $p.Kill(); $p.WaitForExit() }
 $stdout=$p.StandardOutput.ReadToEnd(); $stderr=$p.StandardError.ReadToEnd()
 [IO.File]::WriteAllText((Join-Path $root 'child.stdout.txt'),$stdout)
 [IO.File]::WriteAllText((Join-Path $root 'child.stderr.txt'),$stderr)
 $facts.child=@{exe=$psi.FileName;exe_sha256=(Get-FileHash $psi.FileName).Hash;argv=$psi.Arguments;pid=$childPid;start_utc=$childStart;end_utc=[DateTime]::UtcNow.ToString('o');completed=$done;exit=$p.ExitCode;stdout=$stdout;stderr=$stderr}
} catch { $facts.child=@{exe=$psi.FileName;argv=$psi.Arguments;start_utc=$childStart;error=$_.Exception.ToString()} }
$facts.end_utc=[DateTime]::UtcNow.ToString('o')
$facts | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $root 'capability.private.json') -Encoding utf8
$facts | ConvertTo-Json -Depth 8
