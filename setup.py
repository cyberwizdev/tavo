from setuptools import setup, find_packages
from pathlib import Path
import io
import os

# Rust support
from setuptools_rust import RustBin

here = Path(__file__).parent
readme = io.open(here / "README.md", encoding="utf-8").read()

setup(
    name="tavo",
    version="0.1.23",
    author="Hallel",
    author_email="admin@cyberwizdev.com.ng",
    description="Tavo full-stack framework CLI - Python backend + Rust/SWC React SSR",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/cyberwizdev/tavo",
    license="MIT",
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Rust",
        "Framework :: AsyncIO",
        "Framework :: FastAPI",
        "Operating System :: OS Independent",
    ],

    # Python packages
    packages=find_packages(include=["tavo_cli", "tavo_core", "tavo_cli.*", "tavo_core.*"]),
    include_package_data=True,
    package_data={
        # ship scaffolding/templates/static with the core
        "tavo_core": [
            "templates/**",
            "static/**",
            "frontend/**",
        ],
    },
    exclude_package_data={"": ["*.pyc", "__pycache__", "*.pyo"]},

    # Runtime deps
    install_requires=[
        "anyio>=4.0.0",
        "certifi>=2025.0.0",
        "charset-normalizer>=3.0.0",
        "click>=8.0.0",
        "colorama>=0.4.0",
        "idna>=3.0.0",
        "markdown-it-py>=3.0.0",
        "mdurl>=0.1.0",
        "Pygments>=2.0.0",
        "python-dotenv>=1.0.0",
        "requests>=2.0.0",
        "rich>=13.0.0",
        "shellingham>=1.0.0",
        "sniffio>=1.0.0",
        "starlette>=0.47.0",
        "typer>=0.15.0",
        "typing_extensions>=4.0.0",
        "urllib3>=2.0.0",
        "watchfiles>=1.0.0",
        "websockets>=14.0.0",
    ],

    # Python CLI entrypoint
    entry_points={
        "console_scripts": [
            "tavo=tavo_cli.main:main",
        ],
    },

    # Build + install the Rust binary crate into the wheel
    rust_extensions=[],  # none (we're not building a Python extension module)
    rust_binaries=[
        # target must match [[bin]] name in rust_bundler/Cargo.toml
        RustBin(
            target="rust_bundler",
            path="rust_bundler/Cargo.toml",   # path to the crate manifest
            # args=["--locked"],               # (optional) extra cargo args
            # strip is automatic in release; wheels are built in release mode
        )
    ],

    project_urls={
        "Homepage": "https://github.com/cyberwizdev/tavo",
        "Bug Tracker": "https://github.com/cyberwizdev/tavo/issues",
    },
)
