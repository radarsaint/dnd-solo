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

function Invoke-DiscordGet([string]$Path, [string]$Token) {
    $headers = @{
        Authorization = "Bot $Token"
        "User-Agent" = "KitDiscordArchiveProbe/0.1"
    }
    try {
        return Invoke-RestMethod -Method Get -Uri "$ApiBase$Path" -Headers $headers
    }
    catch {
        $status = $null
        try { $status = [int]$_.Exception.Response.StatusCode } catch {}
        if ($status -eq 401) { throw "Discord rejected the bot token. Reset/copy it again in the Developer Portal." }
        if ($status -eq 403) { throw "Discord denied access. Check that the bot is installed in the Roanoke server." }
        throw
    }
}

function To-Int64($Value) {
    if ($null -eq $Value) { return [int64]0 }
    return [int64]::Parse([string]$Value)
}

function Get-BasePermissions($GuildId, $Member, $Roles) {
    $permissions = [int64]0
    foreach ($role in $Roles) {
        if ([string]$role.id -eq [string]$GuildId) {
            $permissions = $permissions -bor (To-Int64 $role.permissions)
            break
        }
    }
    foreach ($roleId in @($Member.roles)) {
        foreach ($role in $Roles) {
            if ([string]$role.id -eq [string]$roleId) {
                $permissions = $permissions -bor (To-Int64 $role.permissions)
                break
            }
        }
    }
    return $permissions
}

function Apply-Overwrite([int64]$Permissions, $Overwrite) {
    $deny = To-Int64 $Overwrite.deny
    $allow = To-Int64 $Overwrite.allow
    $Permissions = $Permissions -band (-bnot $deny)
    $Permissions = $Permissions -bor $allow
    return $Permissions
}

function Get-ChannelPermissions($GuildId, $BotId, $Member, $Roles, $Channel) {
    [int64]$permissions = Get-BasePermissions $GuildId $Member $Roles

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

    [int64]$roleAllow = 0
    [int64]$roleDeny = 0
    $memberRoles = @($Member.roles | ForEach-Object { [string]$_ })
    foreach ($ow in $overwrites) {
        if ([int]$ow.type -eq 0 -and $memberRoles -contains [string]$ow.id) {
            $roleAllow = $roleAllow -bor (To-Int64 $ow.allow)
            $roleDeny = $roleDeny -bor (To-Int64 $ow.deny)
        }
    }
    $permissions = $permissions -band (-bnot $roleDeny)
    $permissions = $permissions -bor $roleAllow

    foreach ($ow in $overwrites) {
        if ([int]$ow.type -eq 1 -and [string]$ow.id -eq [string]$BotId) {
            $permissions = Apply-Overwrite $permissions $ow
            break
        }
    }

    return $permissions
}

$token = Read-BotToken
try {
    $bot = Invoke-DiscordGet "/users/@me" $token
    $guilds = @(Invoke-DiscordGet "/users/@me/guilds" $token)

    if ($guilds.Count -eq 0) {
        throw "The bot is authenticated but is not installed in any server."
    }

    if (-not $GuildId) {
        if ($guilds.Count -eq 1) {
            $GuildId = [string]$guilds[0].id
        }
        else {
            Write-Host ""
            Write-Host "The bot is installed in multiple servers:"
            for ($i = 0; $i -lt $guilds.Count; $i++) {
                Write-Host ("[{0}] {1}" -f ($i + 1), $guilds[$i].name)
            }
            do {
                $choice = Read-Host "Enter the number for the Roanoke Season 3 server"
                $index = 0
                $valid = [int]::TryParse($choice, [ref]$index) -and $index -ge 1 -and $index -le $guilds.Count
            } until ($valid)
            $GuildId = [string]$guilds[$index - 1].id
        }
    }

    $guild = Invoke-DiscordGet "/guilds/$GuildId" $token
    $member = Invoke-DiscordGet "/guilds/$GuildId/members/$($bot.id)" $token
    $roles = @(Invoke-DiscordGet "/guilds/$GuildId/roles" $token)
    $channels = @(Invoke-DiscordGet "/guilds/$GuildId/channels" $token)

    [int64]$base = Get-BasePermissions $GuildId $member $roles

    Write-Host ""
    Write-Host ("Bot:    {0}" -f $bot.username)
    Write-Host ("Server: {0}" -f $guild.name)
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

        [int64]$perms = Get-ChannelPermissions $GuildId $bot.id $member $roles $channel
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
