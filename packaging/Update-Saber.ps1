# Saber-Translator 更新程式
# 只更新程式檔案；data-v2（書籍、設定、API Key、術語表）完全不會被改動。
param(
    [switch]$Offline,                     # 不連 GitHub，只用下載資料夾裡的檔案
    [string]$DownloadsDir = '',           # 預設為使用者的「下載」資料夾
    [string]$ReleaseFile = '',            # 測試用：從檔案讀取 Release 資訊
    [switch]$Auto,                        # 由 Saber-Translator.exe 開啟時自動執行：不詢問，更新後重新開啟程式
    [int]$WaitPid = 0                     # 先等這個程序（剛才開啟的 Saber-Translator）結束
)
$ErrorActionPreference = 'Stop'
$UpdaterVersion = 4  # 更新程式版本：套用時不會用較舊的更新程式覆蓋這個檔案
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Owner = 'nettoyagejezabelle579-blip'
$Repo = 'Saber-Translator'
$Tag = 'galaxy-zh-hant-cpu'
$Prefix = 'Saber-Translator-zhHant-CPU'
$App = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $App 'data-v2'
$TokenFile = Join-Path $DataDir 'github-token.txt'
$BuildFile = Join-Path $App 'BUILD.json'
# 下載中斷後再執行會從中斷處繼續：已下載的檔案保留在這裡，更新完成才刪除
$WorkRoot = Join-Path $env:TEMP 'saber-update'

function Say([string]$Message, [string]$Color = 'White') { Write-Host $Message -ForegroundColor $Color }
function Start-Saber {
    # 重新開啟時略過更新檢查，避免更新失敗時反覆開啟更新程式
    $env:SABER_SKIP_UPDATE_CHECK = '1'
    try { Start-Process -FilePath (Join-Path $App 'Saber-Translator.exe') -WorkingDirectory $App | Out-Null }
    catch { Say "無法自動開啟 Saber-Translator，請手動雙擊 Saber-Translator.exe。（$($_.Exception.Message)）" 'Yellow' }
}
function Ask([string]$Question) {
    try { return (Read-Host $Question) } catch { return '' }
}
function Stop-Update([string]$Message) {
    Say $Message 'Red'
    if ($Auto -and (Test-Path (Join-Path $App 'Saber-Translator.exe'))) {
        Ask '按 Enter 開啟 Saber-Translator（這次先不更新）' | Out-Null
        Start-Saber
    }
    exit 1
}
if ($Auto) {
    try { $Host.UI.RawUI.WindowTitle = 'Saber-Translator 自動更新' } catch { }
    Say 'Saber-Translator 有新版本，正在自動更新（書籍、設定、API Key 都不會被改動）...' 'Cyan'
}

if (-not (Test-Path (Join-Path $App 'Saber-Translator.exe'))) {
    Stop-Update '請把更新程式放在 Saber-Translator.exe 所在的資料夾再執行。'
}

function Close-Saber {
    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and $_.Path.StartsWith($App, [StringComparison]::OrdinalIgnoreCase)
    })
    if ($running.Count -eq 0) { return }
    Say 'Saber-Translator 正在執行，更新前需要先關閉。' 'Yellow'
    $answer = Ask '要自動關閉嗎？(Y/N)'
    if ($answer -notmatch '^[Yy]') { Stop-Update '已取消。請關閉 Saber-Translator 後再執行更新。' }
    $running | Stop-Process -Force
    Start-Sleep -Seconds 3
}

# 1. 關閉執行中的 Saber-Translator（自動更新時先等剛才開啟的程式自己結束）
if ($WaitPid -gt 0) {
    Wait-Process -Id $WaitPid -Timeout 60 -ErrorAction SilentlyContinue
}
Close-Saber

# 2. 目前版本
$LocalBuild = ''
if (Test-Path $BuildFile) { $LocalBuild = (Get-Content $BuildFile -Raw | ConvertFrom-Json).build }
if ($LocalBuild) { Say "目前版本：$LocalBuild" } else { Say '目前版本：舊版（沒有版本資訊，會下載完整程式）' }

