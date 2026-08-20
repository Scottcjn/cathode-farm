#!/usr/bin/env python3
"""mac-farm MCP — drive the 1994 emulated-Mac render farm as Claude tools.

Each node runs a patched Basilisk II with an ADB-layer control server (see
github.com/Scottcjn/cathode-farm). This exposes screenshot + reliable input
(click / double-click / key / Command-key / type / menu-pick) over MCP.
"""
import socket, subprocess, tempfile, os, base64, time
try:  # mcp >= 2.0.0 removed mcp.server.fastmcp; FastMCP was renamed
    # MCPServer and moved to mcp.server.mcpserver. Same .tool()/.run() API.
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
try:  # Image's home under mcp 2.x is unverified here; try the new
    # module first and fall back, so FastMCP resolving is never
    # coupled to Image resolving.
    from mcp.server.mcpserver import Image
except ImportError:
    from mcp.server.fastmcp import Image

mcp = FastMCP("mac-farm")

# node -> how to reach its control socket + how to grab its framebuffer
NODES = {
    "host":    {"port": 6560, "kind": "host",   "display": ":81"},
    "alpha":   {"port": 6561, "kind": "docker",  "container": "mac-alpha"},
    "bravo":   {"port": 6562, "kind": "docker",  "container": "mac-bravo"},
    "charlie": {"port": 6563, "kind": "docker",  "container": "mac-charlie"},
}
# Mac ADB key codes for convenience
KEYS = {"return": 36, "cmd": 55, "shift": 56, "space": 49, "esc": 53, "tab": 48,
        "o": 31, "w": 13, "a": 0, "q": 12, "s": 1, "n": 45, "period": 47}

def _send(node: str, line: str) -> str:
    n = NODES[node]
    with socket.create_connection(("127.0.0.1", n["port"]), timeout=5) as s:
        s.sendall((line + "\n").encode())
        s.settimeout(3)
        try: return s.recv(64).decode().strip()
        except socket.timeout: return "sent"

def _keycode(k):
    if isinstance(k, int): return k
    if str(k).isdigit(): return int(k)
    return KEYS.get(str(k).lower(), 0)

@mcp.tool()
def mac_nodes() -> str:
    """List farm nodes and whether each control server is reachable."""
    out = []
    for name, n in NODES.items():
        try:
            socket.create_connection(("127.0.0.1", n["port"]), timeout=2).close()
            state = "reachable"
        except OSError:
            state = "DOWN"
        out.append(f"{name}: ctl 127.0.0.1:{n['port']} ({n['kind']}) -> {state}")
    return "\n".join(out)

@mcp.tool()
def mac_screenshot(node: str = "host") -> Image:
    """Screenshot a node's Macintosh screen. node = host|alpha|bravo|charlie."""
    n = NODES[node]; p = tempfile.mktemp(suffix=".png")
    if n["kind"] == "host":
        subprocess.run(f"DISPLAY={n['display']} xwd -root -silent | convert xwd:- {p}",
                       shell=True, check=True)
    else:
        subprocess.run(["docker", "exec", n["container"], "sh", "-c",
                        "DISPLAY=:99 xwd -root -silent | convert xwd:- /tmp/mcp.png"], check=True)
        subprocess.run(["docker", "cp", f"{n['container']}:/tmp/mcp.png", p], check=True)
    return Image(path=p)

@mcp.tool()
def mac_click(node: str, x: int, y: int, double: bool = False) -> str:
    """Click (or double-click) at Mac screen coords x,y on a node."""
    return _send(node, f"{'dc' if double else 'c'} {x} {y}")

@mcp.tool()
def mac_move(node: str, x: int, y: int) -> str:
    """Move the Mac mouse to x,y (no click)."""
    return _send(node, f"m {x} {y}")

@mcp.tool()
def mac_key(node: str, key: str) -> str:
    """Press a key by name (return, cmd, o, w...) or Mac ADB code number."""
    return _send(node, f"k {_keycode(key)}")

@mcp.tool()
def mac_cmd_key(node: str, key: str) -> str:
    """Hold Command and press a key (e.g. Cmd+O to open, Cmd+A select-all)."""
    return _send(node, f"cmd {_keycode(key)}")

@mcp.tool()
def mac_type(node: str, text: str) -> str:
    """Type an ASCII string into the focused Mac field."""
    return _send(node, f"t {text}")

@mcp.tool()
def mac_menu_pick(node: str, title_x: int, item_x: int, item_y: int) -> str:
    """Pick a Mac menu item: press the menu title (title_x, y=9), drag to the
    item (item_x,item_y), release. Handles the press-drag-release menus need."""
    _send(node, f"m {title_x} 9"); time.sleep(0.2)
    _send(node, "d"); time.sleep(0.4)
    _send(node, f"m {item_x} {item_y}"); time.sleep(0.3)
    return _send(node, "u")

if __name__ == "__main__":
    mcp.run()
