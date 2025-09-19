"""
SWC Installation and availability checking utilities
"""

import subprocess
import shutil
import os
import logging
from typing import Optional
from pathlib import Path

from .constants import DEFAULT_SWC_COMMAND

logger = logging.getLogger(__name__)


class SWCInstaller:
    """Manages SWC CLI installation and availability"""
    
    def __init__(self):
        self._swc_command: Optional[str] = None
        self._swc_available: Optional[bool] = None
        self._version_cache: Optional[str] = None
    
    def get_swc_command(self) -> str:
        """
        Get the SWC command to use
        
        Returns:
            SWC command path or name
        """
        if self._swc_command is None:
            # Check environment variable first
            env_command = os.getenv("TAVO_SWC_CMD")
            if env_command:
                self._swc_command = env_command
            else:
                # Look for swc in PATH
                swc_path = shutil.which("swc")
                if swc_path:
                    self._swc_command = swc_path
                else:
                    self._swc_command = DEFAULT_SWC_COMMAND
        
        return self._swc_command
    
    def ensure_swc_available(self) -> bool:
        """
        Check if SWC is available and working
        
        Returns:
            True if SWC is available, False otherwise
        """
        if self._swc_available is not None:
            return self._swc_available
        
        swc_command = self.get_swc_command()
        
        try:
            result = subprocess.run(
                [swc_command, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            
            version_output = result.stdout.strip()
            self._version_cache = version_output
            self._swc_available = True
            
            logger.debug(f"SWC is available: {version_output}")
            return True
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"SWC is not available: {e}")
            self._swc_available = False
            return False
    
    def get_version(self) -> Optional[str]:
        """
        Get SWC version if available
        
        Returns:
            Version string or None if not available
        """
        if self.ensure_swc_available():
            return self._version_cache
        return None
    
    def get_installation_instructions(self) -> str:
        """
        Get instructions for installing SWC
        
        Returns:
            Installation instructions as string
        """
        return """
SWC is not installed or not available in PATH.

To install SWC globally using npm:
    npm install -g @swc/cli @swc/core

To install SWC using yarn:
    yarn global add @swc/cli @swc/core

To install SWC using pnpm:
    pnpm add -g @swc/cli @swc/core

Alternative: Set TAVO_SWC_CMD environment variable to point to your SWC binary:
    export TAVO_SWC_CMD=/path/to/swc

For more information, visit: https://swc.rs/docs/usage/cli
""".strip()
    
    def check_and_raise_if_unavailable(self) -> None:
        """
        Check SWC availability and raise error with instructions if not available
        
        Raises:
            RuntimeError: If SWC is not available
        """
        if not self.ensure_swc_available():
            error_msg = f"SWC is required but not available.\n\n{self.get_installation_instructions()}"
            raise RuntimeError(error_msg)