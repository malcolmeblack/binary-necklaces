#!/usr/bin/env python3
"""Independently verify version 2.1 certificates and their two CSV aggregates.

Usage: python3 verify_output.py [OUTPUTDIR]

Python 3.9+ and the standard library suffice. No Java classes, bitstrings,
chain representatives, field tables, or external packages are consulted.
The checks instantiate the partition theorem in REFERENCE.md#partition-proof.

Public API:
    load_certificate(path) -> dictionary (rejects duplicate JSON keys)
    verify_certificate(dictionary) -> (powerset_row, graph_rows)
    verify_directory(path) -> list of powerset rows, sorted by n

Rows are dictionaries with the exact CSV column names. Numeric fields are
Python integers; graph names and signatures are strings. Invalid inputs raise
VerificationError, a ValueError subclass. No output files are modified.
"""

import argparse
import csv
import itertools
import json
import math
from pathlib import Path
import re
import sys
from functools import lru_cache


POWERSET_HEADER = ("n", "bitstrings", "bitloops", "factors", "chains", "graphs")
GRAPH_HEADER = (
    "n", "name", "chains", "bitloops-per-chain", "bitstrings", "bitloops",
    "factors", "cycle-order", "tree-depth", "signature",
)
_TOP_KEYS = {
    "schema_version", "n", "q", "core_polynomial", "irreducible_factors",
    "strata", "totals",
}
_STRATUM_KEYS = {
    "annihilator", "factor_exponents", "units", "rotation_order", "link_order",
    "cycle_order", "chains", "bitstrings", "bitloops", "factors", "name",
    "signature",
}
_HEX = re.compile(r"0x(?:0|[1-9a-f][0-9a-f]*)\Z")
_CERTIFICATE_NAME = re.compile(r"([1-9][0-9]*)\.json\Z")


class VerificationError(ValueError):
    """A certificate, its mathematical claims, or an aggregate is invalid."""


def _require(condition, message):
    if not condition:
        raise VerificationError(message)


def _keys(value, expected, where):
    _require(type(value) is dict, f"{where}: expected an object")
    _require(set(value) == set(expected),
             f"{where}: wrong keys (missing={sorted(set(expected) - set(value))}, "
             f"unknown={sorted(set(value) - set(expected), key=str)})")


def _integer(value, where, lower=0, upper=None):
    _require(type(value) is int, f"{where}: expected an exact integer, not a boolean or float")
    _require(value >= lower, f"{where}: must be at least {lower}")
    if upper is not None:
        _require(value <= upper, f"{where}: must be at most {upper}")
    return value


def _polynomial(value, where, max_degree):
    _require(type(value) is str and _HEX.fullmatch(value) is not None,
             f"{where}: expected canonical lowercase hexadecimal polynomial")
    _require(len(value) <= 2 + (max_degree + 4) // 4,
             f"{where}: polynomial exceeds its allowed degree")
    result = int(value, 16)
    _require(result > 0 and result.bit_length() - 1 <= max_degree,
             f"{where}: invalid polynomial degree")
    return result


