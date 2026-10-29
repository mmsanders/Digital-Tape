$ErrorActionPreference = 'Stop'
# This job creates exactly one private VHD, then probes only its returned disk path.
# No native physical disk is selected, initialized, formatted or removed.
$root = Join-Path $env:RUNNER_TEMP 'verifier364-volume-query'
New-Item -ItemType Directory -Path $root | Out-Null
$vhd = Join-Path $root 'probe.vhd'
$script = Join-Path $root 'diskpart.txt'
@("create vdisk file=`"$vhd`" maximum=64 type=fixed", "select vdisk file=`"$vhd`"", 'attach vdisk') | Set-Content $script
diskpart /s $script | Out-File (Join-Path $root 'diskpart-create.txt')
if ($LASTEXITCODE -ne 0) { throw 'private VHD creation failed' }
try {
    $image = Get-DiskImage -ImagePath $vhd
    if (-not $image.Attached -or $image.ImagePath -ne $vhd) { throw 'wrong VHD identity' }
    $disk = $image | Get-Disk
    if (@($disk).Count -ne 1 -or $disk.IsBoot -or $disk.IsSystem -or $disk.PartitionStyle -ne 'RAW') { throw 'not the fresh VHD' }
    $disk | Initialize-Disk -PartitionStyle MBR -PassThru | New-Partition -UseMaximumSize -AssignDriveLetter | Format-Volume -FileSystem NTFS -NewFileSystemLabel 'VERIFY364' -Confirm:$false | Out-Null
    $dev = '\\.\PhysicalDrive' + $disk.Number
    $exe = Join-Path $env:GITHUB_WORKSPACE 'probe.exe'
    & $exe $dev 1> (Join-Path $root 'RESULT.json') 2> (Join-Path $root 'stderr.txt')
    $result = $LASTEXITCODE
    Get-Content (Join-Path $root 'RESULT.json')
    if ($result -ne 1) { throw "expected current-head query-omission reproduction (exit 1); got $result" }
} finally {
    @("select vdisk file=`"$vhd`"", 'detach vdisk') | Set-Content $script
    diskpart /s $script | Out-File (Join-Path $root 'diskpart-detach.txt')
}
