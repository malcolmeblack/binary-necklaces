"""Bounded exact integer factorization; probable primes are never final answers.

Miller--Rabin's seven-base theorem certifies integers below 2**64. Larger
probable primes require a recursively verified Lucas n-1 certificate. Pollard
rho supplies candidate factors only; every final prime factor is certified.
"""
from math import gcd
from random import Random


class ComputationLimit(RuntimeError):
    """An exact result could not be completed within a resource limit."""


_SMALL = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
_MR64 = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)
MAX_FACTOR_DEPTH = 64
MAX_INTEGER_BITS = 4096


def _miller_rabin(n, bases, check=None):
    if n < 2:
        return False
    for p in _SMALL:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in bases:
        if check:
            check()
        a %= n
        if a == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


class _Factorer:
    def __init__(self, check):
        self.check = check or (lambda: None)
        self.primes = set(_SMALL)
        self.factors = {1: {}}
        self.steps = 0
        self.depth = 0

    def tick(self, steps=1):
        self.steps += steps
        self.check()
        if self.steps > 2_000_000:
            raise ComputationLimit("Integer factorization exceeded its work budget")

    def prime(self, n):
        self.tick()
        if n in self.primes:
            return True
        if n < 2**64:
            answer = _miller_rabin(n, _MR64, self.check)
            if answer:
                self.primes.add(n)
            return answer
        if not _miller_rabin(n, _SMALL, self.check):
            return False
        # Full n-1 factorization gives an exact Lucas certificate. A different
        # witness may be used for each prime divisor of n-1.
        factors = self.factor(n - 1)
        for p in factors:
            for a in range(2, 258):
                self.tick()
                if pow(a, n - 1, n) != 1:
                    return False
                if gcd(pow(a, (n - 1) // p, n) - 1, n) == 1:
                    break
            else:
                raise ComputationLimit("A large prime could not be certified within the witness budget")
        self.primes.add(n)
        return True

    def rho(self, n):
        rng = Random(n)
        for _ in range(32):
            self.tick()
            y = rng.randrange(1, n)
            c = rng.randrange(1, n)
            g, r = 1, 1
            while g == 1:
                x = y
                for i in range(r):
                    y = (y * y + c) % n
                    if i % 128 == 0:
                        self.tick(128)
                k = 0
                while k < r and g == 1:
                    ys = y
                    product = 1
                    for _ in range(min(128, r - k)):
                        y = (y * y + c) % n
                        product = product * abs(x - y) % n
                    self.tick(128)
                    g = gcd(product, n)
                    k += 128
                r *= 2
            if g == n:
                g = 1
                while g == 1:
                    ys = (ys * ys + c) % n
                    g = gcd(abs(x - ys), n)
                    self.tick()
            if 1 < g < n:
                return g
        raise ComputationLimit("Integer factorization did not find a nontrivial factor")

    def factor(self, n):
        # Recursive prime certificates also call factor(). Bound their stack
        # explicitly so an unfinished proof is deferred, not a Python overflow.
        if self.depth >= MAX_FACTOR_DEPTH:
            raise ComputationLimit("Integer factorization exceeded its certificate-depth limit")
        self.depth += 1
        try:
            return self._factor(n)
        finally:
            self.depth -= 1

    def _factor(self, n):
        self.tick()
        if n in self.factors:
            return self.factors[n].copy()
        if n.bit_length() > MAX_INTEGER_BITS:
            raise ComputationLimit(f"The required integer order bound exceeds the {MAX_INTEGER_BITS}-bit factoring limit")
        original, result = n, {}
        for p in _SMALL:
            while n % p == 0:
                n //= p
                result[p] = result.get(p, 0) + 1
        if n > 1:
            if self.prime(n):
                result[n] = result.get(n, 0) + 1
            else:
                divisor = self.rho(n)
                for part in (divisor, n // divisor):
                    for p, e in self.factor(part).items():
                        result[p] = result.get(p, 0) + e
        self.factors[original] = result
        return result.copy()


def factor_integer(n, check=None):
    """Return {certified prime: exponent}, or raise ComputationLimit/TimeoutError."""
    if n < 1:
        raise ValueError("Positive integer required")
    return _Factorer(check).factor(n)


def divisors(n):
    """Small n divisors, ordered increasingly; no advanced factoring needed."""
    low, high = [], []
    d = 1
    while d * d <= n:
        if n % d == 0:
            low.append(d)
            if d * d != n:
                high.append(n // d)
        d += 1
    return low + high[::-1]


def totient(n):
    result, p = n, 2
    while p * p <= n:
        if n % p == 0:
            result -= result // p
            while n % p == 0:
                n //= p
        p += 1
    if n > 1:
        result -= result // n
    return result


def mobius(n):
    result, p = 1, 2
    while p * p <= n:
        if n % p == 0:
            n //= p
            if n % p == 0:
                return 0
            result = -result
        p += 1
    return -result if n > 1 else result
