# Binary necklace tessellator

The Lambda entry point is `main.handler`. It accepts the existing `bitstring` query parameter, locates the periodic necklace reached from that word, repeats it spatially, and draws a geometric tessellation. Invalid words return HTTP 400.

Install `requirements.txt` for Pillow. The service recognizes both the existing `src/` / `data/` Lambda layout and direct imports from this directory. Put `american-typewriter.ttf` in the existing working-directory `data/` folder, in `data/` beside the renderer, or beside the renderer itself.

The row update `adjacent_xor_staggered` XORs positions `i` and `i+1` because each new row is shifted horizontally by half a cell. It is a rotation of the right-rotation word map `D` in the exposition, so the induced necklace map is the same. Tile geometry, GIF output, and the API response contract are retained.

`calc.py` mirrors the calculator's mathematical helpers so each Lambda package remains self-contained. Keep the copies synchronized when changing these helpers.
