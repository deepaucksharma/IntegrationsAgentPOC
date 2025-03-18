import sys
import os
from workflow_agent.main import app

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Current directory: {os.getcwd()}")
print("\nTrying to run workflow agent...")

try:
    app(['install', 'infra_agent', '--license-key=test123', '--host=localhost'])
    print("Workflow agent ran successfully!")
except Exception as e:
    print(f"Error running workflow agent: {str(e)}")
    raise 