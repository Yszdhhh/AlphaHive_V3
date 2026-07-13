# AlphaHive V3.1.1 Phase 1 - 一键建目录骨架
# 在 G:\Quant test\ 下运行，会创建 AlphaHive_V3\ 完整目录树
# PowerShell (Windows 11)，无需管理员权限

$ErrorActionPreference = "Stop"

# ---- 目标根目录（如需改路径，只改这一行）----
$root = "G:\Quant test\AlphaHive_V3"

Write-Host "AlphaHive V3.1.1 Phase 1 - creating project structure at: $root" -ForegroundColor Cyan

$dirs = @(
    "config",
    "data\raw",
    "data\processed",
    "data\snapshots",
    "ledger",
    "prompts",
    "scripts",
    "harness\schemas",
    "harness\manifests",
    "harness\runs",
    "harness\logs",
    "harness\fixtures",
    "reports\daily",
    "reports\weekly"
)

foreach ($d in $dirs) {
    $full = Join-Path $root $d
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Force -Path $full | Out-Null
        Write-Host "  [+] $d" -ForegroundColor Green
    } else {
        Write-Host "  [=] $d (exists)" -ForegroundColor DarkGray
    }
}

# 占位 .gitkeep，保证空目录进 git
$keepDirs = @("data\raw","data\processed","data\snapshots","harness\runs","harness\logs","reports\daily","reports\weekly")
foreach ($d in $keepDirs) {
    $keep = Join-Path $root "$d\.gitkeep"
    if (-not (Test-Path $keep)) { New-Item -ItemType File -Path $keep | Out-Null }
}

Write-Host "`nDirectory tree created. Next steps:" -ForegroundColor Cyan
Write-Host "  1. Copy KARPATHY_GUIDELINES.md from old alpha_hive repo to $root\" -ForegroundColor Yellow
Write-Host "  2. Copy templates\ contents into config\ ledger\ harness\ prompts\" -ForegroundColor Yellow
Write-Host "  3. git init  (local only, NO remote/push - token red line)" -ForegroundColor Yellow
Write-Host "  4. Implement scripts\ per scripts_spec\" -ForegroundColor Yellow

# 显示最终结构
Write-Host "`nFinal structure:" -ForegroundColor Cyan
Get-ChildItem -Path $root -Recurse -Directory | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    Write-Host "  $rel"
}
