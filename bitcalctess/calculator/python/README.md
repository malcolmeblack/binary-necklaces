# Binary necklace calculator (Python)

`calc.py` implements word operations, necklace operations, incoming trees, and components. It uses the Python standard library. Canonical names include `adjacent_xor`, `necklace_image`, `word_preimages`, `necklace_preimages`, `complement`, `primitive_root`, `is_achiral`, `branching_sequence`, `tree_depth`, and `tree_levels`. Old names remain aliases.

`main.handler(event, context)` accepts the existing `queryStringParameters.bitstring` request. Invalid or empty words return HTTP 400. Existing JSON fields remain unchanged, with these additions:

| Field | Meaning |
| --- | --- |
| `word_image` | Literal `D(w)=w+R(w)` with right rotation |
| `necklace_chirality` | `achiral` or `chiral` |
| `necklace_preimages` | Sorted distinct least representatives of every preimage necklace |
| `tree_depth` | Maximum tree depth, root at zero |
| `tree_levels` | Number of levels including the root; depth plus one |

`powerset.json` is the existing catalogue for widths 1–28. Its legacy DynamoDB-shaped keys and all numerical data are unchanged. The service supports the original Lambda `src/` and `data/` layout and direct imports from this directory. Place the catalogue either at `data/powerset.json` relative to the handler or alongside `main.py`; the existing working-directory `data/` layout is also recognized.

`example-response.json` is an updated response for `1100101`; `legacy-example-response.json` is the previous response retained for compatibility tests. `component_mass` counts each word once; the former unused helper double-counted the cycle contribution. The public response's existing numeric fields are preserved.
