"""Algebra of an individual binary word and its rotation class.

Polynomial coefficient i is the character word[i]. Multiplication by x is
right rotation, so the adjacent-XOR map is multiplication by 1+x. Basic
invariants and the first periodic iterate never require orbit enumeration.
Only the explicitly bounded previews enumerate vertices.
"""

from math import gcd


def primitive_root(word):
    """Shortest word whose repetitions make word (linear-time prefix table)."""
    prefix = [0] * len(word)
    for i in range(1, len(word)):
        j = prefix[i - 1]
        while j and word[i] != word[j]:
            j = prefix[j - 1]
        if word[i] == word[j]:
            j += 1
        prefix[i] = j
    period = len(word) - prefix[-1]
    return word[:period] if len(word) % period == 0 else word


def least_rotation(word):
    """Lexicographically least rotation, using Booth's linear-time algorithm."""
    n = len(word)
    doubled = word + word
    i, j, k = 0, 1, 0
    while i < n and j < n and k < n:
        a, b = doubled[i + k], doubled[j + k]
        if a == b:
            k += 1
            continue
        if a > b:
            i += k + 1
            if i == j:
                i += 1
        else:
            j += k + 1
            if i == j:
                j += 1
        k = 0
    start = min(i, j)
    return doubled[start:start + n]


def complement(word):
    return word.translate(str.maketrans("01", "10"))


def adjacent_xor(word):
    """D(w)[i] = w[i] XOR w[i-1], including the cyclic boundary."""
    return ''.join('0' if word[i] == word[i - 1] else '1'
                   for i in range(len(word)))


def word_preimages(word):
    """The two literal D-preimages of an even-weight word, or no preimages."""
    if word.count('1') & 1:
        return []
    previous = 0
    bits = ['0']
    for bit in word[1:]:
        previous ^= bit == '1'
        bits.append('1' if previous else '0')
    first = ''.join(bits)
    return [first, complement(first)]


def necklace_preimages(word):
    return sorted({least_rotation(item) for item in word_preimages(word)})


def _encode(word):
    return int(word[::-1], 2)


def _decode(value, width):
    return format(value, '0%db' % width)[::-1]


def _rotate(value, amount, width):
    amount %= width
    if not amount:
        return value
    return ((value << amount) & ((1 << width) - 1)) | (value >> (width - amount))


def xor_jump(word, steps):
    """Compute D**steps(word) in O(log(steps)) cyclic bit operations.

    In characteristic two, (I+R)**(2**j) = I+R**(2**j).
    No intermediate rows or trajectory are constructed.
    """
    if not isinstance(steps, int) or steps < 0:
        raise ValueError('steps must be a nonnegative integer')
    value, width, shift = _encode(word), len(word), 1
    while steps:
        if steps & 1:
            value ^= _rotate(value, shift, width)
        steps >>= 1
        shift = (shift * 2) % width
    return _decode(value, width)


def _valuation_at_one(value, cap):
    """min(v_(x+1)(value), cap), where cap is a power of two.

    First reduce modulo (x+1)**cap = x**cap+1. Each subsequent halving
    uses (x+1)**h = x**h+1 to decide whether the valuation is at least h.
    This avoids repeated linear divisions by x+1.
    """
    mask = (1 << cap) - 1
    residue = 0
    while value:
        residue ^= value & mask
        value >>= cap
    if not residue:
        return cap
    valuation = 0
    width = cap
    while width > 1:
        half = width // 2
        low = residue & ((1 << half) - 1)
        high = residue >> half
        if low == high:
            valuation += half
            residue = low
        else:
            residue = low ^ high
        width = half
    return valuation


def periodic_entry(word):
    """Return (first periodic word, exact transient length), with no factoring."""
    n = len(word)
    q = n & -n
    height = q - _valuation_at_one(_encode(word), q)
    return xor_jump(word, height), height


def core_data(word):
    """Cheap periodic-core data, including its minimal annihilator polynomial."""
    from .finitefield import gcd as poly_gcd, divide_exact

    n = len(word)
    entry, height = periodic_entry(word)
    modulus = (1 << n) | 1
    annihilator = divide_exact(modulus, poly_gcd(_encode(entry), modulus))
    return {
        'q': n & -n,
        'transient_depth': height,
        'cycle_entry': entry,
        'periodic_spatial_period': len(primitive_root(entry)),
        'annihilator': annihilator,
    }


def _tree_data(root, q, period):
    two_part = period & -period
    sequence = '2' + ''.join(
        '1' if j & (j - 1) == 0 and j >= two_part else '2'
        for j in range(1, q)
    ) + '0'
    necklaces = 1
    rho = 1
    for depth in range(1, q + 1):
        while two_part * rho < depth:
            rho *= 2
        necklaces += (1 << (depth - 1)) // rho
    return {
        'root': root,
        'depth': q,
        'levels': q + 1,
        'branching_sequence': sequence,
        'necklaces': necklaces,
        'words': period * (1 << q),
    }