# 3. 取得最新版資訊
function Get-Release([string]$Token) {
    $headers = @{ 'User-Agent' = 'Saber-Updater'; 'Accept' = 'application/vnd.github+json' }
    if ($Token) { $headers['Authorization'] = "Bearer $Token" }
    Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo/releases/tags/$Tag" -Headers $headers
}
$Token = ''
if (Test-Path $TokenFile) { $Token = (Get-Content $TokenFile -Raw).Trim() }
$Release = $null
try {
    if ($Offline) { throw 'offline' }
    if ($ReleaseFile) {
        $Release = Get-Content $ReleaseFile -Raw -Encoding UTF8 | ConvertFrom-Json
    } else {
        $Release = Get-Release $Token
    }
} catch {
    if ($Offline) {
        Say '離線模式：使用下載資料夾裡的更新檔。'
    } elseif ($Auto) {
        Stop-Update ('無法連線到 GitHub（' + $_.Exception.Message + '），這次先不更新。')
    } elseif (-not $Token) {
        Say '這個 GitHub 倉庫是私人倉庫，需要一組「唯讀存取權杖」才能自動下載更新（只需設定一次）。' 'Yellow'
        Say '建立方式：GitHub 右上角頭像 → Settings → Developer settings → Personal access tokens'
        Say '  → Fine-grained tokens → Generate new token；Repository access 選 Saber-Translator，'
        Say '  Permissions → Contents 選 Read-only，產生後複製權杖。'
        $Token = (Read-Host '請貼上權杖（直接按 Enter：改用「下載」資料夾裡已下載的更新檔）').Trim()
        if ($Token) {
            try {
                $Release = Get-Release $Token
                New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
                Set-Content -Path $TokenFile -Value $Token -Encoding ASCII
                Say '權杖已儲存在 data-v2\github-token.txt，下次不用再輸入。' 'Green'
            } catch {
                Say ('權杖無效或沒有權限：' + $_.Exception.Message) 'Red'
                $Token = ''
            }
        }
    } else {
        Say ('無法連線到 GitHub（' + $_.Exception.Message + '），改用「下載」資料夾裡的更新檔。') 'Yellow'
    }
}

function Invoke-Curl($Asset, [string]$Destination) {
    # -C - ：檔案已有一部分時，從中斷處繼續下載
    $curlArgs = @('-L', '--fail', '-C', '-', '-o', $Destination, '-H', 'User-Agent: Saber-Updater')
    if ($Token) {
        $curlArgs += @('-H', "Authorization: Bearer $Token", '-H', 'Accept: application/octet-stream', $Asset.url)
    } else {
        $curlArgs += $Asset.browser_download_url
    }
    & curl.exe @curlArgs
}

function Test-Asset($Asset, [string]$Path) {
    $expected = [int64]$Asset.size
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ($expected -gt 0 -and (Get-Item -LiteralPath $Path).Length -ne $expected) { return $false }
    if ($Asset.digest -and "$($Asset.digest)".StartsWith('sha256:')) {
        $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        return $hash -eq "$($Asset.digest)".Substring(7).ToLowerInvariant()
    }
    return $true
}

function Get-Asset($Asset, [string]$Destination) {
    $expected = [int64]$Asset.size
    if (Test-Path -LiteralPath $Destination) {
        $have = (Get-Item -LiteralPath $Destination).Length
        if ($expected -gt 0 -and $have -eq $expected -and (Test-Asset $Asset $Destination)) {
            Say "$($Asset.name) 上次已下載完成，略過。" 'Green'
            return
        }
        if ($expected -gt 0 -and $have -lt $expected -and $have -gt 0) {
            Say ("繼續上次中斷的下載（已完成 {0:N0} / {1:N0} MB）..." -f ($have / 1MB), ($expected / 1MB))
        } else {
            Remove-Item -LiteralPath $Destination -Force
        }
    }
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        Invoke-Curl $Asset $Destination
        $code = $LASTEXITCODE
        if ($code -eq 33 -or $code -eq 36) {
            # 伺服器不支援續傳：刪掉重新下載
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
            Invoke-Curl $Asset $Destination
            $code = $LASTEXITCODE
        }
        if ($code -eq 0) {
            if (Test-Asset $Asset $Destination) { return }
            Say "$($Asset.name) 檔案不完整或已損壞，重新下載..." 'Yellow'
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
        } elseif ($attempt -lt 5) {
            Say "下載中斷（curl 代碼 $code），$($attempt * 5) 秒後從中斷處繼續..." 'Yellow'
        }
        if ($attempt -lt 5) { Start-Sleep -Seconds ($attempt * 5) }
    }
    Stop-Update "下載失敗：$($Asset.name)。請確認網路後再執行一次 Update-Saber.bat，已下載的部分會保留。"
}

