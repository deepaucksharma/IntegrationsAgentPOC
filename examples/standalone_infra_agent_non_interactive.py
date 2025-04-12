"""
DEPRECATED: This file has been removed.

Please use standalone_infra_agent.py with the --non-interactive flag instead:
    python standalone_infra_agent.py --non-interactive --action=install
"""

import sys
import logging

logger = logging.getLogger(__name__)

def main():
    print("\n⚠️  DEPRECATED SCRIPT ⚠️")
    print("This script has been deprecated and will be removed in a future version.")
    print("Please use standalone_infra_agent.py with the --non-interactive flag instead:")
    print("    python standalone_infra_agent.py --non-interactive --action=install\n")
    return 1

if __name__ == "__main__":
    sys.exit(main())
