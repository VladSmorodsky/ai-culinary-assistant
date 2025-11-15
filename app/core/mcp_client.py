from __future__ import annotations
import json, os, re, shlex
from typing import Any, Dict, List, Optional, Tuple, Protocol

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client  # type: ignore

class _ToolLike(Protocol):  # minimal structural type for tools returned by MCP
    name: str  # noqa: D401

def _norm_name(name: str) -> str:
    name = re.sub(r"\([^)]*\)", "", name)
    return re.sub(r"\s+", " ", name).strip().lower()

class MCPClient:
    def __init__(self):
        cmd = os.getenv("MCP_SERVER_CMD") or ""
        args_raw = os.getenv("MCP_SERVER_ARGS") or ""
        if not cmd:
            raise RuntimeError("MCP_SERVER_CMD is not set.")
        # Use shlex.split to respect quoted args
        args = shlex.split(args_raw)
        self.params = StdioServerParameters(command=cmd, args=args)
        self._nutrition_tool_name = os.getenv("NUTRITION_TOOL_NAME") or None
        self._map_tool_name = os.getenv("MAP_TOOL_NAME") or None
        self._dish_tool_name = os.getenv("DISH_INFO_TOOL_NAME") or None

    async def _find_tool(self, session: ClientSession, preferred: Optional[str], keywords: List[str]) -> str:
        tools: List[_ToolLike | Any] = await session.list_tools()  # type: ignore
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

    async def _open_session(self) -> Tuple[ClientSession, Any, Any]:
        """Open a stdio client session and return (session, read, write)."""
        ctx = stdio_client(self.params)
        read_write = await ctx.__aenter__()
        read, write = read_write
        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()
        # Package so caller can close properly
        return session, (ctx, session_cm), (read, write)

    async def _close_session(self, resources: Tuple[Any, Any]) -> None:
        ctx, session_cm = resources
        try:
            await session_cm.__aexit__(None, None, None)
        finally:
            await ctx.__aexit__(None, None, None)

    async def _call_json_tool(self, session: ClientSession, tool_name: str, payload: Dict[str, Any]) -> Any:
        """Call a tool expecting JSON output; try to parse first text item."""
        # Pass dict; mcp client will serialize as needed.
        res = await session.call_tool(tool_name, payload)  # type: ignore[arg-type]
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

    async def find_barcodes_for_names(self, names: List[str]) -> Dict[str, List[str]]:
        session, resources, _rw = await self._open_session()
        try:
            map_tool = await self._find_tool(session, self._map_tool_name, ["map", "barcode", "lookup"])
            out: Dict[str, List[str]] = {}
            for name in names:
                data = await self._call_json_tool(session, map_tool, {"query": name})
                barcodes: List[str] = []
                if isinstance(data, dict):
                    bs = data.get("barcodes") or data.get("codes") or []
                    if isinstance(bs, list):
                        barcodes = [str(b) for b in bs]
                elif isinstance(data, list):
                    barcodes = [str(x) for x in data]
                out[name] = barcodes
            return out
        finally:
            await self._close_session(resources)

    async def analyze_nutrition(self, barcodes: List[str]) -> Dict[str, Dict[str, Any]]:
        session, resources, _rw = await self._open_session()
        try:
            nutrition_tool = await self._find_tool(session, self._nutrition_tool_name, ["analyze", "nutrition"])
            results: Dict[str, Dict[str, Any]] = {}
            for code in barcodes:
                data = await self._call_json_tool(session, nutrition_tool, {"barcode": str(code)})
                product: Dict[str, Any] = {}
                nutrition: List[Dict[str, Any]] | List[Any] = []
                if isinstance(data, dict):
                    product = data.get("product") or data.get("item") or {}
                    nutrition = data.get("nutrition") or data.get("nutrients") or []
                elif isinstance(data, list):
                    nutrition = data
                results[str(code)] = {"product": product, "nutrition": nutrition}
            return results
        finally:
            await self._close_session(resources)

    async def get_dish_info(self, dish_name: str) -> Dict[str, Any]:
        """Attempt to retrieve dish info JSON from an MCP tool.
        Falls back to minimal structure if tool not available or returns invalid output.
        """
        session, resources, _rw = await self._open_session()
        try:
            tool = await self._find_tool(session, self._dish_tool_name, ["dish", "recipe", "info"])  # reuse heuristic
            data = await self._call_json_tool(session, tool, {"query": dish_name})
            if isinstance(data, dict):
                return data
            return {"dish_title": dish_name}
        finally:
            await self._close_session(resources)
