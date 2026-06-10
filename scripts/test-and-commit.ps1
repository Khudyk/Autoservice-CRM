<#
.SYNOPSIS
    Runs pytest, and if all tests pass — creates a Git commit.

.DESCRIPTION
    Automation script: test -> commit.
    Runs pytest, on success stages all changes and creates a commit.
    On failure shows errors and aborts.

.PARAMETER Message
    Commit message. If not specified — auto-generated.

.PARAMETER Push
    If specified — runs git push after commit.

.EXAMPLE
    .\scripts\test-and-commit.ps1
    .\scripts\test-and-commit.ps1 -Message "Added quick-create client to list page"
    .\scripts\test-and-commit.ps1 -Push
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Message = '',

    [switch]$Push
)

$ErrorActionPreference = 'Stop'

# ---- Configuration ----
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PytestArgs = @('--tb=short', '-q')

# ---- Colored output ----
function Write-Step($Text) {
    Write-Host "`n==> " -NoNewline -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor White
}

function Write-Success($Text) {
    Write-Host "  [v] $Text" -ForegroundColor Green
}

function Write-Failure($Text) {
    Write-Host "  [x] $Text" -ForegroundColor Red
}

function Write-Info($Text) {
    Write-Host "  [i] $Text" -ForegroundColor DarkYellow
}

# ---- Find Git ----
$GitExe = ''
try {
    $gitCmd = Get-Command git -ErrorAction Stop
    $GitExe = $gitCmd.Source
} catch {
    $fallbackPaths = @(
        "C:\Program Files\Git\bin\git.exe",
        "C:\Program Files (x86)\Git\bin\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\git.exe"
    )
    foreach ($fp in $fallbackPaths) {
        if (Test-Path -LiteralPath $fp) { $GitExe = $fp; break }
    }
}
if (-not $GitExe) {
    Write-Failure "Git not found. Install Git for Windows: https://git-scm.com"
    exit 1
}

# ---- Check Git repository ----
if (-not (Test-Path -LiteralPath "$ProjectRoot\.git")) {
    Write-Failure "Not a Git repository. Run 'git init' in project root."
    exit 1
}

# ---- 1. Run tests ----
Write-Step "Step 1: Running pytest..."

Set-Location -LiteralPath $ProjectRoot
$pytestOutput = & pytest @PytestArgs 2>&1
$pytestExitCode = $LASTEXITCODE

if ($pytestExitCode -ne 0) {
    Write-Failure "Tests FAILED (code: $pytestExitCode)"
    Write-Host "`n--- pytest output ---" -ForegroundColor Yellow
    $pytestOutput | ForEach-Object { Write-Host $_ }
    Write-Host "--- end of output ---`n" -ForegroundColor Yellow
    exit $pytestExitCode
}

Write-Success "All tests passed!"

# ---- 2. Git status ----
Write-Step "Step 2: Checking Git status..."

$status = & $GitExe -C $ProjectRoot status --porcelain
if (-not $status) {
    Write-Info "No changes to commit."
    exit 0
}

Write-Info "Changed files found:"
$status -split "`n" | ForEach-Object {
    if ($_.Trim()) { Write-Host "       $_" -ForegroundColor DarkYellow }
}

# ---- 3. Stage changes ----
Write-Step "Step 3: Staging files (git add)..."
& $GitExe -C $ProjectRoot add -A 2>&1 | Out-Null
Write-Success "Files staged."

# ---- 4. Commit ----
Write-Step "Step 4: Creating commit..."

if (-not $Message) {
    # Auto-generate message from changed files
    $changedFiles = & $GitExe -C $ProjectRoot diff --cached --name-only 2>&1
    $fileList = $changedFiles -split "`n" | Where-Object { $_ -and $_.Trim() }

    $commitMsg = "chore: auto-commit after successful tests

Files: $($fileList -join ', ')"
} else {
    $commitMsg = $Message
}

& $GitExe -C $ProjectRoot commit -m $commitMsg 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Success "Commit created!"
    Write-Info "Message: $($commitMsg -split "`n" | Select-Object -First 1)"

    # ---- 5. Push (optional) ----
    if ($Push) {
        Write-Step "Step 5: Pushing to remote (git push)..."

        $remoteUrl = & $GitExe -C $ProjectRoot remote get-url origin 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Failure "Remote not configured. Add it manually:"
            Write-Host "       git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git" -ForegroundColor Yellow
            exit 1
        }

        & $GitExe -C $ProjectRoot push 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Pushed to $remoteUrl"
        } else {
            Write-Failure "Push failed. You may need a GitHub Personal Access Token."
            exit 1
        }
    }
} else {
    Write-Failure "Commit failed."
    exit 1
}

Write-Host "`n" -NoNewline
Write-Success "Done! Tests -> Commit -> Success."
