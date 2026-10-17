import java.util.ArrayList;
import java.util.Arrays;

/** Binary polynomials of degree at most 63, encoded coefficient-first in a long. */
final class GF2 {
    private GF2() { }
    static int degree(long p) { return 63 - Long.numberOfLeadingZeros(p); }
    static long remainder(long a, long p) {
        if (p == 0) throw new ArithmeticException("Zero polynomial divisor");
        int d = degree(p);
        while (a != 0 && degree(a) >= d) a ^= p << (degree(a) - d);
        return a;
    }
    static long quotient(long a, long p) {
        if (p == 0) throw new ArithmeticException("Zero polynomial divisor");
        long result = 0;
        int d = degree(p);
        while (a != 0 && degree(a) >= d) {
            int shift = degree(a) - d;
            result ^= 1L << shift; a ^= p << shift;
        }
        return result;
    }
    static long divideExact(long a, long p) {
        if (remainder(a, p) != 0) throw new ArithmeticException("Nonexact polynomial division");
        return quotient(a, p);
    }
    static long multiply(long a, long b) {
        if (a != 0 && b != 0 && degree(a) + degree(b) > 63)
            throw new ArithmeticException("Polynomial product exceeds a long");
        long result = 0;
        while (b != 0) {
            if ((b & 1) != 0) result ^= a;
            a <<= 1; b >>>= 1;
        }
        return result;
    }
    static long multiplyMod(long a, long b, long p) {
        if (p == 0) throw new ArithmeticException("Zero polynomial modulus");
        int d = degree(p);
        if (d < 1) return 0;
        a = remainder(a, p); b = remainder(b, p);
        long result = 0, high = 1L << (d - 1);
        while (b != 0) {
            if ((b & 1) != 0) result ^= a;
            boolean carry = (a & high) != 0;
            a <<= 1;
            if (carry) a ^= p;
            b >>>= 1;
        }
        return result;
    }
    static long powMod(long a, long exponent, long p) {
        if (exponent < 0) throw new IllegalArgumentException("Negative polynomial exponent");
        long result = remainder(1, p);
        a = remainder(a, p);
        while (exponent != 0) {
            if ((exponent & 1) != 0) result = multiplyMod(result, a, p);
            exponent >>>= 1;
            if (exponent != 0) a = multiplyMod(a, a, p);
        }
        return result;
    }
    static long gcd(long a, long b) {
        while (b != 0) { long r = remainder(a, b); a = b; b = r; }
        return a;
    }
    static long derivative(long p) { return (p & 0xAAAAAAAAAAAAAAAAL) >>> 1; }

    /** Deterministic Berlekamp factorization. Input must be squarefree. */
    static long[] factor(long p) {
        if (p == 0) throw new IllegalArgumentException("Cannot factor zero");
        if (p == 1) return new long[0];
        if (gcd(p, derivative(p)) != 1)
            throw new IllegalArgumentException("Factorization requires a squarefree polynomial");
        int d = degree(p);
        long[] rows = new long[d];
        long column = 1, x2 = remainder(4, p);
        for (int j = 0; j < d; j++) {
            long bits = column;
            while (bits != 0) {
                int i = Long.numberOfTrailingZeros(bits);
                rows[i] |= 1L << j; bits &= bits - 1;
            }
            rows[j] ^= 1L << j;
            column = multiplyMod(column, x2, p);
        }
        long[] kernel = nullspace(rows, d);
        ArrayList<Long> factors = new ArrayList<>(); factors.add(p);
        for (long v : kernel) {
            if (v == 0 || v == 1) continue;
            int count = factors.size();
            for (int i = 0; i < count; i++) {
                long f = factors.get(i), a = gcd(f, v);
                if (a != 1 && a != f) {
                    factors.set(i, a); factors.add(divideExact(f, a));
                }
            }
        }
        if (factors.size() != kernel.length)
            throw new IllegalStateException("Berlekamp factorization did not split completely");
        long[] result = new long[factors.size()];
        for (int i = 0; i < result.length; i++) result[i] = factors.get(i);
        Arrays.sort(result);
        long check = 1;
        for (long f : result) check = multiply(check, f);
        if (check != p) throw new IllegalStateException("Polynomial factor product mismatch");
        return result;
    }
    private static long[] nullspace(long[] rows, int columns) {
        int rank = 0;
        int[] pivots = new int[columns];
        boolean[] pivot = new boolean[columns];
        for (int c = 0; c < columns; c++) {
            int chosen = rank;
            while (chosen < rows.length && ((rows[chosen] >>> c) & 1) == 0) chosen++;
            if (chosen == rows.length) continue;
            long tmp = rows[rank]; rows[rank] = rows[chosen]; rows[chosen] = tmp;
            for (int r = 0; r < rows.length; r++)
                if (r != rank && ((rows[r] >>> c) & 1) != 0) rows[r] ^= rows[rank];
            pivots[rank] = c; pivot[c] = true; rank++;
        }
        long[] result = new long[columns - rank];
        int count = 0;
        for (int c = 0; c < columns; c++) if (!pivot[c]) {
            long vector = 1L << c;
            for (int r = 0; r < rank; r++)
                if ((Long.bitCount(rows[r] & vector) & 1) != 0) vector |= 1L << pivots[r];
            result[count++] = vector;
        }
        return result;
    }
}
