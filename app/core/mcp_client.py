from __future__ import annotations
import json
import os
import shlex
from typing import Any, Dict, List, Optional, Tuple, Protocol
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client  # type: ignore

try:
    from mcp.shared.exceptions import McpError  # type: ignore
except Exception:  # pragma: no cover

    class McpError(Exception):
        pass


class _ToolLike(Protocol):  # minimal structural type for tools returned by MCP
    name: str  # noqa: D401


class MCPClient:
    def __init__(self):
        cmd = os.getenv("MCP_SERVER_CMD") or ""
        args_raw = os.getenv("MCP_SERVER_ARGS") or ""
        if not cmd:
            raise RuntimeError("MCP_SERVER_CMD is not set.")
        # Use shlex.split to respect quoted args
        args = shlex.split(args_raw)
        # Pass current environment to subprocess so it inherits credentials
        self.params = StdioServerParameters(
            command=cmd, args=args, env=dict(os.environ)
        )
        self._nutrition_tool_name = os.getenv("NUTRITION_TOOL_NAME") or None
        self._map_tool_name = os.getenv("MAP_TOOL_NAME") or None
        self._dish_tool_name = os.getenv("DISH_INFO_TOOL_NAME") or None

    async def _find_tool(
        self, session: ClientSession, preferred: Optional[str], keywords: List[str]
    ) -> str:
        try:
            # type: ignore
            tools_result = await session.list_tools()
            # Extract the tools list from the result object
            tools: List[_ToolLike | Any] = getattr(
                tools_result,
                "tools",
                tools_result if isinstance(tools_result, list) else [],
            )
        except Exception as e:
            # If listing fails but preferred provided, fallback to preferred name directly
            if preferred:
                return preferred
            raise RuntimeError(f"Failed to list MCP tools: {e}")
        if preferred:
            for t in tools:
                t_name = getattr(t, "name", None)
                if t_name == preferred:
                    return t_name
        for t in tools:
            t_name = getattr(t, "name", "")
            low = t_name.lower()
            if any(k in low for k in keywords):
                return t_name
        if not tools:
            raise RuntimeError("No MCP tools available.")
        first_name = getattr(tools[0], "name", None)
        if not first_name:
            raise RuntimeError("Tools returned without 'name' attribute.")
        return first_name

    @asynccontextmanager
    async def _session(self) -> Any:
        """Async context manager yielding an initialized ClientSession.

        This replaces manual __aenter__/__aexit__ calls to avoid mismatched
        cancel scope exits inside anyio's task groups.
        """
        async with stdio_client(self.params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def _call_json_tool(
        self, session: ClientSession, tool_name: str, payload: Dict[str, Any]
    ) -> Any:
        """Call a tool expecting JSON output; try to parse first text item. Return None on any failure."""
        try:
            # type: ignore[arg-type]
            res = await session.call_tool(tool_name, payload)
        except Exception:
            return None
        content = getattr(res, "content", None)
        if not content:
            return None
        try:
            if isinstance(content, list) and content:
                txt = getattr(content[0], "text", None)
                if txt:
                    return json.loads(txt)
        except Exception:
            return None
        return None

    async def get_nutrition_for_ingredients(
        self, ingredients: List[str]
    ) -> Dict[str, Any]:
        """Get nutrition information for ingredients using Edamam API via MCP.

        Args:
            ingredients: List of ingredient names with quantities (e.g., ['1 cup rice', 'medium apple'])

        Returns:
            Dict with structure: {"ingredients": [...], "total_count": N}
            Each ingredient has: {"ingredient": str, "calories": float, "nutrients": {...}}
        """
        async with self._session() as session:
            try:
                try:
                    tool = await self._find_tool(
                        session,
                        self._nutrition_tool_name,
                        ["nutrition", "ingredient", "edamam"],
                    )
                except Exception:
                    return {"ingredients": [], "total_count": 0}

                data = await self._call_json_tool(
                    session, tool, {"ingredients": ingredients}
                )
                if isinstance(data, dict):
                    return data
                return {"ingredients": [], "total_count": 0}
            except (McpError, RuntimeError):
                return {"ingredients": [], "total_count": 0}
