#!/usr/bin/env python3
"""Independently verify v2 and earlier v2.1/v2.2/v2.3/v2.4 certificates and CSV aggregates.

Usage: python3 verify_output.py [OUTPUTDIR]

Python 3.9+ and its standard library suffice. The verifier checks polynomial
factorization, exact local orders, the complete weighted relation-lattice
calculation, graph totals, and both CSV tables without enumerating words or
chains. Old 2.1 certificates are checked by the preserved verify_v21 module.

Public API: load_certificate(path), verify_certificate(dictionary), and
verify_directory(path). Their signatures match version 2.1. The additional
verify_factor_data(dictionary) and load_factor_data(path=None) APIs check the
bundled integer-factorization hints and recursive primality certificates.
All arithmetic counts are arbitrary-precision integers; no output files
are modified, and no network access or third-party modules are needed.
"""

import argparse
from functools import lru_cache
import math
from pathlib import Path
import sys

import verify_v21 as legacy

VerificationError = legacy.VerificationError
POWERSET_HEADER = legacy.POWERSET_HEADER
GRAPH_HEADER = legacy.GRAPH_HEADER
load_certificate = legacy.load_certificate
_require = legacy._require
_keys = legacy._keys
_integer = legacy._integer
_polynomial = legacy._polynomial
_poly_mul = legacy._poly_mul
_poly_mod = legacy._poly_mod
_poly_pow = legacy._poly_pow

_TOP_KEYS = {
    "schema_version", "n", "q", "core_polynomial", "annihilator_strata",
    "irreducible_factors", "states", "totals",
}
_FACTOR_KEYS = {"polynomial", "degree", "multiplicity", "powers"}
_POWER_KEYS = {
    "exponent", "units", "rotation_order", "link_order", "cycle_order",
    "rotation_shift",
}
_STATE_KEYS = {
    "rotation_order", "cycle_order", "rotation_shift", "units", "chains",
    "bitstrings", "bitloops", "factors", "name", "signature",
}


def _decimal(value, where, upper=(1 << 1024)):
    """Parse the canonical positive decimal strings used in factor hints."""
    _require(type(value) is str and 1 <= len(value) <= 309
             and value.isascii() and value.isdecimal() and value[0] != "0",
             f"{where}: expected a canonical positive decimal string")
    result = int(value)
    _require(result < upper, f"{where}: integer is outside the supported range")
    return result


def _required_degrees():
    """All ord_m(2), for odd 1<m<=1023, are the possible factor degrees."""
    degrees = set()
    for odd in range(3, 1024, 2):
        value, degree = 2 % odd, 1
        while value != 1:
            value = value * 2 % odd
            degree += 1
        degrees.add(degree)
    return degrees


