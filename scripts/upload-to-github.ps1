[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl,

    [string]$Token = "",

    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$repoUrl = $RepoUrl.Trim().TrimEnd("/")
if ($repoUrl -notmatch "^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$") {
    throw "RepoUrl 必须是 https://github.com/<owner>/<repo>[.git] 格式"
}
$owner = $Matches[1]
$repo = $Matches[2] -replace "\.git$", ""
$rawPath = "$owner/$repo"

$pluginRoot = Join-Path $repoRoot "plugins.v2\hdhivedian115checkin"
if (!(Test-Path (Join-Path $pluginRoot "__init__.py"))) {
    throw "未找到插件入口，请确认 plugins.v2\hdhivedian115checkin\__init__.py 存在"
}

foreach ($file in @(
    (Join-Path $repoRoot "package.v2.json"),
    (Join-Path $pluginRoot "__init__.py")
)) {
    $text = Get-Content -LiteralPath $file -Raw -Encoding UTF8
    $updated = $text.Replace("YOUR_GITHUB_USER/YOUR_REPO", $rawPath)
    $updated = [regex]::Replace(
        $updated,
        "https://raw\.githubusercontent\.com/[^/""]+/[^/""]+/main/icons/hdhivedian115checkin\.png",
        "https://raw.githubusercontent.com/$rawPath/main/icons/hdhivedian115checkin.png"
    )
    if ($updated -ne $text) {
        [System.IO.File]::WriteAllText(
            $file,
            $updated.TrimStart([char]0xFEFF).Replace("`r`n", "`n"),
            (New-Object System.Text.UTF8Encoding($false))
        )
        Write-Host "已更新仓库地址：$file"
    }
}

if (!(Test-Path (Join-Path $repoRoot ".git"))) {
    git init -b $Branch
}

$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $existing) {
    git remote set-url origin $repoUrl
} else {
    git remote add origin $repoUrl
}

git add -A
if (git diff --cached --quiet) {
    Write-Host "没有需要提交的变更。"
} else {
    git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" commit -m "chore: upload HDHive/Dian115 checkin plugin"
}

if ($Token) {
    $pushUrl = "https://oauth2:$Token@github.com/$owner/$repo.git"
} else {
    $pushUrl = $repoUrl
}
git push $pushUrl $Branch

Write-Host "已推送到 $repoUrl ($Branch)"
Write-Host "接下来请到 GitHub Actions 手动运行一次 Release Plugin，或在仓库中启用工作流。"
