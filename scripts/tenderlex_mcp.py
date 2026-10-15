#!/usr/bin/env python3
"""
TenderLex MCP CLI Runner.
Usage:
    export TENDERLEX_API_KEY="tl_admin_..."
    python scripts/tenderlex_mcp.py
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mcp_server.server import main

if __name__ == "__main__":
    main()
