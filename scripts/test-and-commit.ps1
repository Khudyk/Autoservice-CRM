<#
.SYNOPSIS
    Запускає pytest, і якщо всі тести проходять — створює Git-коміт.

.DESCRIPTION
    Скрипт для автоматизації: тестування → коміт.
    Виконує pytest, при успіху stage всі зміни та створює коміт.
    При невдачі показує помилки та переривається.

.PARAMETER Message
    Повідомлення коміту. Якщо не вказано — генерується автоматично.

.PARAMETER Push
    Якщо вказано — після коміту виконує git push.

.EXAMPLE
    .\scripts\test-and-commit.ps1
    .\scripts\test-and-commit.ps1 -Message "Додано quick-create клієнта на сторінку списку"
    .\scripts\test-and-commit.ps1 -Push
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Message = '',

    [switch]$Push
)

$ErrorActionPreference = 'Stop'

# ---- Конфігурація ----
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$GitExe = "C:\Program Files\Git\bin\git.exe"
$PytestArgs = @('--tb=short', '-q')

# ---- Кольоровий вивід ----
function Write-Step($Text) {
    Write-Host "`n==> " -NoNewline -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor White
}

function Write-Success($Text) {
    Write-Host "  [✓] $Text" -ForegroundColor Green
}

function Write-Failure($Text) {
    Write-Host "  [✗] $Text" -ForegroundColor Red
}

function Write-Info($Text) {
    Write-Host "  [i] $Text" -ForegroundColor DarkYellow
}

# ---- Перевірка Git ----
if (-not (Test-Path -LiteralPath $GitExe)) {
    Write-Failure "Git не знайдено за шляхом: $GitExe"
    exit 1
}

if (-not (Test-Path -LiteralPath "$ProjectRoot\.git")) {
    Write-Failure "Це не Git-репозиторій. Виконайте 'git init' у корені проєкту."
    exit 1
}

# ---- 1. Запуск тестів ----
Write-Step "Крок 1: Запуск pytest..."

Set-Location -LiteralPath $ProjectRoot
$pytestOutput = & pytest @PytestArgs 2>&1
$pytestExitCode = $LASTEXITCODE

if ($pytestExitCode -ne 0) {
    Write-Failure "Тести НЕ пройдено (код: $pytestExitCode)"
    Write-Host "`n--- Вивід pytest ---" -ForegroundColor Yellow
    $pytestOutput | ForEach-Object { Write-Host $_ }
    Write-Host "--- Кінець виводу ---`n" -ForegroundColor Yellow
    exit $pytestExitCode
}

Write-Success "Усі тести пройдено!"

# ---- 2. Статус Git ----
Write-Step "Крок 2: Перевірка змін у Git..."

$status = & $GitExe -C $ProjectRoot status --porcelain
if (-not $status) {
    Write-Info "Немає змін для коміту."
    exit 0
}

Write-Info "Знайдено змінені файли:"
$status -split "`n" | ForEach-Object {
    if ($_.Trim()) { Write-Host "       $_" -ForegroundColor DarkYellow }
}

# ---- 3. Stage змін ----
Write-Step "Крок 3: Додавання файлів (git add)..."
& $GitExe -C $ProjectRoot add -A 2>&1 | Out-Null
Write-Success "Файли додано в індекс."

# ---- 4. Коміт ----
Write-Step "Крок 4: Створення коміту..."

if (-not $Message) {
    # Авто-генерація повідомлення: список змінених файлів
    $changedFiles = & $GitExe -C $ProjectRoot diff --cached --name-only 2>&1
    $fileList = $changedFiles -split "`n" | Where-Object { $_ -and $_.Trim() }
    
    $summary = @()
    $fileList | ForEach-Object {
        $ext = [System.IO.Path]::GetExtension($_)
        $dir = [System.IO.Path]::GetDirectoryName($_)
        switch ($ext) {
            '.py'    { $summary += "py:$dir" }
            '.html'  { $summary += "html:$dir" }
            '.js'    { $summary += "js:$dir" }
            '.css'   { $summary += "css:$dir" }
            '.ps1'   { $summary += "ps1:$dir" }
            '.md'    { $summary += "docs:$_" }
            default  { $summary += "misc:$_" }
        }
    }
    $uniqueSummary = $summary | Sort-Object -Unique
    $commitMsg = "chore: auto-commit after successful tests`n`nФайли: $($fileList -join ', ')"
} else {
    $commitMsg = $Message
}

& $GitExe -C $ProjectRoot commit -m $commitMsg 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Success "Коміт створено!"
    Write-Info "Повідомлення: $($commitMsg -split "`n" | Select-Object -First 1)"

    # ---- 5. Push (опціонально) ----
    if ($Push) {
        Write-Step "Крок 5: Відправка до віддаленого репозиторію (git push)..."
        
        $remoteUrl = & $GitExe -C $ProjectRoot remote get-url origin 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Failure "Віддалений репозиторій не налаштовано. Додайте його вручну:"
            Write-Host "       git remote add origin https://github.com/ВАШ_ЛОГІН/НАЗВА_РЕПО.git" -ForegroundColor Yellow
            exit 1
        }

        & $GitExe -C $ProjectRoot push 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Зміни відправлено до $remoteUrl"
        } else {
            Write-Failure "Помилка push. Можливо, потрібен GitHub Personal Access Token."
            exit 1
        }
    }
} else {
    Write-Failure "Помилка створення коміту."
    exit 1
}

Write-Host "`n" -NoNewline
Write-Success "Готово! Тести → коміт → успіх."
