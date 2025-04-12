# Backup and Cleanup Script for IntegrationsAgentPOC
# This script archives directories and manages project cleanup

# Configuration
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveDir = Join-Path $projectRoot "archives"
$backupArchive = Join-Path $archiveDir "backup_$timestamp.zip"
$cleanupArchive = Join-Path $archiveDir "cleanup_$timestamp.zip"
$maxBackups = 5 # Maximum number of backups to keep

# Display banner
function Show-Banner {
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "║   IntegrationsAgentPOC Cleanup Utility                       ║" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

# Create archives directory if it doesn't exist
if (-not (Test-Path $archiveDir)) {
    Write-Host "Creating archives directory: $archiveDir"
    New-Item -Path $archiveDir -ItemType Directory | Out-Null
}

# Function to trim old archives
function Trim-Archives {
    param (
        [string]$Pattern,
        [int]$KeepCount
    )
    
    $files = Get-ChildItem -Path $archiveDir -Filter $Pattern | Sort-Object LastWriteTime -Descending
    
    if ($files.Count -gt $KeepCount) {
        Write-Host "Trimming old archives, keeping most recent $KeepCount..."
        $filesToDelete = $files | Select-Object -Skip $KeepCount
        
        foreach ($file in $filesToDelete) {
            Write-Host "  Removing old archive: $($file.Name)"
            Remove-Item -Path $file.FullName -Force
        }
    }
}

# Backup generated_scripts directory
$scriptsDir = Join-Path $projectRoot "generated_scripts"
if (Test-Path $scriptsDir) {
    $scriptsArchive = Join-Path $archiveDir "scripts_$timestamp.zip"
    Write-Host "Archiving generated scripts to: $scriptsArchive"
    Compress-Archive -Path $scriptsDir -DestinationPath $scriptsArchive -Force
}

# Archive the backup directory
$backupDir = Join-Path $projectRoot "backup"
if (Test-Path $backupDir) {
    Write-Host "Archiving backup directory to: $backupArchive"
    Compress-Archive -Path $backupDir -DestinationPath $backupArchive -Force
    
    # Remove the backup directory after archiving
    Write-Host "Removing backup directory: $backupDir"
    Remove-Item -Path $backupDir -Recurse -Force
    Write-Host "Backup directory removed successfully"
} else {
    Write-Host "Backup directory not found: $backupDir"
}

# Archive the cleanup directory
$cleanupDir = Join-Path $projectRoot "cleanup"
if (Test-Path $cleanupDir) {
    # First, extract any valuable documentation
    $cleanupDocsDir = Join-Path $cleanupDir "docs"
    $mainDocsDir = Join-Path $projectRoot "docs"
    
    if (Test-Path $cleanupDocsDir) {
        # Ensure main docs directory exists
        if (-not (Test-Path $mainDocsDir)) {
            New-Item -Path $mainDocsDir -ItemType Directory | Out-Null
        }
        
        # Copy documentation files from cleanup to main docs
        $refactoringDir = Join-Path $mainDocsDir "refactoring"
        if (-not (Test-Path $refactoringDir)) {
            New-Item -Path $refactoringDir -ItemType Directory | Out-Null
        }
        
        # Copy key documentation files
        Write-Host "Extracting valuable documentation from cleanup directory"
        $docsToPreserve = @(
            "REFACTORING.md",
            "IMPROVEMENTS.md",
            "CLEANUP.md",
            "FIXED.md"
        )
        
        foreach ($doc in $docsToPreserve) {
            $sourcePath = Join-Path $cleanupDocsDir $doc
            $destPath = Join-Path $refactoringDir $doc
            
            if (Test-Path $sourcePath) {
                Copy-Item -Path $sourcePath -Destination $destPath -Force
                Write-Host "  Copied: $doc to refactoring directory"
            }
        }
    }
    
    # Archive the cleanup directory
    Write-Host "Archiving cleanup directory to: $cleanupArchive"
    Compress-Archive -Path $cleanupDir -DestinationPath $cleanupArchive -Force
    
    # Remove the cleanup directory after archiving
    Write-Host "Removing cleanup directory: $cleanupDir"
    Remove-Item -Path $cleanupDir -Recurse -Force
    Write-Host "Cleanup directory removed successfully"
} else {
    Write-Host "Cleanup directory not found: $cleanupDir"
}

# Clean up temporary files
Write-Host "Cleaning up temporary files..."
$tempPatterns = @("*.tmp", "*.temp", "*.bak", "~*")
$tempCount = 0

foreach ($pattern in $tempPatterns) {
    $tempFiles = Get-ChildItem -Path $projectRoot -Recurse -File -Filter $pattern
    foreach ($file in $tempFiles) {
        Write-Host "  Removing temporary file: $($file.FullName)"
        Remove-Item -Path $file.FullName -Force
        $tempCount++
    }
}
Write-Host "Removed $tempCount temporary files"

# Remove Python cache files
Write-Host "Cleaning up Python cache files..."
$cachePatterns = @("__pycache__", "*.pyc", "*.pyo")
$cacheCount = 0

foreach ($pattern in $cachePatterns) {
    if ($pattern -eq "__pycache__") {
        $cacheDirs = Get-ChildItem -Path $projectRoot -Recurse -Directory -Filter $pattern
        foreach ($dir in $cacheDirs) {
            Write-Host "  Removing cache directory: $($dir.FullName)"
            Remove-Item -Path $dir.FullName -Recurse -Force
            $cacheCount++
        }
    } else {
        $cacheFiles = Get-ChildItem -Path $projectRoot -Recurse -File -Filter $pattern
        foreach ($file in $cacheFiles) {
            Write-Host "  Removing cache file: $($file.FullName)"
            Remove-Item -Path $file.FullName -Force
            $cacheCount++
        }
    }
}
Write-Host "Removed $cacheCount Python cache files/directories"

# Trim archives to keep only the recent ones
Trim-Archives -Pattern "backup_*.zip" -KeepCount $maxBackups
Trim-Archives -Pattern "cleanup_*.zip" -KeepCount $maxBackups
Trim-Archives -Pattern "scripts_*.zip" -KeepCount $maxBackups

# Update README in archives directory
$archiveReadmePath = Join-Path $archiveDir "README.md"
if (-not (Test-Path $archiveReadmePath)) {
    Write-Host "Creating README in archives directory..."
    $readmeContent = @"
# Archives Directory

This directory contains archived backups and cleanup files from previous versions.

## Purpose

The archives directory is used by the `cleanup_script.ps1` to store:
- **Backup archives**: Containing saved state from previous runs
- **Cleanup archives**: Containing removed code and files during refactoring
- **Scripts archives**: Containing generated scripts

## Retention Policy

By default, only the most recent $maxBackups archives of each type are kept.

*Note: This directory is excluded from version control.*
"@
    Set-Content -Path $archiveReadmePath -Value $readmeContent
}

Write-Host "`nCleanup completed successfully. Archives created:"
Write-Host "  - $backupArchive"
Write-Host "  - $cleanupArchive"
if (Test-Path $scriptsArchive) {
    Write-Host "  - $scriptsArchive"
}
Write-Host "`nImportant documentation has been preserved in: $refactoringDir"
Write-Host "`nArchives older than the most recent $maxBackups have been removed."
