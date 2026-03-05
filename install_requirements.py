"""
Install all required dependencies for TikTok Video Creator.

Usage:
    python install_requirements.py

This script installs all packages from requirements.txt using pip.
"""
import subprocess
import sys
import os


def main():
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")

    if not os.path.exists(req_file):
        print("ERROR: requirements.txt not found!")
        sys.exit(1)

    print("=" * 50)
    print("  TikTok Video Creator - Installing Dependencies")
    print("=" * 50)
    print()
    print(f"Using Python: {sys.executable}")
    print(f"Reading: {req_file}")
    print()

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
        check=False,
    )

    print()
    if result.returncode == 0:
        print("All dependencies installed successfully!")
    else:
        print("Some dependencies failed to install.")
        print("If PyTorch failed, install it manually first:")
        print()
        print("  RTX 5070/5080/5090 (Blackwell):")
        print("    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu130")
        print()
        print("  RTX 4060/4070/4080/4090 (Ada Lovelace):")
        print("    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
        print()
        print("  Then run this script again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