def _poly_mul(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a <<= 1
        b >>= 1
    return result


def _poly_mod(a, modulus):
    degree = modulus.bit_length() - 1
    while a and a.bit_length() - 1 >= degree:
        a ^= modulus << (a.bit_length() - 1 - degree)
    return a


def _poly_gcd(a, b):
    while b:
        a, b = b, _poly_mod(a, b)
    return a


def _poly_pow(a, exponent, modulus):
    a = _poly_mod(a, modulus)
    result = _poly_mod(1, modulus)
    while exponent:
        if exponent & 1:
            result = _poly_mod(_poly_mul(result, a), modulus)
        exponent >>= 1
        if exponent:
            a = _poly_mod(_poly_mul(a, a), modulus)
    return result


@lru_cache(maxsize=None)
def _prime(n):
    """Deterministic Miller--Rabin for integers below 2**64."""
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
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


def _rho_factor(n):
    """Deterministic-seeded, bounded Pollard--Brent factor search."""
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return p
    # A failure is reported instead of accepting an unproved prime or hanging.
    for attempt in range(1, 33):
        y, c, r, g, steps = 2 + attempt, 2 * attempt + 1, 1, 1, 0
        saved = y
        while g == 1 and steps < 262144:
            x = y
            for _ in range(r):
                y = (y * y + c) % n
            steps += r
            k = 0
            while k < r and g == 1:
                saved = y
                product = 1
                batch = min(128, r - k)
                for _ in range(batch):
                    y = (y * y + c) % n
                    product = product * abs(x - y) % n
                g = math.gcd(product, n)
                k += batch
                steps += batch
            r *= 2
        if g == n:
            for _ in range(4096):
                saved = (saved * saved + c) % n
                g = math.gcd(abs(x - saved), n)
                if g > 1:
                    break
        if 1 < g < n:
            return g
    raise VerificationError(f"bounded integer factorization did not finish for {n}")


@lru_cache(maxsize=None)
def _prime_factors(n):
    _require(1 <= n < (1 << 64), "integer factorization outside the supported range")
    if n == 1:
        return ()
    if _prime(n):
        return (n,)
    divisor = _rho_factor(n)
    return tuple(sorted(_prime_factors(divisor) + _prime_factors(n // divisor)))


@lru_cache(maxsize=None)
def _irreducible(f):
    degree = f.bit_length() - 1
    if degree < 1:
        return False
    x = _poly_mod(2, f)
    tests = {degree // p for p in set(_prime_factors(degree))}
    value = x
    for k in range(1, degree + 1):
        value = _poly_mod(_poly_mul(value, value), f)
        if k in tests and _poly_gcd(value ^ x, f) != 1:
            return False
    return value == x


def _divisors(n):
    return [d for d in range(1, n + 1) if n % d == 0]


def _totient(n):
    result = n
    for p in set(_prime_factors(n)):
        result = result // p * (p - 1)
    return result


def _mobius(n):
    primes = _prime_factors(n)
    if len(primes) != len(set(primes)):
        return 0
    return -1 if len(primes) % 2 else 1


def _necklaces(n):
    return sum(_totient(d) * (1 << (n // d)) for d in _divisors(n)) // n


def _primitive_necklaces(n):
    return sum(_mobius(d) * (1 << (n // d)) for d in _divisors(n)) // n


def _signature(q, d):
    h = math.gcd(q, d)
    return "2" + "".join("1" if j >= h and j & (j - 1) == 0 else "2"
                         for j in range(1, q)) + "0"


def _per_chain_counts(n, q, d, cycle):
    orbit = d * cycle
    loops = factors = 0
    e = 1
    while e <= q:
        coordinates = 2 if e == 1 else (1 << e) - (1 << (e // 2))
        period = math.lcm(d, e)
        numerator = orbit * coordinates
        _require(numerator % period == 0, "nonintegral lifted bitloop count")
        loops += numerator // period
        if period == n:
            factors += numerator // period
        e *= 2
    # A different formula counts vertices directly from the rooted tree.
    h = math.gcd(d, q)
    tree_size = 1
    for height in range(1, q + 1):
        rotation_orbit = 1
        while h * rotation_orbit < height:
            rotation_orbit *= 2
        tree_size += (1 << (height - 1)) // rotation_orbit
    _require(loops == cycle * tree_size, "tree and period bitloop formulas disagree")
    return orbit << q, loops, factors


def _check_order(base, order, modulus, identity, where):
    _require(_poly_pow(base, order, modulus) == identity,
             f"{where}: claimed order does not give the identity")
    for p in set(_prime_factors(order)):
        _require(_poly_pow(base, order // p, modulus) != identity,
                 f"{where}: claimed order is not minimal (prime divisor {p})")


def verify_certificate(certificate):
    """Verify one decoded certificate; return its powerset and graph rows."""
    _keys(certificate, _TOP_KEYS, "certificate")
    _require(certificate["schema_version"] == "2.1", "unsupported schema_version")
    n = _integer(certificate["n"], "n", 1, 64)
    q = _integer(certificate["q"], "q", 1, 64)
    _require(q == n & -n, "q must be the largest power of two dividing n")
    dimension = n - q
    expected_core = sum(1 << (i * q) for i in range(n // q))
    core = _polynomial(certificate["core_polynomial"], "core_polynomial", dimension)
    _require(core == expected_core, "incorrect core polynomial")
    factor_records = certificate["irreducible_factors"]
    _require(type(factor_records) is list, "irreducible_factors: expected an array")
    _require(len(factor_records) <= dimension, "too many irreducible factors")
    polynomials, degrees, powers = [], [], []
    product = 1
    for i, record in enumerate(factor_records):
        where = f"irreducible_factors[{i}]"
        _keys(record, {"polynomial", "degree", "multiplicity"}, where)
        f = _polynomial(record["polynomial"], where + ".polynomial", dimension)
        degree = _integer(record["degree"], where + ".degree", 1, dimension)
        _require(degree == f.bit_length() - 1, f"{where}: incorrect degree")
        multiplicity = _integer(record["multiplicity"], where + ".multiplicity", 1, q)
        _require(multiplicity == q, f"{where}: multiplicity must equal q")
        _require(f not in polynomials, f"{where}: duplicate irreducible factor")
        _require(_irreducible(f), f"{where}: polynomial is reducible")
        pows = [1]
        for _ in range(q):
            pows.append(_poly_mul(pows[-1], f))
        product = _poly_mul(product, pows[-1])
        _require(product.bit_length() <= dimension + 1, "factorization exceeds core degree")
        polynomials.append(f)
        degrees.append(degree)
        powers.append(pows)
    _require(product == core, "irreducible factorization does not multiply to core polynomial")

    strata = certificate["strata"]
    _require(type(strata) is list, "strata: expected an array")
    expected_strata = (q + 1) ** len(polynomials)
    _require(len(strata) == expected_strata,
             f"strata: expected complete exponent grid of {expected_strata} entries, got {len(strata)}")
    seen = set()
    graphs = {}
    total_units = total_words = total_loops = total_factors = total_chains = 0
    for i, record in enumerate(strata):
        where = f"n={n} strata[{i}]"
        _keys(record, _STRATUM_KEYS, where)
        exponents = record["factor_exponents"]
        _require(type(exponents) is list and len(exponents) == len(polynomials),
                 f"{where}: factor_exponents has incorrect length or type")
        for j, exponent in enumerate(exponents):
            _integer(exponent, f"{where}.factor_exponents[{j}]", 0, q)
        exponent_tuple = tuple(exponents)
        _require(exponent_tuple not in seen, f"{where}: duplicate exponent tuple")
        seen.add(exponent_tuple)
        h = units = 1
        for j, exponent in enumerate(exponents):
            h = _poly_mul(h, powers[j][exponent])
            if exponent:
                degree = degrees[j]
                units *= (1 << (degree * (exponent - 1))) * ((1 << degree) - 1)
        claimed_h = _polynomial(record["annihilator"], where + ".annihilator", dimension)
        _require(claimed_h == h, f"{where}: annihilator disagrees with exponent tuple")
        actual_units = _integer(record["units"], where + ".units", 1, 1 << dimension)
        _require(actual_units == units, f"{where}: incorrect unit-group cardinality")
        d = _integer(record["rotation_order"], where + ".rotation_order", 1, n)
        link_order = _integer(record["link_order"], where + ".link_order", 1, units)
        cycle = _integer(record["cycle_order"], where + ".cycle_order", 1, link_order)
        _require(n % d == 0, f"{where}: rotation order does not divide n")
        _require(units % link_order == 0, f"{where}: link order does not divide unit count")
        _require(link_order % cycle == 0, f"{where}: quotient order does not divide link order")
        identity = _poly_mod(1, h)
        _check_order(2, d, h, identity, where + ".rotation_order")
        _check_order(3, link_order, h, identity, where + ".link_order")
        rotations = set()
        value = identity
        for _ in range(d):
            rotations.add(value)
            value = _poly_mod(value << 1, h)
        _require(len(rotations) == d, f"{where}: rotation subgroup cardinality mismatch")
        _require(_poly_pow(3, cycle, h) in rotations,
                 f"{where}: cycle order fails quotient-group membership test")
        for p in set(_prime_factors(cycle)):
            _require(_poly_pow(3, cycle // p, h) not in rotations,
                     f"{where}: cycle order is not minimal (prime divisor {p})")
        orbit = d * cycle
        _require(units % orbit == 0, f"{where}: nonintegral chain count")
        chains = _integer(record["chains"], where + ".chains", 1, units)
        _require(chains == units // orbit, f"{where}: incorrect chain count")
        signature = _signature(q, d)
        _require(type(record["signature"]) is str and record["signature"] == signature,
                 f"{where}: incorrect tree signature")
        name = f"G{cycle}-{signature}"
        _require(type(record["name"]) is str and record["name"] == name,
                 f"{where}: incorrect graph name")
        words, loops, factors = _per_chain_counts(n, q, d, cycle)
        for key, expected in (("bitstrings", words), ("bitloops", loops), ("factors", factors)):
            _integer(record[key], where + "." + key, 0, 1 << n)
            _require(record[key] == expected, f"{where}: incorrect per-chain {key}")
        if name not in graphs:
            graphs[name] = {
                "n": n, "name": name, "chains": 0, "bitloops-per-chain": loops,
                "bitstrings": 0, "bitloops": 0, "factors": 0,
                "cycle-order": cycle, "tree-depth": q, "signature": signature,
            }
        graph = graphs[name]
        _require(graph["bitloops-per-chain"] == loops,
                 f"{where}: same graph type has inconsistent bitloop count")
        graph["chains"] += chains
        graph["bitstrings"] += chains * words
        graph["bitloops"] += chains * loops
        graph["factors"] += chains * factors
        total_units += units
        total_words += chains * words
        total_loops += chains * loops
        total_factors += chains * factors
        total_chains += chains
    # Valid distinct tuples with this cardinality exhaust the finite grid.
    _require(len(seen) == expected_strata, "incomplete factor-exponent grid")
    _require(total_units == 1 << dimension, "strata do not cover the periodic core")
    _require(total_words == 1 << n, "weighted bitstring total is not 2**n")
    _require(total_loops == _necklaces(n), "weighted bitloop total disagrees with Burnside count")
    _require(total_factors == _primitive_necklaces(n),
             "weighted full-period bitloop total disagrees with Mobius count")
    expected_totals = {
        "bitstrings": total_words, "bitloops": total_loops, "factors": total_factors,
        "chains": total_chains, "graphs": len(graphs),
    }
    _keys(certificate["totals"], expected_totals, "totals")
    for key, expected in expected_totals.items():
        _integer(certificate["totals"][key], "totals." + key, 0, 1 << n)
        _require(certificate["totals"][key] == expected, f"totals.{key}: incorrect total")
    graph_rows = sorted(graphs.values(), key=lambda row: (row["cycle-order"], row["signature"]))
    return {"n": n, **expected_totals}, graph_rows


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_noninteger(value):
    raise VerificationError(f"JSON contains a noninteger numeric value: {value}")


def load_certificate(path):
    """Read strict JSON: unique keys and integers only, with no NaN/Infinity."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=_unique_object,
                             parse_float=_reject_noninteger, parse_constant=_reject_noninteger)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"{path}: cannot read certificate: {error}") from error


def _verify_csv(path, header, expected_rows):
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            actual_header = next(reader, None)
            _require(actual_header == list(header), f"{path}: wrong CSV header")
            for row_number, pair in enumerate(itertools.zip_longest(reader, expected_rows), 2):
                actual, expected = pair
                _require(actual is not None, f"{path}: missing CSV row {row_number}")
                _require(expected is not None, f"{path}: extra CSV row {row_number}")
                _require(len(actual) == len(header), f"{path}:{row_number}: incorrect CSV field count")
                wanted = [str(expected[column]) for column in header]
                _require(actual == wanted,
                         f"{path}:{row_number}: row differs from verified certificates or is out of order")
    except (OSError, UnicodeError, csv.Error) as error:
        raise VerificationError(f"{path}: cannot read CSV: {error}") from error


def verify_directory(output_directory):
    """Verify every certificate and exactly matching sorted CSV aggregates."""
    output_directory = Path(output_directory)
    certificate_directory = output_directory / "certificates"
    _require(certificate_directory.is_dir(), f"missing certificate directory: {certificate_directory}")
    paths = {}
    try:
        entries = list(certificate_directory.iterdir())
    except OSError as error:
        raise VerificationError(f"cannot list certificates: {error}") from error
    for path in entries:
        match = _CERTIFICATE_NAME.fullmatch(path.name)
        _require(match is not None and path.is_file(), f"unexpected certificate-directory entry: {path.name}")
        n = int(match.group(1))
        _require(1 <= n <= 64, f"certificate filename outside n=1..64: {path.name}")
        _require(n not in paths, f"duplicate certificate for n={n}")
        paths[n] = path
    _require(paths, "no certificates found")
    powerset_rows, graph_rows = [], []
    for n, path in sorted(paths.items()):
        certificate = load_certificate(path)
        powerset_row, these_graphs = verify_certificate(certificate)
        _require(powerset_row["n"] == n, f"{path}: certificate n does not match filename")
        powerset_rows.append(powerset_row)
        graph_rows.extend(these_graphs)
    _verify_csv(output_directory / "powersets.csv", POWERSET_HEADER, powerset_rows)
    _verify_csv(output_directory / "graphs.csv", GRAPH_HEADER, graph_rows)
    return powerset_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("output_directory", nargs="?", type=Path, default=Path("output"))
    args = parser.parse_args(argv)
    try:
        rows = verify_directory(args.output_directory)
    except (VerificationError, OSError, ValueError, OverflowError, RecursionError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        return 1
    print(f"Verified {len(rows)} certificates and both CSV aggregates "
          f"(n={rows[0]['n']}..{rows[-1]['n']}; {sum(row['graphs'] for row in rows)} graph rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
