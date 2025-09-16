"""
SWC Installation Manager

Handles global installation of @swc/cli and @swc/core packages.
"""

import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SWCInstaller:
    """Manages SWC installation and verification"""
    
    def __init__(self):
        self.required_packages = ["@swc/cli", "@swc/core"]
    
    def is_npm_available(self) -> bool:
        """Check if npm is available in the system"""
        return shutil.which("npm") is not None
    
    def is_swc_installed(self) -> bool:
        """Check if SWC CLI is globally installed and accessible"""

        try:
            result = subprocess.run(
                ["swc", "--version"],
                capture_output=True,
                text=True,
                shell=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def install_swc_globally(self) -> bool:
        """Install SWC CLI and Core globally using npm"""
        if not self.is_npm_available():
            logger.error("npm is not available. Please install Node.js and npm first.")
            return False
        
        logger.info("Installing SWC CLI and Core globally...")
        
        try:
            # Install both packages globally
            cmd = ["npm", "install", "-g"] + self.required_packages
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=120  # 2 minutes timeout for installation
            )
            
            if result.returncode == 0:
                logger.info("SWC installed successfully")
                return True
            else:
                logger.error(f"SWC installation failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("SWC installation timed out")
            return False
        except Exception as e:
            logger.error(f"Error installing SWC: {e}")
            return False
    
    def ensure_swc_available(self) -> bool:
        """Ensure SWC is available, install if necessary"""
        if self.is_swc_installed():
            logger.info("SWC is already installed and available")
            return True
        
        logger.info("SWC not found, attempting to install...")
        return self.install_swc_globally()
    
    def get_swc_command(self) -> Optional[str]:
        """Get the appropriate SWC command to use"""
        if self.is_swc_installed():
            return "swc"
        return None


if __name__ == "__main__":
    installer = SWCInstaller()
    if installer.ensure_swc_available():
        print("SWC is ready to use.")
    else:
        print("Failed to ensure SWC is available.")