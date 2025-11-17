#!/usr/bin/env python3
"""Wrapper script to launch the Nutrition MCP server when passed as part of MCP_SERVER_ARGS.

Environment example:
  MCP_SERVER_CMD=python
  MCP_SERVER_ARGS="app/core/mcp_server_wrapper.py python app/core/nutrition_mcp_server.py"

This wrapper will exec the remaining arguments (python app/core/nutrition_mcp_server.py)
so that the nutrition_mcp_server runs as the actual subprocess for stdio communication.
If no extra arguments are provided it will attempt to import and run the server's main().
"""
from __future__ import annotations
import os
import sys
import subprocess


def main() -> None:
    if len(sys.argv) > 1:
        # Remaining args represent the actual command to run (e.g., python app/core/nutrition_mcp_server.py)
        cmd = sys.argv[1:]
        # Replace current process with target command for proper stdio piping
        os.execvp(cmd[0], cmd)
    else:
        # Fallback: import and run server directly
        try:
            from app.core.nutrition_mcp_server import main as server_main  # type: ignore
            import asyncio
            asyncio.run(server_main())
        except Exception as e:  # pragma: no cover
            print(f"Wrapper fallback failed to start server: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

