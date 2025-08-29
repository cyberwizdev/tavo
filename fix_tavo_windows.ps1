# fix_tavo_windows.ps1 - Windows PowerShell version of the Tavo installation fix

Write-Host "🚀 Starting Tavo installation fix for Windows..." -ForegroundColor Green
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Cyan

# Step 1: Clean __pycache__ directories
Write-Host "🧹 Cleaning __pycache__ directories..." -ForegroundColor Yellow
Get-ChildItem -Path . -Name "__pycache__" -Recurse -Directory | ForEach-Object {
    $path = Join-Path (Get-Location) $_
    Write-Host "   Removing $path" -ForegroundColor Gray
    Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
}

# Step 2: Clean .pyc files
Write-Host "🧹 Cleaning .pyc files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Name "*.pyc" -Recurse -File | ForEach-Object {
    $path = Join-Path (Get-Location) $_
    Write-Host "   Removing $path" -ForegroundColor Gray
    Remove-Item $path -Force -ErrorAction SilentlyContinue
}

# Step 3: Clean build directories
Write-Host "🧹 Cleaning build directories..." -ForegroundColor Yellow
$buildDirs = @("build", "dist")
$buildDirs | ForEach-Object {
    if (Test-Path $_) {
        Write-Host "   Removing $_" -ForegroundColor Gray
        Remove-Item $_ -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Clean .egg-info directories
Get-ChildItem -Path . -Name "*.egg-info" -Directory | ForEach-Object {
    Write-Host "   Removing $_" -ForegroundColor Gray
    Remove-Item $_ -Recurse -Force -ErrorAction SilentlyContinue
}

# Step 4: Check package structure
Write-Host "📁 Checking package structure..." -ForegroundColor Yellow
$requiredFiles = @(
    "tavo\__init__.py",
    "tavo\cli\__init__.py", 
    "tavo\core\__init__.py",
    "pyproject.toml"
)

$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host "❌ Missing required files: $($missingFiles -join ', ')" -ForegroundColor Red
    Write-Host "Please ensure these files exist before continuing." -ForegroundColor Red
    exit 1
} else {
    Write-Host "✅ All required files present" -ForegroundColor Green
}

# Step 5: Check and fix __init__.py files
Write-Host "📝 Checking __init__.py files..." -ForegroundColor Yellow

# Main tavo/__init__.py
$mainInit = @'
"""
🚀 Tavo - Modern full-stack framework CLI

Tavo combines:
- ⚡ Python backend (Starlette base)  
- 🦀 Rust + SWC powered SSR for React (with App Router support)  
- 🔥 Client hydration & HMR with no Node.js required  
- 🛠️ CLI scaffolding for apps, routes, components, and APIs  
"""

__version__ = "0.1.0"
__author__ = "CyberwizDev"

# Import main components for easier access
try:
    from .core.bundler import Bundler
    from .core.ssr import SSRRenderer
    from .core.router.app_router import AppRouter
    from .core.router.api_router import APIRouter
    from .core.orm.models import Model
    from .core.orm.fields import Field, CharField, IntegerField, DateTimeField

    __all__ = [
        "Bundler",
        "SSRRenderer", 
        "AppRouter",
        "APIRouter",
        "Model",
        "Field",
        "CharField",
        "IntegerField", 
        "DateTimeField",
    ]
except ImportError:
    # During development, some modules might not be complete
    __all__ = []
'@

# Check if tavo/__init__.py needs updating
$tavoInit = "tavo\__init__.py"
if (-not (Test-Path $tavoInit) -or (Get-Content $tavoInit -Raw).Length -lt 100) {
    Write-Host "   Fixing tavo\__init__.py" -ForegroundColor Gray
    $mainInit | Out-File -FilePath $tavoInit -Encoding utf8
}

# Step 6: Uninstall existing installation
Write-Host "🗑️ Uninstalling existing tavo..." -ForegroundColor Yellow
pip uninstall tavo -y 2>$null

# Step 7: Upgrade pip and build tools
Write-Host "⬆️ Upgrading pip and build tools..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel build

# Step 8: Install in editable mode
Write-Host "📦 Installing tavo in editable mode..." -ForegroundColor Yellow
$installResult = pip install -e . 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Installation successful!" -ForegroundColor Green
} else {
    Write-Host "❌ Editable install failed. Output:" -ForegroundColor Red
    Write-Host $installResult -ForegroundColor Red
    
    Write-Host "Trying alternative installation method..." -ForegroundColor Yellow
    python -m build
    if (Test-Path "setup.py") {
        python setup.py develop
    }
}

# Step 9: Verify installation
Write-Host "🧪 Verifying installation..." -ForegroundColor Yellow

# Check pip list
$pipList = pip list | Select-String "tavo"
if ($pipList) {
    Write-Host "✅ Tavo found in pip list: $pipList" -ForegroundColor Green
} else {
    Write-Host "⚠️ Tavo not found in pip list" -ForegroundColor Red
}

# Test import
Write-Host "Testing import..." -ForegroundColor Cyan
$testImport = python -c "
try:
    import tavo
    print('✅ Successfully imported tavo')
    print(f'📍 Location: {tavo.__file__}')
    print(f'🏷️ Version: {tavo.__version__}')
    exit(0)
except ImportError as e:
    print(f'❌ Import failed: {e}')
    exit(1)
" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $testImport -ForegroundColor Green
    
    # Test CLI
    Write-Host "Testing CLI..." -ForegroundColor Cyan
    $cliTest = tavo --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ CLI is working!" -ForegroundColor Green
    } else {
        Write-Host "⚠️ CLI not working, but package is importable" -ForegroundColor Yellow
        Write-Host "CLI error: $cliTest" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "🎉 Installation completed successfully!" -ForegroundColor Green
    Write-Host "You can now use:" -ForegroundColor Cyan
    Write-Host "  import tavo" -ForegroundColor White
    Write-Host "  tavo --help" -ForegroundColor White
    
} else {
    Write-Host $testImport -ForegroundColor Red
    Write-Host ""
    Write-Host "❌ Installation verification failed." -ForegroundColor Red
    Write-Host "Please check the errors above." -ForegroundColor Red
}

Write-Host ""
Write-Host "Fix script completed." -ForegroundColor Green