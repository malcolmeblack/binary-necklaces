import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Arrays;

/** Exact polynomials over F_2, with coefficient i stored in bit i. */
final class BinaryPolynomial {
    private static final BigInteger ZERO = BigInteger.ZERO;
    private static final BigInteger ONE = BigInteger.ONE;
    private static final BigInteger X = BigInteger.TWO;

    private BinaryPolynomial() { }

    static int degree(BigInteger p) {
        nonnegative(p);
        return p.bitLength() - 1;
    }

    static BigInteger remainder(BigInteger a, BigInteger p) {
        nonnegative(a);
        divisor(p);
        int degree = p.bitLength() - 1;
        while (a.signum() != 0 && a.bitLength() - 1 >= degree)
            a = a.xor(p.shiftLeft(a.bitLength() - 1 - degree));
        return a;
    }

    static BigInteger quotient(BigInteger a, BigInteger p) {
        nonnegative(a);
        divisor(p);
        BigInteger result = ZERO;
        int degree = p.bitLength() - 1;
        while (a.signum() != 0 && a.bitLength() - 1 >= degree) {
            int shift = a.bitLength() - 1 - degree;
            result = result.setBit(shift);
            a = a.xor(p.shiftLeft(shift));
        }
        return result;
    }

    static BigInteger divideExact(BigInteger a, BigInteger p) {
        if (remainder(a, p).signum() != 0)
            throw new ArithmeticException("Nonexact polynomial division");
        return quotient(a, p);
    }

    static BigInteger multiply(BigInteger a, BigInteger b) {
        nonnegative(a);
        nonnegative(b);
        BigInteger result = ZERO;
        if (a.equals(b)) {
            while (b.signum() != 0) {
                int bit = b.getLowestSetBit();
                result = result.setBit(Math.multiplyExact(2, bit));
                b = b.clearBit(bit);
            }
            return result;
        }
        if (a.bitCount() < b.bitCount()) {
            BigInteger swap = a; a = b; b = swap;
        }
        while (b.signum() != 0) {
            int bit = b.getLowestSetBit();
            result = result.xor(a.shiftLeft(bit));
            b = b.clearBit(bit);
        }
        return result;
    }

    static BigInteger multiplyMod(BigInteger a, BigInteger b, BigInteger p) {
        divisor(p);
        return remainder(multiply(remainder(a, p), remainder(b, p)), p);
    }

    static BigInteger powMod(BigInteger a, BigInteger exponent, BigInteger p) {
        if (exponent.signum() < 0)
            throw new IllegalArgumentException("Negative polynomial exponent");
        BigInteger result = remainder(ONE, p);
        a = remainder(a, p);
        for (int i = 0; i < exponent.bitLength(); i++) {
            if (exponent.testBit(i)) result = multiplyMod(result, a, p);
            if (i + 1 < exponent.bitLength()) a = multiplyMod(a, a, p);
        }
        return result;
    }

    static BigInteger gcd(BigInteger a, BigInteger b) {
        nonnegative(a);
        nonnegative(b);
        while (b.signum() != 0) {
            BigInteger next = remainder(a, b); a = b; b = next;
        }
        return a;
    }

    static BigInteger derivative(BigInteger p) {
        nonnegative(p);
        BigInteger result = ZERO;
        for (int i = 1; i < p.bitLength(); i += 2)
            if (p.testBit(i)) result = result.setBit(i - 1);
        return result;
    }

