"""Focused checks for exact arithmetic and the repeated-factor lattice lift."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import finitefield as ff
from shared import numbertheory as nt
from shared.census import _base_relation, _lift_relation, relation_for_modulus


def trial_prime(n):
    return n >= 2 and all(n % d for d in range(2, int(n ** 0.5) + 1))


def polynomial_power(f, exponent):
    value = 1
    for _ in range(exponent):
        value = ff.multiply(value, f)
    return value


def direct_relation(modulus):
    """Enumerate operator residues only, independently of order/factor logic."""
    rotations, value = {}, 1
    while value not in rotations:
        rotations[value] = len(rotations)
        value = ff.multiply_mod(value, 2, modulus)
    assert value == 1
    d = len(rotations)
    value, t = ff.remainder(3, modulus), 1
    while value not in rotations:
        value = ff.multiply_mod(value, 3, modulus)
        t += 1
        assert t < 10000
    return d, t, rotations[value]


class ExactIntegerTests(unittest.TestCase):
    def test_small_factorizations(self):
        for n in range(1, 500):
            factors = nt.factor_integer(n)
            product = 1
            for p, e in factors.items():
                self.assertTrue(trial_prime(p))
                product *= p ** e
            self.assertEqual(product, n)

    def test_strong_pseudoprime_is_factored(self):
        # These composite inputs defeat several familiar short base lists.
        self.assertEqual(nt.factor_integer(3215031751), {151: 1, 751: 1, 28351: 1})
        self.assertEqual(nt.factor_integer(341550071728321), {10670053: 1, 32010157: 1})

    def test_large_prime_has_independent_lucas_lehmer_check(self):
        exponent = 89
        prime = (1 << exponent) - 1
        self.assertTrue(trial_prime(exponent))
        residue = 4
        for _ in range(exponent - 2):
            residue = (residue * residue - 2) % prime
        self.assertEqual(residue, 0)  # Independent Mersenne primality criterion.
        factorer = nt._Factorer(None)
        self.assertEqual(factorer.factor(prime), {prime: 1})
        self.assertIn(prime - 1, factorer.factors)  # Lucas n-1 proof was required.

    def test_probable_prime_is_not_accepted_without_proof(self):
        composite = (1 << 64) + 1
        actual = nt._miller_rabin
        # Force the large-input screen to pass. The exact certificate must
        # still reject this composite; screening is not the final criterion.
        with patch.object(nt, "_miller_rabin", side_effect=lambda n, bases, check=None: True if n == composite else actual(n, bases, check)):
            self.assertFalse(nt._Factorer(None).prime(composite))
        self.assertEqual(nt.factor_integer(composite), {274177: 1, 67280421310721: 1})

    def test_resource_limits_are_explicit(self):
        with self.assertRaises(nt.ComputationLimit):
            nt.factor_integer((1 << 4097) - 1)

        def stop():
            raise TimeoutError("test deadline")

        with self.assertRaises(TimeoutError):
            nt.factor_integer((1 << 89) - 1, stop)


class PolynomialTests(unittest.TestCase):
    def test_squarefree_factorization_and_rabin(self):
        for odd in range(1, 32, 2):
            polynomial = (1 << odd) - 1
            product = 1
            for f in ff.factor_squarefree(polynomial):
                ff.verify_irreducible(f)
                product = ff.multiply(product, f)
            self.assertEqual(product, polynomial)
        with self.assertRaises(ArithmeticError):
            ff.verify_irreducible(0b10101)  # (x^2+x+1)^2.

    def test_mixed_multiplicities(self):
        # Include both odd and even multiplicities and x+1, which is excluded
        # from the invertible part but must work in the general factor routine.
        expected = {0b11: 3, 0b111: 5, 0b1011: 2, 0b1101: 4}
        polynomial = 1
        for f, exponent in expected.items():
            polynomial = ff.multiply(polynomial, polynomial_power(f, exponent))
        self.assertEqual(ff.factor_with_multiplicity(polynomial), expected)

    def test_lattice_lift_against_direct_operator_enumeration(self):
        for f, odd_period in ((0b111, 3), (0b1011, 7), (0b1101, 7), (0b11111, 5)):
            base = _base_relation(f, odd_period, None, {})
            for exponent in range(1, 9):
                modulus = polynomial_power(f, exponent)
                expected = direct_relation(modulus)
                self.assertEqual(_lift_relation(base, exponent), expected)
                n = odd_period * (1 << (exponent - 1).bit_length())
                self.assertEqual(relation_for_modulus(modulus, n), expected)


if __name__ == "__main__":
    unittest.main()
