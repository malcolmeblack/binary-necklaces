---
inclusion: auto
description: Binary-necklace chatbot architecture and terminology contracts.
---

The FastAPI app `mcp/main.py` exposes `/mcp` (POST/SSE) and `/health`, and starts `mcp/binary_necklaces.py` as a stdio MCP tool server. Its `get_properties` tool translates the deployed calculator API into canonical terminology. Its `research://binary-necklaces-exposition` resource fetches the current YAML reference or uses the bundled snapshot. The former script and resource URI remain compatibility aliases.

The UI is exported under `/binary-necklaces/chatbot`. The public exposition is `https://malcolmblack.org/binary-necklaces.html`; its YAML is `/binary-necklaces/binary-necklaces.yml`. Use the definitions in that reference, especially word versus necklace equality, all preimages versus one selection, branching sequence, and components versus reflected pairs.

The existing FastAPI/SSE transport, Bedrock model and AWS region, ECR `mcp` repository, and CloudWatch `BitloopsChatbot` namespace are retained. Deployment configuration uses `mcp.malcolmblack.org`. Do not rename live resource identifiers as a terminology edit. See the chatbot README for deployment and the repository README for tests.