function Assert-FreeSpace($Assets) {
    # 檔案直接寫入程式資料夾、套用完就刪掉 zip，所以只需要「還沒下載完的部分」再加 1 GB
    $needed = 1GB
    foreach ($asset in $Assets) {
        $path = Join-Path $Work $asset.name
        if (Test-Path -LiteralPath "$path.done") { continue }
        $have = 0
        if (Test-Path -LiteralPath $path) { $have = (Get-Item -LiteralPath $path).Length }
        $needed += [Math]::Max([int64]0, [int64]$asset.size - $have)
    }
    $drive = $WorkRoot.Substring(0, 1)
    $free = $null
    try { $free = (Get-PSDrive -Name $drive -ErrorAction Stop).Free } catch { return }
    if ($free -and $free -lt $needed) {
        Stop-Update ("{0} 槽空間不足：更新還需要約 {1:N1} GB，目前只剩 {2:N1} GB。請清出空間後再執行（已下載的部分會保留）。" -f $drive, ($needed / 1GB), ($free / 1GB))
    }
}

function Use-WorkDir([string]$Name, [switch]$Fresh) {
    New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
    $dir = Join-Path $WorkRoot $Name
    if ($Fresh -and (Test-Path -LiteralPath $dir)) { Remove-Item -LiteralPath $dir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if (-not $Fresh) {
        # 舊版更新程式把分卷直接放在 saber-update 裡：搬過來沿用（下載時會核對，不符才重新下載）
        Get-ChildItem -LiteralPath $WorkRoot -Filter '*.zip' -File | ForEach-Object {
            $target = Join-Path $dir $_.Name
            if (-not (Test-Path -LiteralPath $target)) { Move-Item -LiteralPath $_.FullName -Destination $target }
        }
    }
    # 只保留這一版的資料夾；其他版本（或舊版更新程式）留下的暫存檔都清掉
    Get-ChildItem -LiteralPath $WorkRoot -Force | Where-Object { $_.Name -ne $Name } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    return $dir
}

function Get-ZipInfo([string]$Zip) {
    # 小型更新包裡的 UPDATE-INFO.json（完整分卷沒有）
    $archive = [IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        $entry = $archive.GetEntry('Saber-Translator/UPDATE-INFO.json')
        if (-not $entry) { return $null }
        $reader = New-Object IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8)
        try { return ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
    } finally { $archive.Dispose() }
}

function Get-EntryUpdaterVersion($Entry) {
    $reader = New-Object IO.StreamReader($Entry.Open(), [Text.Encoding]::UTF8)
    try { $text = $reader.ReadToEnd() } finally { $reader.Dispose() }
    if ($text -match '\$UpdaterVersion\s*=\s*(\d+)') { return [int]$Matches[1] }
    return 0
}

function Write-Entry($Entry, [string]$Target) {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target)) | Out-Null
    for ($attempt = 1; ; $attempt++) {
        try {
            $source = $Entry.Open()
            try {
                $output = [IO.File]::Create($Target)
                try { $source.CopyTo($output, 1048576) } finally { $output.Dispose() }
            } finally { $source.Dispose() }
            return
        } catch {
            if ($attempt -ge 8) { throw "無法寫入 $Target（$($_.Exception.Message)）" }
            # 防毒軟體掃描剛寫入的檔案時會短暫鎖住；唯讀檔先解除唯讀，稍等再試
            try { if ([IO.File]::Exists($Target)) { [IO.File]::SetAttributes($Target, [IO.FileAttributes]::Normal) } } catch { }
            Start-Sleep -Milliseconds (250 * $attempt)
        }
    }
}

