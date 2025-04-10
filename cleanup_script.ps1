# Backup and Cleanup Script for IntegrationsAgentPOC
# This script archives backup and cleanup directories and removes them from the project

# Configuration
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveDir = Join-Path $projectRoot "archives"
$backupArchive = Join-Path $archiveDir "backup_$timestamp.zip"
$cleanupArchive = Join-Path $archiveDir "cleanup_$timestamp.zip"

# Create archives directory if it doesn't exist
if (-not (Test-Path $archiveDir)) {
    Write-Host "Creating archives directory: $archiveDir"
    New-Item -Path $archiveDir -ItemType Directory | Out-Null
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

Write-Host "`nCleanup completed successfully. Archives created:"
Write-Host "  - $backupArchive"
Write-Host "  - $cleanupArchive"
Write-Host "`nImportant documentation has been preserved in: $refactoringDir"
