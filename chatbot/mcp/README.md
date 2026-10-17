# Binary-necklace MCP service

`main.py` serves the `/mcp` streaming endpoint and `/health`. It starts `binary_necklaces.py` as a stdio MCP subprocess. `roles.py` defines the analysis roles and common terminology guidance.

The `get_properties(state)` tool retains its name and argument schema. Its response uses canonical mathematical terms and distinguishes literal images, necklace representatives, all preimage necklaces, tree depth, levels, and reflected component pairs. The deployed calculator route and its old JSON keys are translated at this boundary.

The canonical resource is `research://binary-necklaces-exposition`. The old URI and `bitloops.py` entry point remain aliases. The bundled `knowledge/` reference permits startup before the new website path is published. Invalid/error-page/obsolete remote responses are rejected. Set `BINARY_NECKLACES_REFERENCE_URL` to an empty string for deterministic bundled-only operation, or to another current YAML URL. The orchestrator caches the selected reference until restart.

The Docker build includes `knowledge/`. See [the chatbot README](../README.md) for setup and deployment. `test/` contains historical recorded evaluations; it is not runtime reference material.
