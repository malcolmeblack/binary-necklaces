---
inclusion: auto
description: Development and validation for the binary-necklace chatbot.
---

Use Python 3.12+ and the locked dependencies in `mcp/pyproject.toml` and `mcp/uv.lock`. Use the existing Next.js dependencies and lockfile for the UI. Build the static UI with `npm run build`; deploy `ui/out/` under `/binary-necklaces/chatbot`.

Run offline checks from the repository root using `python3 -m unittest discover -s tests -v`. Live evaluation scripts in `mcp/` call AWS Bedrock repeatedly and are not offline tests. Recorded evaluation JSON is historical data; preserve it as recorded.

Keep legacy calculator wire keys and `/api/bitloops/*` routes compatible. Update display labels, tool prose, reference material, and new canonical fields together. Restart the MCP service after a reference update because it is cached at startup.