def _preview_result(items, total, limit, reason=None):
    truncated = total is None or len(items) < total
    return {'items': items, 'total': total, 'truncated': truncated,
            'returned': len(items), 'limit': limit,
            'status': 'truncated' if truncated else 'complete',
            'reason': (reason or 'item_limit') if truncated else None}


def _tree_preview(root, total, limit, check=None):
    """Breadth-first prefix of this root's attached tree, excluding cycle edges."""
    items, queue = [], [(root, 0)]
    index = 0
    try:
        while index < len(queue) and len(items) < limit:
            if check:
                check()
            vertex, depth = queue[index]
            index += 1
            items.append({'word': vertex, 'depth': depth})
            if len(items) < limit:
                for preimage in necklace_preimages(vertex):
                    if depth or periodic_entry(preimage)[1] != 0:
                        queue.append((preimage, depth + 1))
    except TimeoutError:
        return _preview_result(items, total, limit, 'time_limit')
    return _preview_result(items, total, limit)


def _cycle_preview(root, total, limit, check=None):
    items, seen = [], set()
    vertex = root
    try:
        while len(items) < limit and vertex not in seen:
            if check:
                check()
            seen.add(vertex)
            items.append(vertex)
            if total is not None and len(items) >= total:
                break
            vertex = least_rotation(adjacent_xor(vertex))
        if total is None and vertex in seen:
            # A bounded preview can sometimes close even when algebraic
            # classification was deferred. This list then proves its own size.
            total = len(items)
    except TimeoutError:
        return _preview_result(items, total, limit, 'time_limit')
    return _preview_result(items, total, limit)


def analyze_word(word, check=None, preview_limit=16):
    """Return exact invariants plus bounded previews for a validated binary word.

    check() may raise TimeoutError to bound expensive order computations.
    Integer factorization failures are reported as deferred component fields;
    the already exact word, necklace, transient and tree data remain available.
    Counts are Python integers; the HTTP layer serializes them losslessly.
    """
    if not isinstance(word, str) or not 1 <= len(word) <= 4096 or any(c not in '01' for c in word):
        raise ValueError('word must contain 1 to 4096 binary digits')
    if isinstance(preview_limit, bool) or not isinstance(preview_limit, int) or not 0 <= preview_limit <= 64:
        raise ValueError('preview_limit must be in 0..64')
    from .numbertheory import ComputationLimit

    n = len(word)
    primitive = primitive_root(word)
    core = core_data(word)
    root = least_rotation(core['cycle_entry'])
    tree = _tree_data(root, core['q'], core['periodic_spatial_period'])
    component = {'status': 'deferred', 'cycle_length': None, 'word_period': None,
                 'rotation_shift': None, 'graph_name': None, 'necklaces': None,
                 'words': None, 'reason': None}
    try:
        if core['annihilator'] == 1:
            period, cycle, shift = 1, 1, 0
        else:
            from .census import relation_for_modulus
            period, cycle, shift = relation_for_modulus(core['annihilator'], n, check)
        if period != core['periodic_spatial_period']:
            raise ArithmeticError('Annihilator rotation order disagrees with the word period')
        component.update({
            'status': 'exact',
            'cycle_length': cycle,
            'word_period': cycle * period // gcd(period, shift),
            'rotation_shift': shift,
            'graph_name': 'G%d-%s' % (cycle, tree['branching_sequence']),
            'necklaces': cycle * tree['necklaces'],
            'words': cycle * tree['words'],
        })
    except (ComputationLimit, TimeoutError) as exc:
        component['reason'] = str(exc) or 'Exact order computation exceeded its work limit.'
    return {
        'word': {
            'value': word,
            'length': n,
            'weight': word.count('1'),
            'parity': 'odd' if word.count('1') & 1 else 'even',
            'complement': complement(word),
            'reversal': word[::-1],
            'palindrome': word == word[::-1],
            'primitive_root': primitive,
            'spatial_period': len(primitive),
            'adjacent_xor': adjacent_xor(word),
        },
        'necklace': {
            'least_rotation': least_rotation(word),
            'image': least_rotation(adjacent_xor(word)),
            'chirality': 'achiral' if word[::-1] in word + word else 'chiral',
            'self_complementary': complement(word) in word + word,
            'spatial_period': len(primitive),
            'preimages': necklace_preimages(word),
        },
        'dynamics': {
            'transient_depth': core['transient_depth'],
            'cycle_entry': core['cycle_entry'],
            'periodic_spatial_period': core['periodic_spatial_period'],
            'annihilator': hex(core['annihilator']),
        },
        'tree': tree,
        'component': component,
        'preview': {
            'cycle': _cycle_preview(root, component['cycle_length'], preview_limit, check),
            'tree': _tree_preview(root, tree['necklaces'], preview_limit, check),
        },
    }
