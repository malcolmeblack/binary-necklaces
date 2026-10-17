"""MCP tools and exposition resource for binary-necklace questions."""
from pathlib import Path
from typing import Any
import os
import re
import sys

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('binary-necklaces')
# Preserve the deployed calculator route and request parameter.
BITCALC_API_BASE = os.environ.get('BINARY_NECKLACES_CALCULATOR_URL', 'https://malcolmblack.org/api/bitloops/calc')
REFERENCE_URL = os.environ.get('BINARY_NECKLACES_REFERENCE_URL', 'https://malcolmblack.org/binary-necklaces/binary-necklaces.yml')
REFERENCE_FILE = Path(__file__).with_name('knowledge') / 'binary-necklaces.yml'
USER_AGENT = 'binary-necklaces-app/1.0'
RESOURCE_URI = 'research://binary-necklaces-exposition'


def validate_word(word: str) -> None:
    if not isinstance(word, str) or re.fullmatch(r'[01]{1,64}', word) is None:
        raise ValueError('Provide a binary word of length 1 to 64, preserving leading zeros.')


def local_necklace_properties(word: str) -> dict[str, Any]:
    """Small exact operations; no component or power-set enumeration."""
    validate_word(word)
    def least(value):
        return min(value[i:] + value[:i] for i in range(len(value)))
    image = ''.join(str(int(word[i]) ^ int(word[i-1])) for i in range(len(word)))
    preimages = []
    if word.count('1') % 2 == 0:
        first = '0'
        for bit in word[1:]:
            first += str(int(first[-1]) ^ int(bit))
        other = ''.join('1' if bit == '0' else '0' for bit in first)
        preimages = sorted({least(first), least(other)})
    return {'word_image': image, 'necklace_image': least(image),
            'necklace_preimages': preimages,
            'necklace_chirality': 'achiral' if word[::-1] in word + word else 'chiral',
            'fixed_necklace': image in word + word}


async def make_bitcalc_request(url: str) -> dict[str, Any] | None:
    """Read the existing calculator API without changing its wire schema."""
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except (httpx.HTTPError, ValueError):
            return None


def format_response(response: dict, state: str | None = None) -> str:
    """Translate legacy API keys to the exposition's mathematical terminology."""
    facts = local_necklace_properties(state) if state is not None else {}
    def value(key):
        return response.get(key, 'not supplied')
    chirality = facts.get('necklace_chirality', response.get('necklace_chirality'))
    if chirality is None:
        chirality = {'symmetric': 'achiral', 'asymmetric': 'chiral'}.get(str(value('bl_symmetry')).lower(), 'not supplied')
    preimages = facts.get('necklace_preimages', response.get('necklace_preimages'))
    preimage_line = ('Distinct preimage necklaces (least representatives): ' + (', '.join(preimages) or 'None')) if preimages is not None else ('One preimage representative (legacy service selection): ' + str(value('bl_sublink')))
    levels = response.get('tree_levels')
    depth = response.get('tree_depth', value('tr_num_levels'))
    if levels is None:
        try:
            levels = int(depth) + 1
        except (TypeError, ValueError):
            levels = 'not supplied'
    word_image = facts.get('word_image', response.get('word_image', 'not supplied'))
    fixed = str(facts['fixed_necklace']).lower() if 'fixed_necklace' in facts else 'not determined'
    return f'''Properties of a binary word, its necklace, its incoming tree and component, and its ambient word space.

Binary word:
- Length: {value('bs_num_bits')}
- Parity: {value('bs_parity')}
- Complement: {value('bs_inverse')}
- Reversal: {value('bs_reverse')}
- Primitive root: {value('bs_pattern')}
- Literal adjacent-XOR image D(w), using right rotation: {word_image}

Binary necklace:
- Chirality: {chirality}
- Adjacent-XOR image (least necklace representative): {facts.get('necklace_image', value('bl_link'))}
- Fixed by the induced adjacent-XOR map: {fixed}
- {preimage_line}
- Least rotation: {value('bl_mvrot')}

Incoming rooted tree:
- Cycle root representative: {value('tr_root')}
- Branching sequence: {value('tr_structure')}
- Tree depth, root at depth zero: {depth}
- Number of levels, including the root: {levels}
- Number of necklaces: {value('tr_num_bl')}
- Number of binary words: {value('tr_num_bs')}
- Necklace representatives: {value('tr_ls_bl')}

Weakly connected component:
- Cycle length (number of attached trees): {value('ch_num_trees')}
- Cycle representatives: {value('ch_ls_roots')}
- Least cycle representative: {value('ch_mvroo')}

Ambient word space V_n and its necklace quotient:
- Number of binary words: {value('gr_num_bs')}
- Number of necklaces: {value('gr_num_bl')}
- Number of reflection-invariant components: {value('gr_num_sym_chains')}
- Reflection-invariant component representatives: {value('gr_ls_sym_chains')}
- Number of reflected component pairs: {value('gr_num_asym_chains')}
- Representatives of reflected component pairs: {value('gr_ls_asym_chains')}
- Number of graph types: {value('gr_num_graphs')}
- Graph types: {value('gr_ls_graphs')}

Each reflected pair contains TWO components. A reflection-invariant component can contain chiral necklaces. A fixed necklace requires D(w) to be a rotation of w, not necessarily the same written word. A branching sequence includes both incoming edges only at the cycle root.
'''


@mcp.tool()
async def get_properties(state: str) -> str:
    """Get properties of a binary word and its binary necklace.

    Args:
        state: A word of 1 to 64 bits, for example 1100101. Preserve leading zeros.

    Distinguishes literal word images from necklace representatives, lists all
    preimage necklaces, and reports components separately from reflected pairs.
    """
    try:
        validate_word(state)
    except ValueError as exc:
        return str(exc)
    response = await make_bitcalc_request(f'{BITCALC_API_BASE}?bitstring={state}')
    if response is None:
        return 'The calculator service could not be reached; its component and word-space counts are unavailable.'
    return format_response(response, state)


def valid_reference(text: str) -> bool:
    """Reject empty/error pages and the obsolete glossary before caching."""
    return bool(text.strip()) and all(marker in text for marker in (
        'concepts:', 'binary_necklace:', 'branching_sequence:', 'source: /binary-necklaces.html'))


@mcp.resource(RESOURCE_URI)
async def get_exposition() -> str:
    """Current terminology reference, with a bundled copy for offline startup."""
    if REFERENCE_URL:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(REFERENCE_URL)
                response.raise_for_status()
                if valid_reference(response.text):
                    return response.text
                print('Remote exposition is not the current reference; using bundled copy.', file=sys.stderr)
        except httpx.HTTPError:
            print('Remote exposition unavailable; using bundled copy.', file=sys.stderr)
    text = REFERENCE_FILE.read_text(encoding='utf-8')
    if not valid_reference(text):
        raise RuntimeError('The bundled binary-necklace reference is missing or invalid.')
    return text


@mcp.resource('research://bitloops-paper')
async def get_paper() -> str:
    """Compatibility resource; returns the same current exposition."""
    return await get_exposition()


def main():
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
