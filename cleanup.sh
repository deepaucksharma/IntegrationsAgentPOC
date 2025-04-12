#!/bin/bash
# Cleanup script for Linux/Unix environments
# Provides similar functionality to cleanup_script.ps1 for non-Windows platforms

# Set up colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${BLUE}│                                                              │${NC}"
echo -e "${BLUE}│   IntegrationsAgentPOC Cleanup Utility                       │${NC}"
echo -e "${BLUE}│                                                              │${NC}"
echo -e "${BLUE}└──────────────────────────────────────────────────────────────┘${NC}"
echo ""

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$PROJECT_ROOT/archives"
BACKUP_ARCHIVE="$ARCHIVE_DIR/backup_$TIMESTAMP.tar.gz"
CLEANUP_ARCHIVE="$ARCHIVE_DIR/cleanup_$TIMESTAMP.tar.gz"
SCRIPTS_ARCHIVE="$ARCHIVE_DIR/scripts_$TIMESTAMP.tar.gz"
MAX_BACKUPS=5

# Create archives directory if it doesn't exist
if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "Creating archives directory: $ARCHIVE_DIR"
    mkdir -p "$ARCHIVE_DIR"
fi

# Trim old archives
trim_archives() {
    pattern=$1
    keep_count=$2
    
    # Get list of files sorted by modification time (newest first)
    files=($(ls -t $ARCHIVE_DIR/$pattern 2>/dev/null))
    
    if [ ${#files[@]} -gt $keep_count ]; then
        echo "Trimming old archives, keeping most recent $keep_count..."
        
        # Loop through files to delete (skip the first $keep_count)
        for ((i=$keep_count; i<${#files[@]}; i++)); do
            echo "  Removing old archive: ${files[$i]}"
            rm "${files[$i]}"
        done
    fi
}

# Archive generated scripts directory
SCRIPTS_DIR="$PROJECT_ROOT/generated_scripts"
if [ -d "$SCRIPTS_DIR" ]; then
    echo "Archiving generated scripts to: $SCRIPTS_ARCHIVE"
    tar -czf "$SCRIPTS_ARCHIVE" -C "$PROJECT_ROOT" generated_scripts
fi

# Archive backup directory
BACKUP_DIR="$PROJECT_ROOT/backup"
if [ -d "$BACKUP_DIR" ]; then
    echo "Archiving backup directory to: $BACKUP_ARCHIVE"
    tar -czf "$BACKUP_ARCHIVE" -C "$PROJECT_ROOT" backup
    
    # Remove backup directory
    echo "Removing backup directory: $BACKUP_DIR"
    rm -rf "$BACKUP_DIR"
    echo "Backup directory removed successfully"
else
    echo "Backup directory not found: $BACKUP_DIR"
fi

# Archive cleanup directory
CLEANUP_DIR="$PROJECT_ROOT/cleanup"
if [ -d "$CLEANUP_DIR" ]; then
    # Extract valuable documentation first
    CLEANUP_DOCS_DIR="$CLEANUP_DIR/docs"
    MAIN_DOCS_DIR="$PROJECT_ROOT/docs"
    
    if [ -d "$CLEANUP_DOCS_DIR" ]; then
        # Ensure main docs directory exists
        if [ ! -d "$MAIN_DOCS_DIR" ]; then
            mkdir -p "$MAIN_DOCS_DIR"
        fi
        
        # Create refactoring directory if needed
        REFACTORING_DIR="$MAIN_DOCS_DIR/refactoring"
        if [ ! -d "$REFACTORING_DIR" ]; then
            mkdir -p "$REFACTORING_DIR"
        fi
        
        # Copy important docs
        echo "Extracting valuable documentation from cleanup directory"
        for doc in REFACTORING.md IMPROVEMENTS.md CLEANUP.md FIXED.md; do
            if [ -f "$CLEANUP_DOCS_DIR/$doc" ]; then
                cp "$CLEANUP_DOCS_DIR/$doc" "$REFACTORING_DIR/$doc"
                echo "  Copied: $doc to refactoring directory"
            fi
        done
    fi
    
    # Archive cleanup directory
    echo "Archiving cleanup directory to: $CLEANUP_ARCHIVE"
    tar -czf "$CLEANUP_ARCHIVE" -C "$PROJECT_ROOT" cleanup
    
    # Remove cleanup directory
    echo "Removing cleanup directory: $CLEANUP_DIR"
    rm -rf "$CLEANUP_DIR"
    echo "Cleanup directory removed successfully"
else
    echo "Cleanup directory not found: $CLEANUP_DIR"
fi

# Clean up Python cache files
echo "Cleaning up Python cache files..."
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} +  2>/dev/null || true
find "$PROJECT_ROOT" -name "*.pyc" -delete
find "$PROJECT_ROOT" -name "*.pyo" -delete
echo "Python cache files removed"

# Clean up temporary files
echo "Cleaning up temporary files..."
find "$PROJECT_ROOT" -name "*.tmp" -delete
find "$PROJECT_ROOT" -name "*.temp" -delete
find "$PROJECT_ROOT" -name "*.bak" -delete
find "$PROJECT_ROOT" -name "*~" -delete
echo "Temporary files removed"

# Trim archives
trim_archives "backup_*.tar.gz" $MAX_BACKUPS
trim_archives "cleanup_*.tar.gz" $MAX_BACKUPS
trim_archives "scripts_*.tar.gz" $MAX_BACKUPS

# Create README in archives directory if it doesn't exist
ARCHIVE_README="$ARCHIVE_DIR/README.md"
if [ ! -f "$ARCHIVE_README" ]; then
    echo "Creating README in archives directory..."
    cat > "$ARCHIVE_README" << EOF
# Archives Directory

This directory contains archived backups and cleanup files from previous versions.

## Purpose

The archives directory is used by the cleanup scripts to store:
- **Backup archives**: Containing saved state from previous runs
- **Cleanup archives**: Containing removed code and files during refactoring
- **Scripts archives**: Containing generated scripts

## Retention Policy

By default, only the most recent $MAX_BACKUPS archives of each type are kept.

*Note: This directory is excluded from version control.*
EOF
fi

echo -e "\n${GREEN}Cleanup completed successfully. Archives created:${NC}"
[ -f "$BACKUP_ARCHIVE" ] && echo "  - $BACKUP_ARCHIVE"
[ -f "$CLEANUP_ARCHIVE" ] && echo "  - $CLEANUP_ARCHIVE"
[ -f "$SCRIPTS_ARCHIVE" ] && echo "  - $SCRIPTS_ARCHIVE"

if [ -d "$REFACTORING_DIR" ]; then
    echo -e "\n${GREEN}Important documentation has been preserved in: $REFACTORING_DIR${NC}"
fi

echo -e "\n${GREEN}Archives older than the most recent $MAX_BACKUPS have been removed.${NC}"

# Make the script executable
chmod +x "$PROJECT_ROOT/cleanup.sh"