# 把 zip 內的 Saber-Translator\ 直接寫入程式資料夾：不需要額外的暫存空間。
# data-v2 一律跳過；BUILD.json 與 UPDATE-INFO.json 先放在暫存資料夾，全部套用完才處理。
function Install-Part([string]$Zip) {
    $root = [IO.Path]::GetFullPath($App).TrimEnd('\', '/')
    $separator = [IO.Path]::DirectorySeparatorChar
    $entryPrefix = 'Saber-Translator/'
    $archive = [IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        $entries = @($archive.Entries | Where-Object { -not $_.FullName.EndsWith('/') })
        Say ("套用 {0}（{1} 個檔案）..." -f (Split-Path $Zip -Leaf), $entries.Count)
        $count = 0
        foreach ($entry in $entries) {
            $count++
            if ($count % 1000 -eq 0) { Say ("  已套用 {0} / {1}" -f $count, $entries.Count) }
            $name = $entry.FullName -replace '\\', '/'
            if (-not $name.StartsWith($entryPrefix)) { continue }
            $relative = $name.Substring($entryPrefix.Length)
            if ($relative -eq 'data-v2' -or $relative.StartsWith('data-v2/')) { continue }
            if ($relative -eq 'BUILD.json') {
                $target = Join-Path $Work 'BUILD.json.new'
            } elseif ($relative -eq 'UPDATE-INFO.json') {
                $target = Join-Path $Work 'UPDATE-INFO.json'
            } elseif ($relative -eq 'Update-Saber.bat' -and (Test-Path -LiteralPath (Join-Path $App $relative))) {
                continue  # 正在執行的批次檔不能覆蓋
            } elseif ($relative -eq 'Update-Saber.ps1' -and (Get-EntryUpdaterVersion $entry) -lt $UpdaterVersion) {
                continue  # 不用較舊的更新程式蓋掉現在這個
            } else {
                $target = [IO.Path]::GetFullPath([IO.Path]::Combine($root, $relative))
                if (-not $target.StartsWith($root + $separator, [StringComparison]::OrdinalIgnoreCase)) { continue }
            }
            Write-Entry $entry $target
        }
    } finally { $archive.Dispose() }
}

# 4. 下載（線上）或找到（離線）更新檔
$DeleteZips = $false
if ($Release) {
    $assets = @{}
    foreach ($asset in $Release.assets) { $assets[$asset.name] = $asset }
    New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
    $info = $null
    if ($assets.ContainsKey('update-info.json')) {
        $infoPath = Join-Path $WorkRoot 'update-info.json'
        Remove-Item -LiteralPath $infoPath -Force -ErrorAction SilentlyContinue
        Get-Asset $assets['update-info.json'] $infoPath
        $info = Get-Content $infoPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Remove-Item -LiteralPath $infoPath -Force
    }
    $RemoteBuild = if ($info) { $info.build } else { ($Release.name -split ' ')[-1] }
    if ($LocalBuild -and $LocalBuild -eq $RemoteBuild) {
        Say "已經是最新版本（$LocalBuild），不需要更新。" 'Green'
        Remove-Item $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
        if ($Auto) { Start-Saber }
        exit 0
    }
    $Work = Use-WorkDir ('build-' + ($RemoteBuild -replace '[^A-Za-z0-9._-]', '_'))
    if ($info -and $LocalBuild -and $info.base -eq $LocalBuild -and $assets.ContainsKey("$Prefix-update.zip")) {
        $selected = @($assets["$Prefix-update.zip"])
        Say ("小型更新包（{0} → {1}，約 {2:N0} MB）" -f $LocalBuild, $RemoteBuild, ($selected[0].size / 1MB))
    } else {
        $selected = @($Release.assets | Where-Object { $_.name -like "$Prefix-part*.zip" } | Sort-Object name)
        if ($selected.Count -eq 0) { Stop-Update 'GitHub 上找不到更新檔，請稍後再試。' }
        $total = ($selected | Measure-Object -Property size -Sum).Sum / 1GB
        Say ("需要下載完整程式：{0} 個分卷，約 {1:N1} GB（書籍與設定會保留）。" -f $selected.Count, $total) 'Yellow'
        if ($Auto) {
            # 版本差太多才需要完整下載，時間較長，先問一聲
            $answer = Ask '這次需要下載完整程式，時間較長。現在下載嗎？(Y/N)'
            if ($answer -notmatch '^[Yy]') {
                New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
                Set-Content -LiteralPath (Join-Path $DataDir 'update-skipped.txt') -Value $RemoteBuild -Encoding ASCII
                Say '已略過這個版本，開啟程式時不會再詢問；之後要更新請雙擊 Update-Saber.bat。' 'Yellow'
                Start-Saber
                exit 0
            }
        }
        Say '中途關掉視窗或斷線也沒關係：再執行一次會從中斷處繼續，已下載的部分不會重新下載。'
    }
    Assert-FreeSpace $selected
    # 先下載完全部檔案；這段期間程式完全不會被改動
    foreach ($asset in $selected) {
        if (Test-Path -LiteralPath ((Join-Path $Work $asset.name) + '.done')) { continue }
        Say "下載 $($asset.name)..."
        Get-Asset $asset (Join-Path $Work $asset.name)
    }
    $Zips = @($selected | ForEach-Object { Join-Path $Work $_.name })
    $DeleteZips = $true
} else {
    # 離線：使用「下載」資料夾中手動下載的檔案（不會刪除這些檔案）
    $Work = Use-WorkDir 'offline' -Fresh
    $downloads = if ($DownloadsDir) { $DownloadsDir } else { Join-Path $env:USERPROFILE 'Downloads' }
    $update = Get-ChildItem $downloads -Filter "$Prefix-update*.zip" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $parts = @(Get-ChildItem $downloads -Filter "$Prefix-part*.zip" -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($update -and $LocalBuild) {
        $Zips = @($update.FullName)
    } elseif ($parts.Count -gt 0) {
        $Zips = @($parts | ForEach-Object { $_.FullName })
    } else {
        Stop-Update '找不到更新檔。請到 GitHub Release 頁面下載所有 part*.zip（或 update.zip）到「下載」資料夾後再執行。'
    }
    Say "使用「下載」資料夾中的 $($Zips.Count) 個檔案更新。"
}

# 5. 小型更新包只適用於特定版本：套用前先確認
foreach ($zip in $Zips) {
    if (-not (Test-Path -LiteralPath $zip)) { continue }
    try { $zipInfo = Get-ZipInfo $zip } catch { Stop-Update "更新檔損壞：$(Split-Path $zip -Leaf)。請再執行一次 Update-Saber.bat。" }
    if ($zipInfo -and $zipInfo.base -ne $LocalBuild) {
        Stop-Update "這個更新包只適用於 $($zipInfo.base) 版，你目前是 $LocalBuild 版。請改用完整分卷（part1、part2…）更新。"
    }
}

# 6. 套用：直接寫入程式資料夾，每套用完一個就刪掉 zip。
# BUILD.json 最後才寫入：中途被中斷時版本號仍是舊的，再執行一次會補完。
Close-Saber
Say '套用更新中（data-v2 不會被改動，請不要關閉視窗）...'
foreach ($zip in $Zips) {
    $doneMark = Join-Path $Work ((Split-Path $zip -Leaf) + '.done')
    if ($DeleteZips -and (Test-Path -LiteralPath $doneMark)) {
        Say "$(Split-Path $zip -Leaf) 上次已套用，略過。" 'Green'
        continue
    }
    try {
        Install-Part $zip
    } catch {
        Stop-Update "套用 $(Split-Path $zip -Leaf) 失敗：$($_.Exception.Message)。請確認 Saber-Translator 已關閉後再執行一次 Update-Saber.bat（已下載的檔案會保留）。"
    }
    if ($DeleteZips) {
        Set-Content -LiteralPath $doneMark -Value 'ok'
        Remove-Item -LiteralPath $zip -Force
    }
}

$UpdateInfoFile = Join-Path $Work 'UPDATE-INFO.json'
if (Test-Path -LiteralPath $UpdateInfoFile) {
    $UpdateInfo = Get-Content -LiteralPath $UpdateInfoFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($relative in @($UpdateInfo.deleted)) {
        if (-not $relative -or $relative -like 'data-v2*') { continue }
        $target = Join-Path $App ($relative -replace '/', '\')
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
    }
}
# 清掉舊版留下、目前版本沒有的 *.dist-info 資料夾：缺少 METADATA 的舊資料夾會讓
# importlib.metadata 回傳 None，第三方套件（openai）匯入時就會崩潰。只看 _internal 第一層。
$ManifestFile = Join-Path $App 'build-manifest.json'
if (Test-Path -LiteralPath $ManifestFile) {
    try {
        $Manifest = Get-Content -LiteralPath $ManifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $Keep = @{}
        foreach ($name in $Manifest.files.PSObject.Properties.Name) {
            if ($name -match '^_internal/([^/]+\.dist-info)/') { $Keep[$Matches[1].ToLowerInvariant()] = $true }
        }
        if ($Keep.Count -gt 0) {
            $Internal = Join-Path $App '_internal'
            foreach ($dir in @(Get-ChildItem -LiteralPath $Internal -Directory -Filter '*.dist-info' -ErrorAction SilentlyContinue)) {
                if (-not $Keep.ContainsKey($dir.Name.ToLowerInvariant())) {
                    Remove-Item -LiteralPath $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
                    Say "已移除舊版留下的 $($dir.Name)" 'DarkGray'
                }
            }
        }
    } catch {
        Say "略過清理舊套件資訊：$($_.Exception.Message)" 'DarkGray'
    }
}
$NewBuildFile = Join-Path $Work 'BUILD.json.new'
if (Test-Path -LiteralPath $NewBuildFile) { Copy-Item -LiteralPath $NewBuildFile -Destination $BuildFile -Force }
Remove-Item $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $DataDir 'update-skipped.txt') -Force -ErrorAction SilentlyContinue

$NewBuild = ''
if (Test-Path $BuildFile) { $NewBuild = (Get-Content $BuildFile -Raw | ConvertFrom-Json).build }
Say "更新完成！目前版本：$NewBuild。你的書籍、設定、API Key、術語表都已保留。" 'Green'
if ($Auto) {
    Say '正在重新開啟 Saber-Translator...'
    Start-Saber
    Start-Sleep -Seconds 2
} else {
    Say '現在可以重新開啟 Saber-Translator.exe。'
}
