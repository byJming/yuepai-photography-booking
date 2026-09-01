$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$root = Split-Path -Parent $PSScriptRoot
$errors = [System.Collections.Generic.List[string]]::new()

function Add-CheckError {
    param([string]$Message)
    $errors.Add($Message)
}

$requiredFiles = @(
    'project.config.json',
    'miniprogram/app.ts',
    'miniprogram/app.json',
    'miniprogram/app.wxss',
    'miniprogram/sitemap.json',
    'miniprogram/custom-tab-bar/index.ts',
    'miniprogram/custom-tab-bar/index.json',
    'miniprogram/custom-tab-bar/index.wxml',
    'miniprogram/custom-tab-bar/index.wxss'
)

$pages = @(
    'pages/works/index',
    'pages/booking/index',
    'pages/profile/index',
    'pages/portfolio-detail/index',
    'pages/booking-form/index',
    'pages/booking-detail/index',
    'pages/policies/index'
)

foreach ($relativePath in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $relativePath))) {
        Add-CheckError "缺少文件：$relativePath"
    }
}

foreach ($page in $pages) {
    foreach ($extension in @('ts', 'json', 'wxml', 'wxss')) {
        $relativePath = "miniprogram/$page.$extension"
        if (-not (Test-Path -LiteralPath (Join-Path $root $relativePath))) {
            Add-CheckError "缺少页面文件：$relativePath"
        }
    }
}

$jsonFiles = Get-ChildItem -Path $root -Recurse -Filter *.json -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch '\\node_modules\\' -and
        $_.Name -notin @('package-lock.json', 'project.private.config.json')
    }

foreach ($jsonFile in $jsonFiles) {
    try {
        Get-Content -LiteralPath $jsonFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
    }
    catch {
        Add-CheckError "JSON 无法解析：$($jsonFile.FullName)"
    }
}

$projectConfigPath = Join-Path $root 'project.config.json'
if (Test-Path -LiteralPath $projectConfigPath) {
    $projectConfig = Get-Content -LiteralPath $projectConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($projectConfig.miniprogramRoot -ne 'miniprogram/') {
        Add-CheckError 'project.config.json 的 miniprogramRoot 必须是 miniprogram/'
    }
    if ($projectConfig.setting.urlCheck -ne $true) {
        Add-CheckError '共享 project.config.json 必须开启合法域名校验，本地调试请在 private 配置中覆盖'
    }
    if ($projectConfig.setting.minified -ne $true -or $projectConfig.setting.minifyWXSS -ne $true -or $projectConfig.setting.minifyWXML -ne $true) {
        Add-CheckError '共享 project.config.json 必须开启 JS、WXSS 和 WXML 上传压缩'
    }
    if ($projectConfig.libVersion -notmatch '^\d+\.\d+\.\d+$') {
        Add-CheckError '共享 project.config.json 必须固定经过验收的数字基础库版本'
    }
    if ($projectConfig.description -match '展示版') {
        Add-CheckError '共享 project.config.json 不应继续标记为展示版'
    }
}

$appJsonPath = Join-Path $root 'miniprogram/app.json'
if (Test-Path -LiteralPath $appJsonPath) {
    $appJson = Get-Content -LiteralPath $appJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($page in $pages) {
        if ($appJson.pages -notcontains $page) {
            Add-CheckError "app.json 未注册页面：$page"
        }
    }
    if (-not $appJson.tabBar.custom) {
        Add-CheckError 'app.json 必须启用自定义 TabBar'
    }
}

$miniprogramPath = Join-Path $root 'miniprogram'
if (Test-Path -LiteralPath $miniprogramPath) {
    $mediaExtensions = @('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp3', '.wav', '.aac', '.m4a', '.ogg')
    $oversizedMedia = Get-ChildItem -Path $miniprogramPath -Recurse -File |
        Where-Object { $_.Extension.ToLowerInvariant() -in $mediaExtensions -and $_.Length -gt 200KB }
    foreach ($mediaFile in $oversizedMedia) {
        $relativePath = $mediaFile.FullName.Substring($root.Length + 1)
        Add-CheckError "图片或音频资源超过 200 KiB：$relativePath ($([math]::Round($mediaFile.Length / 1KB, 1)) KiB)"
    }

    $forbidden = Get-ChildItem -Path $miniprogramPath -Recurse -File |
        Where-Object { $_.Extension -in @('.ts', '.js', '.json', '.wxml') } |
        Select-String -Pattern 'owner-service|admin-api|管理中心' -SimpleMatch -Encoding UTF8
    if ($forbidden) {
        Add-CheckError '小程序中不应包含管理端入口或管理 API 代码'
    }

    $unsupportedLocaleApis = Get-ChildItem -Path $miniprogramPath -Recurse -File |
        Where-Object { $_.Extension -in @('.ts', '.js') } |
        Select-String -Pattern '\bIntl\b|\.toLocale(?:Date|Time)?String\(|wx\.getSystemInfoSync\(' -Encoding UTF8
    if ($unsupportedLocaleApis) {
        Add-CheckError '小程序运行时代码不应依赖 Intl、toLocale*String 或已弃用的 wx.getSystemInfoSync'
    }

    $wxmlFiles = Get-ChildItem -Path $miniprogramPath -Recurse -File -Filter *.wxml
    foreach ($wxmlFile in $wxmlFiles) {
        $content = Get-Content -LiteralPath $wxmlFile.FullName -Raw -Encoding UTF8
        $contentWithoutAttributes = [regex]::Replace($content, '="[^"]*"', '=""')
        $textNodes = [regex]::Matches($contentWithoutAttributes, '>([^<>]*)<')
        foreach ($textNode in $textNodes) {
            $visibleText = [regex]::Replace($textNode.Groups[1].Value, '\{\{.*?\}\}', '').Trim()
            if ($visibleText -match '[A-Za-z]' -and $visibleText -ne '小程序作者：© ming woqiang0610@163.com') {
                $relativePath = $wxmlFile.FullName.Substring($root.Length + 1)
                Add-CheckError "前端存在英文可见文案：$relativePath -> $visibleText"
            }
        }
    }
}

if ($errors.Count -gt 0) {
    Write-Output '小程序结构检查失败：'
    foreach ($message in $errors) {
        Write-Output "- $message"
    }
    exit 1
}

Write-Output '小程序结构检查通过。'
