param(
    [string]$GuildId
)

$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Command = "py"; Prefix = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Command = "python"; Prefix = @() }
    }
    throw "Python 3 was not found on PATH."
}

$python = Resolve-PythonCommand

if (-not $env:DISCORD_BOT_TOKEN) {
    . "$PSScriptRoot\set_discord_bot_token.ps1"
}

$installArgs = @($python.Prefix) + @(
    "$PSScriptRoot\discord_archive_setup.py",
    "--install-url"
)
if ($GuildId) {
    $installArgs += @("--guild", $GuildId)
}

Write-Host ""
Write-Host "Generating a least-privilege Discord install URL..."
$installUrl = (& $python.Command @installArgs | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($installUrl)) {
    throw "Could not generate the Discord install URL."
}

Write-Host ""
Write-Host "Opening Discord. Install 'Roanoke Archive' into the Roanoke Season 3 server."
Write-Host "The request is limited to View Channel + Read Message History."
Start-Process $installUrl

Read-Host "After Discord says the app is installed, press Enter here"

$probeArgs = @($python.Prefix) + @(
    "$PSScriptRoot\discord_archive_setup.py",
    "--probe"
)
if ($GuildId) {
    $probeArgs += @("--guild", $GuildId)
}

Write-Host ""
Write-Host "Checking authentication and read-only channel visibility..."
& $python.Command @probeArgs
exit $LASTEXITCODE
