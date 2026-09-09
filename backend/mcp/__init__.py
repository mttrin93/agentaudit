"""The MCP surface: four tools over routes that already exist.

A delivery surface and not a capability
([ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)).
Nothing in this package imports `backend.bench`, starts a process, holds a key or
takes the case-library lease: every rule a tool appears to enforce is enforced on
the far side of an HTTP route, which is what makes the surface safe to hand to a
model. `test_mcp_wall.py` holds the import half of that claim.

The spec is [docs/specs/mcp-server.md](../../docs/specs/mcp-server.md).
"""
