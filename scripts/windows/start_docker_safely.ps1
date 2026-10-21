#requires -Version 5.1
<#
Local workaround for inaccessible Windows AF_UNIX endpoints. This is not an
upstream Docker/Windows fix. Never removes data, changes security settings,
unregisters WSL, or restarts a healthy engine. Unknown failures fail closed.
#>
[CmdletBinding()]
param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$repairLocal = [Environment]::GetFolderPath('LocalApplicationData')
$repairLogDir = Join-Path $repairLocal 'DockerSafeStart'
$repairDockerRoot = Join-Path $repairLocal 'Docker'
$repairExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$repairCli = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$repairAllowedProcesses = @(
    $repairExe,
    'C:\Program Files\Docker\Docker\frontend\Docker Desktop.exe',
    'C:\Program Files\Docker\Docker\resources\com.docker.backend.exe',
    'C:\Program Files\Docker\Docker\resources\com.docker.build.exe'
)

function Write-RepairEvent([string]$Message) {
    $line = [DateTime]::UtcNow.ToString('o') + ' ' + $Message
    Write-Output $line
    Add-Content -LiteralPath (Join-Path $repairLogDir 'last-start.log') -Value $line -Encoding UTF8
}

function Invoke-DockerBounded([string]$Arguments, [int]$TimeoutSeconds = 8) {
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $repairCli
    $start.Arguments = $Arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    # Inspect only local Desktop, never a remote context selected by the caller.
    foreach ($key in @('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','DOCKER_API_VERSION')) {
        $start.EnvironmentVariables.Remove($key)
    }
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    try {
        [void]$process.Start()
        $output = $process.StandardOutput.ReadToEndAsync()
        $errors = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill() # Only this helper's own CLI probe, never an engine process.
            return [pscustomobject]@{ ExitCode = -1; Output = ''; Error = 'probe_timeout' }
        }
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Output = $output.Result; Error = $errors.Result }
    } finally { $process.Dispose() }
}

function Get-VerifiedDockerProcesses {
    $items = @(Get-Process -Name 'Docker Desktop','com.docker.backend','com.docker.build' -ErrorAction SilentlyContinue)
    foreach ($item in $items) {
        if ($item.Path -notin $repairAllowedProcesses) { throw 'Unverified Docker process path; refusing recovery.' }
    }
    return $items
}

function Backup-SocketDirectory([string]$Path, [string]$AllowedNames) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $folder = Get-Item -LiteralPath $Path -Force
    if (-not $folder.PSIsContainer -or $folder.FullName -ne [IO.Path]::GetFullPath($Path) -or
        ($folder.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Runtime parent is not the expected ordinary directory; refusing recovery.'
    }
    $children = @(Get-ChildItem -LiteralPath $Path -Force)
    if ($children.Count -eq 0) { return }
    foreach ($child in $children) {
        if ($child.PSIsContainer -or $child.Length -ne 0 -or $child.Name -notmatch $AllowedNames -or
            -not ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Unexpected data in runtime directory; refusing to move it.'
        }
    }
    $name = $folder.Name + '.safe-start-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $destination = Join-Path $folder.Parent.FullName $name
    if (Test-Path -LiteralPath $destination) { throw 'Recovery backup already exists.' }
    # Parent rename only: never recursively follow a reparse point or remove it.
    Rename-Item -LiteralPath $folder.FullName -NewName $name
    Write-RepairEvent ('socket_backup=' + $destination)
}

$repairMutex = New-Object Threading.Mutex($false, 'Local\DockerSafeStart')
$repairAcquired = $false
try {
    $repairAcquired = $repairMutex.WaitOne(0)
    if (-not $repairAcquired) { exit 0 }
    if (-not (Test-Path -LiteralPath $repairExe) -or -not (Test-Path -LiteralPath $repairCli)) {
        throw 'Expected Docker installation is missing.'
    }
    [void](New-Item -ItemType Directory -Path $repairLogDir -Force)
    Write-RepairEvent 'checking_engine'
    $probe = Invoke-DockerBounded '--host npipe:////./pipe/dockerDesktopLinuxEngine info --format "{{.ServerVersion}}"'
    if ($probe.ExitCode -eq 0 -and $probe.Output.Trim() -match '^\d+\.\d+\.\d+') {
        Write-RepairEvent ('healthy_engine=' + $probe.Output.Trim())
        if (-not $CheckOnly) { Start-Process -FilePath $repairExe -WindowStyle Hidden }
        exit 0
    }
    if ($CheckOnly) { throw 'Docker engine probe failed; read-only check made no recovery changes.' }

    $running = @(Get-VerifiedDockerProcesses)
    if ($running.Count -gt 0) {
        $errorPath = Join-Path $repairDockerRoot 'backend.error.json'
        if (-not (Test-Path -LiteralPath $errorPath)) { throw 'Docker may be starting; no verified socket crash. Nothing changed.' }
        $errorFile = Get-Item -LiteralPath $errorPath
        $backends = @($running | Where-Object { $_.ProcessName -eq 'com.docker.backend' })
        if ($backends.Count -eq 0) { throw 'No current backend startup can be verified; refusing recovery.' }
        $backendStarted = ($backends | Sort-Object StartTime -Descending | Select-Object -First 1).StartTime.ToUniversalTime()
        $failure = Get-Content -LiteralPath $errorPath -Raw
        if ($errorFile.LastWriteTimeUtc -lt $backendStarted -or
            $failure -notmatch 'cannot be accessed by the system' -or
            $failure -notmatch 'dockerInference|sailor-ingest\.sock|engine\.sock|userAnalyticsOtlpHttp\.sock|dockerEthernetVfkit') {
            throw 'Unrecognized or stale failure; refusing to stop Docker.'
        }
        Write-RepairEvent 'verified_socket_crash_stopping_desktop'
        $stopped = Invoke-DockerBounded 'desktop stop --force --timeout 20' 25
        if ($stopped.ExitCode -ne 0 -or @(Get-VerifiedDockerProcesses).Count -gt 0) {
            throw 'Docker has not stopped; no runtime directories were changed.'
        }
    }

    Backup-SocketDirectory (Join-Path $repairDockerRoot 'run') '^(dockerInference|dockerEthernetVfkit|userAnalyticsOtlpHttp\.sock|sailor-ingest\.sock)(\.stale.*)?$'
    Backup-SocketDirectory (Join-Path $repairLocal 'docker-secrets-engine') '^engine\.sock(\.stale.*)?$'
    Write-RepairEvent 'starting_desktop'
    Start-Process -FilePath $repairExe -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 24; $attempt++) {
        Start-Sleep -Seconds 2
        $probe = Invoke-DockerBounded '--host npipe:////./pipe/dockerDesktopLinuxEngine info --format "{{.ServerVersion}}"' 4
        if ($probe.ExitCode -eq 0 -and $probe.Output.Trim() -match '^\d+\.\d+\.\d+') {
            Write-RepairEvent ('ready_engine=' + $probe.Output.Trim())
            exit 0
        }
    }
    throw 'Docker did not become ready. No further recovery attempted; inspect Docker diagnostics.'
} catch {
    if (Test-Path -LiteralPath $repairLogDir) { Write-RepairEvent ('failed=' + $_.Exception.Message) }
    Write-Error $_
    exit 1
} finally {
    if ($repairAcquired) { $repairMutex.ReleaseMutex() }
    $repairMutex.Dispose()
}
