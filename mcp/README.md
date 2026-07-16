# mac-farm MCP

Drives the farm as MCP tools so an assistant can operate the emulated Macs directly.

Tools: `mac_nodes`, `mac_screenshot`, `mac_click` (double=true for double-click),
`mac_move`, `mac_key`, `mac_cmd_key`, `mac_type`, `mac_menu_pick`.

Nodes map to the control ports: host=6560, alpha=6561, bravo=6562, charlie=6563.
Screenshots come from the host X display for `host`, or `docker exec` for the
containerized nodes.

Register with Claude Code:

    claude mcp add mac-farm --scope user -- python3 $PWD/mcp/server.py

Requires the `mcp` python package (FastMCP) and imagemagick on the host.
