"""Exact binary polynomial arithmetic; bit i is the coefficient of x**i."""


def degree(p):
    return p.bit_length() - 1


def divmod_poly(a, p):
    if p <= 0 or a < 0:
        raise ValueError("Nonnegative polynomial and positive divisor required")
    quotient = 0
    d = p.bit_length()
    while a.bit_length() >= d:
        shift = a.bit_length() - d
        quotient ^= 1 << shift
        a ^= p << shift
    return quotient, a


def remainder(a, p):
    if p <= 0 or a < 0:
        raise ValueError("Nonnegative polynomial and positive divisor required")
    d = p.bit_length()
    while a.bit_length() >= d:
        a ^= p << (a.bit_length() - d)
    return a


def quotient(a, p):
    return divmod_poly(a, p)[0]


def divide_exact(a, p):
    q, r = divmod_poly(a, p)
    if r:
        raise ArithmeticError("Nonexact polynomial division")
    return q


def multiply(a, b):
    if a < 0 or b < 0:
        raise ValueError("Negative polynomial")
    result = 0
    if a == b:
        while b:
            low = b & -b
            result |= 1 << (2 * (low.bit_length() - 1))
            b ^= low
        return result
    if a.bit_count() < b.bit_count():
        a, b = b, a
    while b:
        low = b & -b
        result ^= a << (low.bit_length() - 1)
        b ^= low
    return result


mul = multiply


def multiply_mod(a, b, p):
    return remainder(multiply(remainder(a, p), remainder(b, p)), p)


def pow_mod(a, exponent, p, check=None):
    if exponent < 0:
        raise ValueError("Negative polynomial exponent")
    result = remainder(1, p)
    a = remainder(a, p)
    while exponent:
        if check:
            check()
        if exponent & 1:
            result = multiply_mod(result, a, p)
        exponent >>= 1
        if exponent:
            a = multiply_mod(a, a, p)
    return result


powmod = pow_mod


def gcd(a, b):
    while b:
        a, b = b, remainder(a, b)
    return a


def derivative(p):
    result = 0
    for i in range(1, p.bit_length(), 2):
        if (p >> i) & 1:
            result |= 1 << (i - 1)
    return result


def square_root(p):
    """Square root of a polynomial whose odd coefficients vanish."""
    result = 0
    for i in range(p.bit_length()):
        if (p >> i) & 1:
            if i & 1:
                raise ArithmeticError("Polynomial is not a square")
            result |= 1 << (i // 2)
    return result


def _nullspace(rows, columns, check):
    rank = 0
    pivots = []
    for c in range(columns):
        if check:
            check()
        chosen = next((r for r in range(rank, len(rows)) if (rows[r] >> c) & 1), None)
        if chosen is None:
            continue
        rows[rank], rows[chosen] = rows[chosen], rows[rank]
        for r in range(len(rows)):
            if r != rank and ((rows[r] >> c) & 1):
                rows[r] ^= rows[rank]
        pivots.append(c)
        rank += 1
    pivot_set = set(pivots)
    result = []
    for c in range(columns):
        if c in pivot_set:
            continue
        if check:
            check()
        vector = 1 << c
        for r, pivot in enumerate(pivots):
            if (rows[r] & vector).bit_count() & 1:
                vector |= 1 << pivot
        result.append(vector)
    return result


def verify_irreducible(p, check=None):
    d = degree(p)
    if d < 1:
        raise ValueError("Nonconstant polynomial required")
    tests, rest, prime = set(), d, 2
    while prime * prime <= rest:
        if rest % prime == 0:
            tests.add(d // prime)
            while rest % prime == 0:
                rest //= prime
        prime += 1
    if rest > 1:
        tests.add(d // rest)
    x = remainder(2, p)
    value = x
    for i in range(1, d + 1):
        if check:
            check()
        value = multiply_mod(value, value, p)
        if i in tests and gcd(value ^ x, p) != 1:
            raise ArithmeticError("Reducible polynomial")
    if value != x:
        raise ArithmeticError("Reducible polynomial")


def factor_squarefree(p, check=None):
    """Deterministic Berlekamp factorization, verified by Rabin's criterion."""
    if p < 1:
        raise ValueError("Positive polynomial required")
    if p == 1:
        return []
    if gcd(p, derivative(p)) != 1:
        raise ValueError("Squarefree polynomial required")
    d = degree(p)
    rows = [0] * d
    column, x2 = 1, remainder(4, p)
    for j in range(d):
        if check:
            check()
        bits = column
        while bits:
            low = bits & -bits
            rows[low.bit_length() - 1] |= 1 << j
            bits ^= low
        rows[j] ^= 1 << j
        column = multiply_mod(column, x2, p)
    kernel = _nullspace(rows, d, check)
    factors = [p]
    for v in kernel:
        if v in (0, 1):
            continue
        for i in range(len(factors)):
            if check:
                check()
            f = factors[i]
            a = gcd(f, v)
            if a != 1 and a != f:
                factors[i] = a
                factors.append(divide_exact(f, a))
    if len(factors) != len(kernel):
        raise ArithmeticError("Incomplete Berlekamp factorization")
    product = 1
    for f in factors:
        verify_irreducible(f, check)
        product = multiply(product, f)
    if product != p:
        raise ArithmeticError("Polynomial factor product mismatch")
    return sorted(factors)


def factor_with_multiplicity(p, check=None):
    """Squarefree decomposition followed by exact irreducible factorization."""
    if p < 1:
        raise ValueError("Positive polynomial required")
    result = {}

    def split(f, scale):
        if f == 1:
            return
        if check:
            check()
        derivative_f = derivative(f)
        repeated = gcd(f, derivative_f)
        w = divide_exact(f, repeated)
        exponent = 1
        while w != 1:
            if check:
                check()
            y = gcd(w, repeated)
            part = divide_exact(w, y)
            if part != 1:
                for irreducible in factor_squarefree(part, check):
                    result[irreducible] = result.get(irreducible, 0) + scale * exponent
            w = y
            repeated = divide_exact(repeated, y)
            exponent += 1
        if repeated != 1:
            split(square_root(repeated), scale * 2)

    split(p, 1)
    return dict(sorted(result.items()))
