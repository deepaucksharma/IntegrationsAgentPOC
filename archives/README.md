# Archives Directory

This directory contains archived backups and cleanup files from previous versions.

## Purpose

The archives directory is used by the `cleanup_script.ps1` to store:
- **Backup archives**: Containing saved state from previous runs
- **Cleanup archives**: Containing removed code and files during refactoring

## Contents

Archives are timestamped with format `{type}_{yyyyMMdd_HHmmss}.zip` to maintain clear versioning.

## Retention Policy

By default, there is no automatic pruning of old archives. Consider implementing a retention policy that:
1. Keeps the most recent 5 archives of each type
2. Keeps monthly archives for the past year
3. Removes archives older than one year

## Usage

Archives can be accessed using standard ZIP tools. To restore files from an archive:

1. Extract the ZIP file to a temporary location
2. Copy the needed files to the appropriate location in the project
3. Verify the restored files work as expected

## Notes

- This directory is excluded from version control via `.gitignore`
- Manual cleanup may be needed periodically to save disk space
- Do not store sensitive information (e.g., API keys, credentials) in these archives
