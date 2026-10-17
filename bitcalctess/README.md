# Binary Necklace Calculator and Tessellator

The [exposition](https://malcolmblack.org/binary-necklaces.html) describes binary words, their rotation classes (binary necklaces), and the adjacent-XOR functional digraph.

`bitcalctess.html` is the interface. It displays complement, primitive root, chirality, image and preimages, branching sequence, tree depth/levels, and component catalogue properties. Publish it at `/binary-necklaces/bitcalctess.html` beside the website's existing root stylesheet.

The active services are [the Python calculator](calculator/python/) and [the tessellator](tessellator/). They retain the existing Lambda handler interface and API routes. Both accept binary words of length 1–64; large cycles and trees can still make a particular request expensive. The bundled word-space catalogue has entries for widths 1–28; outside that range the catalogue fields report no data. This terminology update does not increase enumeration limits.

The HTML, MCP adapter, and Python services distinguish all preimage necklaces from the former single-preimage field. They also distinguish the number of tree levels from tree depth. The legacy wire fields remain available.

The tessellator draws geometric tilings from a periodic space-time diagram. Its drawing coordinates use a staggered neighbor convention that differs from the literal word map by a rotation; its necklace dynamics and tile geometry are unchanged.

The Java, C, and C++ directories contain earlier standalone implementations. They are not called by the web services. Their historical build/runtime limitations are retained; the bundled Java source refers to a `ParallelCalculator` class not included in that directory. The complete [Java research calculator](../ai/calculators/java-ai/) is available for research enumeration.
