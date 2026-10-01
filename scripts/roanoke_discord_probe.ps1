param(
    [string]$GuildId
)

$ErrorActionPreference = "Stop"
$ApiBase = "https://discord.com/api/v10"
$ViewChannel = [int64]1024
$ReadMessageHistory = [int64]65536
$Administrator = [int64]8

function Read-BotToken {
    $secure = Read-Host "Paste the Roanoke Archive bot token" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        if ([string]::IsNullOrWhiteSpace($plain)) { throw "No token entered." }
        return $plain
    }
    finally {
        if ($ptr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
}

function Invoke-DiscordGet([string]$Path, [string]$Token, [string]$Label) {
    $headers = @{
        Authorization = "Bot $Token"
        "User-Agent" = "KitDiscordArchiveProbe/0.2"
    }
    try {
        return Invoke-RestMethod -Method Get -Uri "$ApiBase$Path" -Headers $headers
    }
    catch {
        $status = $null
        try { $status = [int]$_.Exception.Response.StatusCode } catch {}
        if ($status -eq 401) { throw "Discord rejected the bot token while checking $Label. Reset/copy the bot token again." }
        if ($status -eq 403) { throw "Discord denied access while checking $Label. Confirm Roanoke Archive is installed in that server." }
        if ($status) { throw "Discord returned HTTP $status while checking $Label." }
        throw
    }
}

function To-Int64($Value) {
    if ($null -eq $Value) { return [int64]0 }
    return [int64]::Parse([string]$Value)
}

function Get-BotRole($BotId, $Roles) {
    foreach ($role in $Roles) {
        if ($role.tags -and $role.tags.bot_id -and [string]$role.tags.bot_id -eq [string]$BotId) {
            return $role
        }
    }
    return $null
}

function Get-BasePermissions($GuildId, $BotRole, $Roles) {
    [int64]$permissions = 0
    foreach ($role in $Roles) {
        if ([string]$role.id -eq [string]$GuildId) {
            $permissions = $permissions -bor (To-Int64 $role.permissions)
            break
        }
    }
    if ($BotRole) {
        $permissions = $permissions -bor (To-Int64 $BotRole.permissions)
    }
    return $permissions
}

function Apply-Overwrite([int64]$Permissions, $Overwrite) {
    [int64]$deny = To-Int64 $Overwrite.deny
    [int64]$allow = To-Int64 $Overwrite.allow
    $Permissions = $Permissions -band (-bnot $deny)
    $Permissions = $Permissions -bor $allow
    return $Permissions
}

function Get-ChannelPermissions($GuildId, $BotId, $BotRole, $Roles, $Channel) {
    [int64]$permissions = Get-BasePermissions $GuildId $BotRole $Roles

    if (($permissions -band $Administrator) -ne 0) {
        return [int64]::MaxValue
    }

    $overwrites = @($Channel.permission_overwrites)

    foreach ($ow in $overwrites) {
        if ([int]$ow.type -eq 0 -and [string]$ow.id -eq [string]$GuildId) {
            $permissions = Apply-Overwrite $permissions $ow
            break
        }
    }

    if ($BotRole) {
        [int64]$roleAllow = 0
        [int64]$roleDeny = 0
        foreach ($ow in $overwrites) {
            if ([int]$ow.type -eq 0 -and [string]$ow.id -eq [string]$BotRole.id) {
                $roleAllow = $roleAllow -bor (To-Int64 $ow.allow)
                $roleDeny = $roleDeny -bor (To-Int64 $ow.deny)
            }
        }
        $permissions = $permissions -band (-bnot $roleDeny)
        $permissions = $permissions -bor $roleAllow
    }

    foreach ($ow in $overwrites) {
        if ([int]$ow.type -eq 1 -and [string]$ow.id -eq [string]$BotId) {
            $permissions = Apply-Overwrite $permissions $ow
            break
        }
    }

    return $permissions
}

if (-not $GuildId) {
    $GuildId = (Read-Host "Paste the Roanoke Season 3 server ID").Trim()
}
if ([string]::IsNullOrWhiteSpace($GuildId) -or $GuildId -notmatch '^\d{15,22}$') {
    throw "That does not look like a Discord server ID."
}

$token = Read-BotToken
try {
    Write-Host ""
    Write-Host "Checking bot authentication..."
    $bot = Invoke-DiscordGet "/users/@me" $token "bot authentication"

    Write-Host "Checking Roanoke server access..."
    $guild = Invoke-DiscordGet "/guilds/$GuildId" $token "the Roanoke server"

    Write-Host "Reading role permissions..."
    $roles = @(Invoke-DiscordGet "/guilds/$GuildId/roles" $token "server roles")
    $botRole = Get-BotRole $bot.id $roles
    if (-not $botRole) {
        throw "Could not find the managed Roanoke Archive role for this bot."
    }

    Write-Host "Reading channel metadata..."
    $channels = @(Invoke-DiscordGet "/guilds/$GuildId/channels" $token "server channels")

    [int64]$base = Get-BasePermissions $GuildId $botRole $roles

    Write-Host ""
    Write-Host ("Bot:    {0}" -f $bot.username)
    Write-Host ("Server: {0}" -f $guild.name)
    Write-Host ("Role:   {0}" -f $botRole.name)
    Write-Host ""

    if (($base -band $Administrator) -ne 0) {
        Write-Warning "The bot currently has Administrator. Remove Administrator before archival use."
    }

    $categories = @{}
    foreach ($channel in $channels) {
        if ([int]$channel.type -eq 4) {
            $categories[[string]$channel.id] = [string]$channel.name
        }
    }

    $rows = @()
    foreach ($channel in $channels) {
        if (@(0,5) -notcontains [int]$channel.type) { continue }

        [int64]$perms = Get-ChannelPermissions $GuildId $bot.id $botRole $roles $channel
        $canView = ($perms -band $ViewChannel) -ne 0
        $canHistory = ($perms -band $ReadMessageHistory) -ne 0

        if ($canView -and $canHistory) { $status = "OK" }
        elseif (-not $canView -and -not $canHistory) { $status = "NO_VIEW+NO_HISTORY" }
        elseif (-not $canView) { $status = "NO_VIEW" }
        else { $status = "NO_HISTORY" }

        $category = ""
        if ($channel.parent_id -and $categories.ContainsKey([string]$channel.parent_id)) {
            $category = $categories[[string]$channel.parent_id]
        }

        $rows += [pscustomobject]@{
            Status = $status
            Category = $category
            Channel = [string]$channel.name
            ChannelId = [string]$channel.id
            Position = [int]$channel.position
        }
    }

    $rows = $rows | Sort-Object Position, Category, Channel

    Write-Host "Channel access:"
    $rows | Select-Object Status, Category, Channel | Format-Table -AutoSize

    $ok = @($rows | Where-Object Status -eq "OK").Count
    Write-Host ("Readable history: {0}/{1} text channels." -f $ok, $rows.Count)

    if (($base -band $Administrator) -ne 0) { exit 3 }
    if ($ok -eq 0) { exit 2 }
    exit 0
}
finally {
    Remove-Variable token -ErrorAction SilentlyContinue
}
