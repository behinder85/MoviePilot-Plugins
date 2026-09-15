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

foreach ($file in @(
    (Join-Path $repoRoot "package.v2.json"),
    (Join-Path $repoRoot "plugins.v2\hdhive_dian115_checkin\__init__.py"),
    (Join-Path $repoRoot "README.md")
)) {
    $text = Get-Content -LiteralPath $file -Raw -Encoding UTF8
    $updated = $text.Replace("YOUR_GITHUB_USER/YOUR_REPO", $rawPath)
    if ($updated -ne $text) {
        Set-Content -LiteralPath $file -Value $updated -Encoding UTF8 -NoNewline
        Write-Host "已替换占位符：$file"
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