    /** Deterministic Berlekamp factorization; the input must be squarefree. */
    static BigInteger[] factor(BigInteger p) {
        divisor(p);
        if (p.equals(ONE)) return new BigInteger[0];
        if (!gcd(p, derivative(p)).equals(ONE))
            throw new IllegalArgumentException("Factorization requires a squarefree polynomial");
        int d = degree(p);
        BigInteger[] rows = new BigInteger[d];
        Arrays.fill(rows, ZERO);
        BigInteger column = ONE, x2 = remainder(BigInteger.valueOf(4), p);
        for (int j = 0; j < d; j++) {
            BigInteger bits = column;
            while (bits.signum() != 0) {
                int i = bits.getLowestSetBit();
                rows[i] = rows[i].setBit(j);
                bits = bits.clearBit(i);
            }
            rows[j] = rows[j].flipBit(j);
            column = multiplyMod(column, x2, p);
        }
        BigInteger[] kernel = nullspace(rows, d);
        ArrayList<BigInteger> factors = new ArrayList<>();
        factors.add(p);
        for (BigInteger v : kernel) {
            if (v.signum() == 0 || v.equals(ONE)) continue;
            int count = factors.size();
            for (int i = 0; i < count; i++) {
                BigInteger f = factors.get(i), a = gcd(f, v);
                if (!a.equals(ONE) && !a.equals(f)) {
                    factors.set(i, a);
                    factors.add(divideExact(f, a));
                }
            }
        }
        if (factors.size() != kernel.length)
            throw new IllegalStateException("Berlekamp factorization did not split completely");
        BigInteger[] result = factors.toArray(BigInteger[]::new);
        Arrays.sort(result);
        BigInteger check = ONE;
        for (BigInteger f : result) {
            verifyIrreducible(f);
            check = multiply(check, f);
        }
        if (!check.equals(p)) throw new IllegalStateException("Polynomial factor product mismatch");
        return result;
    }

    /** Rabin's irreducibility criterion, checked with exact polynomial arithmetic. */
    static void verifyIrreducible(BigInteger p) {
        int d = degree(p);
        if (d < 1) throw new IllegalArgumentException("Nonconstant polynomial required");
        boolean[] tests = new boolean[d + 1];
        int remaining = d;
        for (int prime = 2; (long) prime * prime <= remaining; prime++) {
            if (remaining % prime != 0) continue;
            tests[d / prime] = true;
            while (remaining % prime == 0) remaining /= prime;
        }
        if (remaining > 1) tests[d / remaining] = true;
        BigInteger x = remainder(X, p), value = x;
        for (int i = 1; i <= d; i++) {
            value = multiplyMod(value, value, p);
            if (tests[i] && !gcd(value.xor(x), p).equals(ONE))
                throw new IllegalArgumentException("Reducible polynomial: 0x" + p.toString(16));
        }
        if (!value.equals(x))
            throw new IllegalArgumentException("Reducible polynomial: 0x" + p.toString(16));
    }

    private static BigInteger[] nullspace(BigInteger[] rows, int columns) {
        int rank = 0;
        int[] pivots = new int[columns];
        boolean[] pivot = new boolean[columns];
        for (int c = 0; c < columns; c++) {
            int chosen = rank;
            while (chosen < rows.length && !rows[chosen].testBit(c)) chosen++;
            if (chosen == rows.length) continue;
            BigInteger tmp = rows[rank]; rows[rank] = rows[chosen]; rows[chosen] = tmp;
            for (int r = 0; r < rows.length; r++)
                if (r != rank && rows[r].testBit(c)) rows[r] = rows[r].xor(rows[rank]);
            pivots[rank] = c; pivot[c] = true; rank++;
        }
        BigInteger[] result = new BigInteger[columns - rank];
        int count = 0;
        for (int c = 0; c < columns; c++) if (!pivot[c]) {
            BigInteger vector = ONE.shiftLeft(c);
            for (int r = 0; r < rank; r++)
                if ((rows[r].and(vector).bitCount() & 1) != 0) vector = vector.setBit(pivots[r]);
            result[count++] = vector;
        }
        return result;
    }

    private static void nonnegative(BigInteger p) {
        if (p.signum() < 0) throw new IllegalArgumentException("Negative polynomial representation");
    }

    private static void divisor(BigInteger p) {
        nonnegative(p);
        if (p.signum() == 0) throw new ArithmeticException("Zero polynomial divisor");
    }
}
