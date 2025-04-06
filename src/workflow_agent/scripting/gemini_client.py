"""Google Gemini LLM client implementation."""
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Try to import the google.generativeai module
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except ImportError:
    HAVE_GENAI = False
    logger.warning("Google Generative AI package not found. Using mock implementation.")

from ..error.exceptions import ScriptError

class GeminiClient:
    """Client for interacting with Google's Gemini LLM."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini client."""
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = None
        
        if not self.api_key:
            logger.warning("Gemini API key not provided, creating mock client")
            # Don't raise an error, just create a mock client
            return
            
        if not HAVE_GENAI:
            logger.warning("Google Generative AI package not available, creating mock client")
            return
            
        # Configure the Gemini client
        try:
            genai.configure(api_key=self.api_key)
            
            # List available models
            models = genai.list_models()
            model_name = None
            
            # First try to find gemini-1.5-flash
            for model in models:
                if "gemini-1.5-flash" in model.name.lower():
                    model_name = model.name
                    break
            
            # If not found, try any gemini model
            if not model_name:
                for model in models:
                    if "gemini" in model.name.lower():
                        model_name = model.name
                        break
            
            if not model_name:
                logger.warning("No Gemini model found, creating mock client")
                return
            
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Using Gemini model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {str(e)}")
            # Don't raise an error, just create a mock client
    
    async def generate_script(
        self,
        system_prompt: str,
        user_prompt: str,
        template_content: Optional[str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Generate a script using Gemini or return a mock response if not available."""
        try:
            # Check if we have a working model
            if not HAVE_GENAI or not self.model:
                logger.warning("Using mock generation since Gemini is not available")
                return self._generate_mock_script(system_prompt, user_prompt, template_content)
                
            # Combine prompts
            combined_prompt = f"{system_prompt}\n\nTemplate reference:\n{template_content}\n\nUser request:\n{user_prompt}"
            
            # Generate response with retries
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(combined_prompt)
                    
                    if not response.text:
                        if attempt < max_retries - 1:
                            logger.warning(f"Empty response from Gemini (attempt {attempt + 1}/{max_retries})")
                            continue
                        return {"error": "Gemini returned empty response"}
                    
                    # Extract the script from the response
                    script = response.text
                    if "```" in script:
                        # Extract code from markdown code blocks if present
                        code_blocks = script.split("```")
                        if len(code_blocks) >= 3:  # At least one complete code block
                            code_block = code_blocks[1].strip()
                            # Remove language identifier if present
                            if code_block.startswith(("bash", "powershell", "sh", "python")):
                                code_block = code_block.split("\n", 1)[1]
                            script = code_block
                    
                    return {"script": script}
                
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Gemini generation failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        continue
                    raise
            
            return {"error": "Failed to generate script after all retries"}
        
        except Exception as e:
            logger.error(f"Error in Gemini script generation: {str(e)}", exc_info=True)
            return {"error": f"Gemini generation error: {str(e)}"} 
            
    def _generate_mock_script(
        self,
        system_prompt: str,
        user_prompt: str,
        template_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a mock script when Gemini is not available."""
        logger.info("Generating mock script since Gemini is not available")
        
        # Generate a simple script based on the user prompt
        if "windows" in system_prompt.lower() or "powershell" in system_prompt.lower():
            # Generate a PowerShell script
            script = """# Mock PowerShell script generated when Gemini was not available
$ErrorActionPreference = "Stop"

# Log start of script
Write-Host "Starting script execution..."

# Main function
function Main {
    Write-Host "Running main functionality"
    
    # Check prerequisites
    if (!(Test-Prerequisites)) {
        Write-Error "Prerequisites check failed"
        exit 1
    }
    
    # Perform installation
    Install-Components
    
    # Verify installation
    if (!(Verify-Installation)) {
        Write-Error "Verification failed"
        exit 1
    }
    
    Write-Host "Script completed successfully"
}

function Test-Prerequisites {
    Write-Host "Checking prerequisites..."
    return $true
}

function Install-Components {
    Write-Host "Installing components..."
    # This would normally contain installation code
}

function Verify-Installation {
    Write-Host "Verifying installation..."
    return $true
}

# Run the main function
try {
    Main
    exit 0
} catch {
    Write-Error "Error: $_"
    exit 1
}
"""
        else:
            # Generate a Bash script
            script = """#!/bin/bash
# Mock Bash script generated when Gemini was not available
set -e

# Log start of script
echo "Starting script execution..."

# Function to check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."
    return 0
}

# Function to install components
install_components() {
    echo "Installing components..."
    # This would normally contain installation code
}

# Function to verify installation
verify_installation() {
    echo "Verifying installation..."
    return 0
}

# Main function
main() {
    echo "Running main functionality"
    
    # Check prerequisites
    if ! check_prerequisites; then
        echo "Prerequisites check failed"
        exit 1
    fi
    
    # Perform installation
    install_components
    
    # Verify installation
    if ! verify_installation; then
        echo "Verification failed"
        exit 1
    fi
    
    echo "Script completed successfully"
}

# Run the main function with error handling
{
    main
    exit 0
} || {
    echo "Script failed with error: $?"
    exit 1
}
"""
        
        return {"script": script}
