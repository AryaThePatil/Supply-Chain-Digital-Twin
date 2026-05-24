# Safe Project Cleanup Script
# Run this to preview what will be deleted (dry-run mode)

# IMPORTANT: This script is CONSERVATIVE and SAFE
# It ONLY deletes files that Python regenerates automatically

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "FYP_Dynamic Project Cleanup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$projectRoot = "C:\Users\aryap\OneDrive\Desktop\Arya_College\FYP_Dynamic\FYP"

Write-Host "🔍 Scanning for cache files...`n" -ForegroundColor Yellow

# Count items to be deleted
$pycacheCount = (Get-ChildItem -Path $projectRoot -Include __pycache__ -Recurse -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
$pycFiles = Get-ChildItem -Path $projectRoot -Filter *.pyc -Recurse -File -ErrorAction SilentlyContinue
$pycCount = ($pycFiles | Measure-Object).Count
$pycSize = ($pycFiles | Measure-Object -Property Length -Sum).Sum / 1MB

Write-Host "Found:" -ForegroundColor White
Write-Host "  - $pycacheCount __pycache__ directories" -ForegroundColor Gray
Write-Host "  - $pycCount .pyc files (~$([math]::Round($pycSize, 2)) MB)" -ForegroundColor Gray

Write-Host "`n⚠️  SAFETY NOTES:" -ForegroundColor Yellow
Write-Host "  ✅ These are Python cache files (100% safe to delete)" -ForegroundColor Green
Write-Host "  ✅ They regenerate automatically when you run Python" -ForegroundColor Green
Write-Host "  ✅ Deleting them will NOT break your code" -ForegroundColor Green
Write-Host "  ✅ Your source code will NOT be affected" -ForegroundColor Green

Write-Host "`n📋 What will be deleted:" -ForegroundColor White
Write-Host "  - All __pycache__ folders" -ForegroundColor Gray
Write-Host "  - All .pyc compiled files" -ForegroundColor Gray

Write-Host "`n❌ What will NOT be touched:" -ForegroundColor White
Write-Host "  - Your source code (.py files)" -ForegroundColor Gray
Write-Host "  - Configuration files" -ForegroundColor Gray
Write-Host "  - Log files (we'll ask separately)" -ForegroundColor Gray
Write-Host "  - Data files" -ForegroundColor Gray
Write-Host "  - Any other project files" -ForegroundColor Gray

Write-Host "`n========================================`n" -ForegroundColor Cyan

$confirm = Read-Host "Delete Python cache files? (yes/no)"

if ($confirm -eq "yes") {
    Write-Host "`n🗑️  Deleting cache files..." -ForegroundColor Yellow
    
    # Delete __pycache__ directories
    $deleted = 0
    Get-ChildItem -Path $projectRoot -Include __pycache__ -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force
        $deleted++
        Write-Host "  ✓ Deleted: $($_.FullName)" -ForegroundColor Gray
    }
    
    # Delete .pyc files
    Get-ChildItem -Path $projectRoot -Filter *.pyc -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_.FullName -Force
        $deleted++
    }
    
    Write-Host "`n✅ Cleanup complete!" -ForegroundColor Green
    Write-Host "   Deleted: $deleted items" -ForegroundColor Gray
    Write-Host "   Freed: ~$([math]::Round($pycSize, 2)) MB" -ForegroundColor Gray
    
} else {
    Write-Host "`n❌ Cleanup cancelled. No files were deleted." -ForegroundColor Yellow
}

Write-Host "`n========================================`n" -ForegroundColor Cyan
