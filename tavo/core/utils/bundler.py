import platform
from pathlib import Path
from typing import Optional

class BundlerNotFound(Exception):
    pass

def get_bundler_path() -> Path:
    """Return the path to the Rust bundler binary for the current platform."""
    system = platform.system().lower()
    if system == "windows":
        bin_name = "ssr-bundler.exe"
        target = "x86_64-pc-windows-msvc"
    elif system == "darwin":
        bin_name = "ssr-bundler"
        target = "x86_64-apple-darwin"
    elif system == "linux":
        bin_name = "ssr-bundler"
        target = "x86_64-unknown-linux-gnu"
    else:
        raise BundlerNotFound(f"Unsupported platform: {system}")

    bin_path = (
        Path(__file__).parent.parent.parent  # up from tavo/core/utils → project root
        / "rust_bundler"
        / "target"
        / target
        / "release"
        / bin_name
    )

    if not bin_path.exists():
        raise BundlerNotFound(f"Rust bundler not found at {bin_path}")

    return bin_path