def verify_factor_data(data):
    """Prove every factorization and primality certificate in a data object.

    Small primes use the deterministic Miller--Rabin test below 2**64 only.
    Larger primes use Pocklington's theorem: a proved factor F of p-1 must
    exceed sqrt(p), and a common witness must satisfy the power and gcd
    conditions for every prime dividing F. Recursive factors must be smaller
    than p. Full factorization of p-1 is permitted but is not required.

    Require complete coverage of all possible factor degrees for n<=1024.
    Return {degree: tuple(prime_factors_with_multiplicity)}. This function
    deliberately does not use a cache, so callers can independently check
    modified or untrusted data without inheriting a previous successful check.
    """
    _keys(data, {"schema_version", "mersenne_factors", "prime_certificates"},
          "integer factor data")
    _require(data["schema_version"] == "1", "unsupported integer-factor schema")
    raw_factors = data["mersenne_factors"]
    raw_proofs = data["prime_certificates"]
    _require(type(raw_factors) is dict and raw_factors,
             "mersenne_factors: expected a nonempty object")
    _require(type(raw_proofs) is dict, "prime_certificates: expected an object")
    proofs = {}
    for text, record in raw_proofs.items():
        p = _decimal(text, "prime_certificates key")
        _require(p >= (1 << 64), "prime certificates are reserved for integers at least 2**64")
        where = f"prime_certificates[{p}]"
        _keys(record, {"factors", "witness"}, where)
        _require(type(record["factors"]) is list and 1 <= len(record["factors"]) <= 1024,
                 f"{where}.factors: expected a factorization of at most 1024 entries")
        known = 1
        previous = 1
        factors = []
        for index, pair in enumerate(record["factors"]):
            _require(type(pair) is list and len(pair) == 2,
                     f"{where}.factors[{index}]: expected [prime, exponent]")
            factor = _decimal(pair[0], f"{where}.factors[{index}][0]", p)
            _require(factor > previous,
                     f"{where}: factors must be distinct primes in increasing order")
            previous = factor
            exponent = _integer(pair[1], f"{where}.factors[{index}][1]", 1,
                                min(1023, p.bit_length()))
            known *= factor ** exponent
            _require(known <= p - 1, f"{where}: known factor product exceeds p-1")
            factors.append(factor)
        _require((p - 1) % known == 0, f"{where}: known factor product does not divide p-1")
        _require(known * known > p, f"{where}: Pocklington factor product is too small")
        witness = _decimal(record["witness"], where + ".witness", p)
        _require(witness >= 2, f"{where}: witness must be at least 2")
        proofs[p] = (tuple(factors), witness)

    proved = set()

    def prove(p):
        if p in proved:
            return
        if p in proofs:
            factors, witness = proofs[p]
            for factor in factors:
                prove(factor)
            _require(pow(witness, p - 1, p) == 1,
                     f"prime {p}: Pocklington witness does not give the identity")
            for factor in factors:
                _require(math.gcd(pow(witness, (p - 1) // factor, p) - 1, p) == 1,
                         f"prime {p}: invalid Pocklington witness for factor {factor}")
        else:
            _require(2 <= p < (1 << 64), f"prime {p}: missing exact primality certificate")
            _require(legacy._prime(p), f"integer factor {p} is not prime")
        proved.add(p)

    # Validate supplied certificates even when no Mersenne entry uses them.
    for p in sorted(proofs):
        prove(p)
    result = {}
    for text, entries in raw_factors.items():
        degree = _decimal(text, "mersenne_factors key", 1024)
        where = f"mersenne_factors[{degree}]"
        _require(type(entries) is list and 1 <= len(entries) <= degree,
                 f"{where}: expected a nonempty array of at most {degree} factors")
        factors = tuple(_decimal(entry, where + " factor") for entry in entries)
        _require(list(factors) == sorted(factors), f"{where}: factors must be sorted")
        _require(math.prod(factors) == (1 << degree) - 1,
                 f"{where}: integer factorization product mismatch")
        for factor in factors:
            prove(factor)
        result[degree] = factors
    _require(set(result) == _required_degrees(),
             "integer factor data does not cover exactly the degrees required for n<=1024")
    return result


def load_factor_data(path=None):
    """Load and exactly verify factor data; default to the bundled JSON file."""
    if path is None:
        path = Path(__file__).resolve().with_name("order-factors.json")
    return verify_factor_data(load_certificate(path))


@lru_cache(maxsize=1)
def _verified_factor_data():
    return load_factor_data()


def _intersection(left, right):
    """Intersect relation lattices (d,t,s) by a bounded congruence search.

    Such a key denotes {(i,j): j=k*t, i=-k*s (mod d)}. Periods divide
    n<=1024. Only the congruence solution is searched, never the large link
    order or any polynomial unit group.
    """
    da, ta, sa = left
    db, tb, sb = right
    base = math.lcm(ta, tb)
    common = math.gcd(da, db)
    difference = (base // ta * sa - base // tb * sb) % common
    cycle = base * (common // math.gcd(common, difference))
    period = math.lcm(da, db)
    ra, rb = (cycle // ta * sa) % da, (cycle // tb * sb) % db
    shift = next((s for s in range(ra, period, da) if s % db == rb), None)
    _require(shift is not None, "inconsistent lattice intersection")
    return period, cycle, shift


@lru_cache(maxsize=None)
def _bound_primes(degree):
    """Use exactly proved factors of 2**degree-1, never probable primes."""
    factors = _verified_factor_data()
    _require(degree in factors, f"missing exact integer factorization for degree {degree}")
    return tuple(sorted(set(factors[degree])))


def _check_order(base, order, modulus, bound, primes, where):
    _require(bound % order == 0, f"{where}: order does not divide its group bound")
    _require(_poly_pow(base, order, modulus) == 1,
             f"{where}: order does not give the identity")
    for prime in primes:
        if order % prime == 0:
            _require(_poly_pow(base, order // prime, modulus) != 1,
                     f"{where}: order is not minimal (prime divisor {prime})")


def _check_local(record, factor, degree, exponent, n, q, where):
    _keys(record, _POWER_KEYS, where)
    _require(_integer(record["exponent"], where + ".exponent", 1, q) == exponent,
             f"{where}: missing, repeated, or out-of-order factor power")
    units = ((1 << degree) - 1) << (degree * (exponent - 1))
    _require(_integer(record["units"], where + ".units", 1, 1 << (n - q)) == units,
             f"{where}: incorrect unit count")
    period = _integer(record["rotation_order"], where + ".rotation_order", 1, n)
    _require(n % period == 0, f"{where}: rotation order does not divide n")
    link_order = _integer(record["link_order"], where + ".link_order", 1, units)
    cycle = _integer(record["cycle_order"], where + ".cycle_order", 1, link_order)
    shift = _integer(record["rotation_shift"], where + ".rotation_shift", 0, period - 1)
    _require(link_order % cycle == 0, f"{where}: cycle order does not divide link order")
    _check_order(2, period, factor, n, set(legacy._prime_factors(n)),
                 where + ".rotation_order")
    bound = ((1 << degree) - 1) * q
    primes = set(_bound_primes(degree)) | ({2} if q > 1 else set())
    _check_order(3, link_order, factor, bound, primes, where + ".link_order")
    rotations = set()
    value = 1
    for _ in range(period):
        rotations.add(value)
        value = _poly_mod(value << 1, factor)
    linked = _poly_pow(3, cycle, factor)
    _require(linked == _poly_pow(2, shift, factor),
             f"{where}: cycle and rotation shift do not give the same polynomial")
    for prime in primes:
        if cycle % prime == 0:
            _require(_poly_pow(3, cycle // prime, factor) not in rotations,
                     f"{where}: cycle order is not minimal (prime divisor {prime})")
    _require(link_order == cycle * period // math.gcd(period, shift),
             f"{where}: link order disagrees with the exact relation lattice")
    _require(units % (period * cycle) == 0, f"{where}: nonintegral local orbit count")
    return (period, cycle, shift), units


def _verify_lattice(certificate, maximum_n):
    _keys(certificate, _TOP_KEYS, "certificate")
    n = _integer(certificate["n"], "n", 1, maximum_n)
    q = _integer(certificate["q"], "q", 1, maximum_n)
    _require(q == n & -n, "q must be the largest power of two dividing n")
    dimension = n - q
    expected_core = sum(1 << (i * q) for i in range(n // q))
    core = _polynomial(certificate["core_polynomial"], "core_polynomial", dimension)
    _require(core == expected_core, "incorrect core polynomial")
    factor_records = certificate["irreducible_factors"]
    _require(type(factor_records) is list and len(factor_records) <= dimension,
             "irreducible_factors: expected an array with at most core-degree entries")
    product, previous = 1, 0
    weights = {(1, 1, 0): 1}
    for index, record in enumerate(factor_records):
        where = f"n={n} irreducible_factors[{index}]"
        _keys(record, _FACTOR_KEYS, where)
        polynomial = _polynomial(record["polynomial"], where + ".polynomial", dimension)
        _require(polynomial > previous, f"{where}: factors are duplicated or out of order")
        previous = polynomial
        degree = _integer(record["degree"], where + ".degree", 1, dimension)
        _require(degree == polynomial.bit_length() - 1, f"{where}: incorrect degree")
        _require(legacy._irreducible(polynomial), f"{where}: polynomial is reducible")
        _require(_integer(record["multiplicity"], where + ".multiplicity", 1, q) == q,
                 f"{where}: factor multiplicity must equal q")
        powers = record["powers"]
        _require(type(powers) is list and len(powers) == q,
                 f"{where}: expected all {q} nonzero factor powers")
        choices = [((1, 1, 0), 1)]
        power = 1
        for exponent, local in enumerate(powers, 1):
            power = _poly_mul(power, polynomial)
            choices.append(_check_local(local, power, degree, exponent, n, q,
                                        f"{where}.powers[{exponent - 1}]"))
        product = _poly_mul(product, power)
        _require(product.bit_length() <= dimension + 1, "factorization exceeds core degree")
        combined = {}
        for old_lattice, old_weight in weights.items():
            for local_lattice, local_weight in choices:
                lattice = _intersection(old_lattice, local_lattice)
                combined[lattice] = combined.get(lattice, 0) + old_weight * local_weight
        weights = combined
    _require(product == core, "irreducible factorization does not multiply to core polynomial")
    strata = (q + 1) ** len(factor_records)
    _require(_integer(certificate["annihilator_strata"], "annihilator_strata", 1) == strata,
             "incorrect implicit annihilator-stratum count")
    records = certificate["states"]
    _require(type(records) is list and len(records) == len(weights),
             "states: missing or extra relation states")
    graphs = {}
    total_units = total_words = total_loops = total_factors = total_chains = 0
    for index, (record, (lattice, units)) in enumerate(zip(records, sorted(weights.items()))):
        where = f"n={n} states[{index}]"
        _keys(record, _STATE_KEYS, where)
        period, cycle, shift = lattice
        for key, expected in (("rotation_order", period), ("cycle_order", cycle),
                              ("rotation_shift", shift), ("units", units)):
            _integer(record[key], where + "." + key, 0, 1 << n)
            _require(record[key] == expected, f"{where}: incorrect or out-of-order {key}")
        orbit = period * cycle
        _require(units % orbit == 0, f"{where}: nonintegral chain count")
        chains = units // orbit
        _require(_integer(record["chains"], where + ".chains", 1, 1 << dimension) == chains,
                 f"{where}: incorrect chain count")
        signature = legacy._signature(q, period)
        _require(type(record["signature"]) is str and record["signature"] == signature,
                 f"{where}: incorrect tree signature")
        name = f"G{cycle}-{signature}"
        _require(type(record["name"]) is str and record["name"] == name,
                 f"{where}: incorrect graph name")
        words, loops, factors = legacy._per_chain_counts(n, q, period, cycle)
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
    _require(total_units == 1 << dimension, "relation states do not cover the periodic core")
    _require(total_words == 1 << n, "weighted bitstring total is not 2**n")
    _require(total_loops == legacy._necklaces(n), "bitloop total disagrees with Burnside count")
    _require(total_factors == legacy._primitive_necklaces(n),
             "full-period bitloop total disagrees with Mobius count")
    totals = {"bitstrings": total_words, "bitloops": total_loops,
              "factors": total_factors, "chains": total_chains, "graphs": len(graphs)}
    _keys(certificate["totals"], totals, "totals")
    for key, expected in totals.items():
        _integer(certificate["totals"][key], "totals." + key, 0, 1 << n)
        _require(certificate["totals"][key] == expected, f"totals.{key}: incorrect total")
    graph_rows = sorted(graphs.values(), key=lambda row: (row["cycle-order"], row["signature"]))
    return {"n": n, **totals}, graph_rows


def verify_certificate(certificate):
    """Verify a decoded 2 or earlier 2.1/2.2/2.3/2.4 certificate; return powerset and graph rows."""
    _require(type(certificate) is dict, "certificate: expected an object")
    version = certificate.get("schema_version")
    if version == "2.1":
        return legacy.verify_certificate(certificate)
    maxima = {"2.2": 128, "2.3": 256, "2.4": 512, "2": 1024}
    _require(type(version) is str and version in maxima, "unsupported schema_version")
    return _verify_lattice(certificate, maxima[version])


def verify_directory(output_directory):
    """Verify all certificates and exactly matching sorted CSV aggregates."""
    output_directory = Path(output_directory)
    certificate_directory = output_directory / "certificates"
    _require(certificate_directory.is_dir(), f"missing certificate directory: {certificate_directory}")
    paths = {}
    try:
        entries = list(certificate_directory.iterdir())
    except OSError as error:
        raise VerificationError(f"cannot list certificates: {error}") from error
    for path in entries:
        match = legacy._CERTIFICATE_NAME.fullmatch(path.name)
        _require(match is not None and path.is_file(), f"unexpected certificate-directory entry: {path.name}")
        n = int(match.group(1))
        _require(1 <= n <= 1024, f"certificate filename outside n=1..1024: {path.name}")
        _require(n not in paths, f"duplicate certificate for n={n}")
        paths[n] = path
    _require(paths, "no certificates found")
    powerset_rows, graph_rows = [], []
    for n, path in sorted(paths.items()):
        powerset_row, these_graphs = verify_certificate(load_certificate(path))
        _require(powerset_row["n"] == n, f"{path}: certificate n does not match filename")
        powerset_rows.append(powerset_row)
        graph_rows.extend(these_graphs)
    legacy._verify_csv(output_directory / "powersets.csv", POWERSET_HEADER, powerset_rows)
    legacy._verify_csv(output_directory / "graphs.csv", GRAPH_HEADER, graph_rows)
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
