# PowerShell installation script
Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = "Stop"

# Import common macros
# PowerShell common macros



 
function Log-Message {
    param(
        [string]$Level,
        [string]$Message
    )
    Write-Host "[$([datetime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))] [$Level] $Message"
}

function Log-Info {
    param([string]$Message)
    Log-Message -Level "INFO" -Message $Message
}

function Log-Error {
    param([string]$Message)
    Write-Error "[$([datetime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))] [ERROR] $Message"
}

# Check prerequisites
function Check-Command {
    param([string]$Command)
    return [bool](Get-Command -Name $Command -ErrorAction SilentlyContinue)
}

Log-Info "Starting installation of infrastructure-agent..."

# Check required tools
if (-not (Check-Command "curl")) {
    Log-Error "Required tool not found: curl"
    exit 1
}
if (-not (Check-Command "wget")) {
    Log-Error "Required tool not found: wget"
    exit 1
}

# Installation steps
Log-Info "Executing installation steps..."
Log-Info "Executing: wget https://example.com/infra-agent/1.0.0/infra-agent"
try {
    Invoke-Expression "wget https://example.com/infra-agent/1.0.0/infra-agent"
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
} catch {
    Log-Error "Step failed: wget https://example.com/infra-agent/1.0.0/infra-agent"
    Log-Error $_.Exception.Message
    exit 1
}
Log-Info "Executing: chmod +x infra-agent"
try {
    Invoke-Expression "chmod +x infra-agent"
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
} catch {
    Log-Error "Step failed: chmod +x infra-agent"
    Log-Error $_.Exception.Message
    exit 1
}
Log-Info "Executing: ./infra-agent install --license-key test123 --host localhost --port 8080 --log-level INFO"
try {
    Invoke-Expression "./infra-agent install --license-key test123 --host localhost --port 8080 --log-level INFO"
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
} catch {
    Log-Error "Step failed: ./infra-agent install --license-key test123 --host localhost --port 8080 --log-level INFO"
    Log-Error $_.Exception.Message
    exit 1
}

# Verify installation
Log-Info "Verifying installation..."
Log-Info "Running verification step: curl -s http://localhost:8080/health"
try {
    Invoke-Expression "curl -s http://localhost:8080/health"
    if ($LASTEXITCODE -ne 0) {
        throw "Verification failed with exit code $LASTEXITCODE"
    }
} catch {
    Log-Error "Verification failed: curl -s http://localhost:8080/health"
    Log-Error $_.Exception.Message
    exit 1
}
Log-Info "Running verification step: infra-agent status"
try {
    Invoke-Expression "infra-agent status"
    if ($LASTEXITCODE -ne 0) {
        throw "Verification failed with exit code $LASTEXITCODE"
    }
} catch {
    Log-Error "Verification failed: infra-agent status"
    Log-Error $_.Exception.Message
    exit 1
}

# Check version if specified
Log-Info "Checking installed version..."
try {
    $installed_version = Invoke-Expression "infra-agent --version"
    if (-not ($installed_version -like "*1.0.0*")) {
        Log-Error "Version mismatch. Expected: 1.0.0, Got: $installed_version"
        exit 1
    }
} catch {
    Log-Error "Failed to check version"
    Log-Error $_.Exception.Message
    exit 1
}

Log-Info "Installation of infrastructure-agent completed successfully" 