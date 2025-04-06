"""
Redirects to enhanced recovery manager.
This module is maintained for backward compatibility.
New code should use recovery.manager directly.
"""

# Re-export RecoveryManager from the enhanced implementation
from ..recovery.manager import RecoveryManager

# For backward compatibility
from ..recovery.manager import RecoveryStrategy
