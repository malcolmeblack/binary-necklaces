import java.math.BigInteger;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/** Exact factorization support for the finite-field order bounds used through n=1024. */
final class ExactInteger {
    private static final BigInteger ONE = BigInteger.ONE;
    private static final BigInteger TWO = BigInteger.TWO;
    private static final int[] SMALL = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37};
    // This Miller--Rabin base set is deterministic only for integers below 2^64.
    private static final long[] BASES = {2, 325, 9375, 28178, 450775, 9780504, 1795265022};
    private static final ConcurrentHashMap<BigInteger, BigInteger[]> CACHE = new ConcurrentHashMap<>();

    // Every factor and primality witness is checked once before any order is used.
    private static final Map<Integer, BigInteger[]> ORDER_FACTORS =
            verifyFactorData(Json.parse(OrderFactorData.JSON));

    private ExactInteger() { }

    /** Validate an untrusted factor dataset. Used by the startup check and tests. */
    static Map<Integer, BigInteger[]> verifyFactorData(Object raw) {
        Map<?, ?> data = object(raw, Set.of("schema_version", "mersenne_factors", "prime_certificates"));
        if (!"1".equals(data.get("schema_version"))) throw bad("Unsupported integer factor data schema");
        if (!(data.get("mersenne_factors") instanceof Map<?, ?> mersenne)
                || !(data.get("prime_certificates") instanceof Map<?, ?> proofs))
            throw bad("Integer factor data must contain objects");
        Set<Integer> needed = new TreeSet<>();
        for (int m = 3; m <= 1023; m += 2) {
            int residue = 2 % m, degree = 1;
            while (residue != 1) { residue = (2 * residue) % m; degree++; }
            needed.add(degree);
        }
        Set<String> keys = new TreeSet<>();
        for (int degree : needed) keys.add(Integer.toString(degree));
        if (!mersenne.keySet().equals(keys)) throw bad("Incomplete or unsupported order-bound degree set");
        Set<BigInteger> proved = new HashSet<>();
        for (Object key : proofs.keySet()) {
            BigInteger prime = decimal(key);
            if (prime.bitLength() <= 64 || prime.bitLength() > 1024)
                throw bad("Wide-prime certificate is outside its supported range");
            provePrime(prime, proofs, proved);
        }
        Map<Integer, BigInteger[]> result = new TreeMap<>();
        for (int degree : needed) {
            Object entry = mersenne.get(Integer.toString(degree));
            if (!(entry instanceof List<?> list) || list.isEmpty() || list.size() > degree)
                throw bad("Invalid Mersenne factor list");
            BigInteger previous = ONE, product = ONE;
            BigInteger[] primes = new BigInteger[list.size()];
            for (int i = 0; i < primes.length; i++) {
                BigInteger prime = decimal(list.get(i));
                if (prime.compareTo(TWO) < 0 || prime.compareTo(previous) < 0)
                    throw bad("Mersenne factors must be sorted primes");
                provePrime(prime, proofs, proved);
                product = product.multiply(prime);
                primes[i] = prime; previous = prime;
            }
            if (!product.equals(ONE.shiftLeft(degree).subtract(ONE)))
                throw bad("Mersenne factor product mismatch at degree " + degree);
            result.put(degree, primes);
        }
        return Collections.unmodifiableMap(result);
    }

    /** Pocklington: F divides p-1, F^2>p, and each prime divisor of F has a witness. */
    private static void provePrime(BigInteger prime, Map<?, ?> proofs, Set<BigInteger> proved) {
        if (proved.contains(prime)) return;
        if (prime.bitLength() <= 64) {
            if (!prime64(prime)) throw bad("Composite integer in factor data: " + prime);
            proved.add(prime); return;
        }
        if (prime.bitLength() > 1024) throw bad("Integer certificate exceeds supported bound");
        Map<?, ?> proof = object(proofs.get(prime.toString()), Set.of("factors", "witness"));
        if (!(proof.get("factors") instanceof List<?> list) || list.isEmpty() || list.size() > 1024)
            throw bad("Invalid Pocklington factor list");
        BigInteger minusOne = prime.subtract(ONE), product = ONE, previous = ONE;
        List<BigInteger> divisors = new ArrayList<>();
        for (Object entry : list) {
            if (!(entry instanceof List<?> pair) || pair.size() != 2)
                throw bad("Invalid Pocklington factor pair");
            BigInteger q = decimal(pair.get(0));
            int exponent = exponent(pair.get(1));
            if (q.compareTo(previous) <= 0 || q.compareTo(TWO) < 0 || q.compareTo(prime) >= 0)
                throw bad("Pocklington factors must be distinct sorted smaller primes");
            provePrime(q, proofs, proved);
            product = product.multiply(q.pow(exponent));
            if (product.compareTo(minusOne) > 0) throw bad("Pocklington factor product exceeds p-1");
            divisors.add(q); previous = q;
        }
        if (minusOne.mod(product).signum() != 0 || product.multiply(product).compareTo(prime) <= 0)
            throw bad("Insufficient Pocklington factor product");
        BigInteger a = decimal(proof.get("witness"));
        if (a.compareTo(TWO) < 0 || a.compareTo(prime) >= 0 || !a.modPow(minusOne, prime).equals(ONE))
            throw bad("Invalid Pocklington witness");
        for (BigInteger q : divisors)
            if (!a.modPow(minusOne.divide(q), prime).subtract(ONE).gcd(prime).equals(ONE))
                throw bad("Pocklington witness lacks required order");
        proved.add(prime);
    }

    private static Map<?, ?> object(Object value, Set<String> fields) {
        if (!(value instanceof Map<?, ?> map) || !map.keySet().equals(fields))
            throw bad("Integer factor certificate fields mismatch");
        return map;
    }

    private static BigInteger decimal(Object value) {
        if (!(value instanceof String text) || !text.matches("[1-9][0-9]{0,308}"))
            throw bad("Expected a canonical positive decimal integer string");
        BigInteger result = new BigInteger(text);
        if (result.bitLength() > 1024) throw bad("Integer certificate exceeds supported bound");
        return result;
    }

    private static int exponent(Object value) {
        if (!(value instanceof BigInteger || value instanceof Integer || value instanceof Long))
            throw bad("Expected an integer exponent");
        BigInteger exponent = new BigInteger(value.toString());
        if (exponent.signum() <= 0 || exponent.compareTo(BigInteger.valueOf(1023)) > 0)
            throw bad("Integer proof exponent is outside supported range");
        return exponent.intValueExact();
    }

    private static IllegalArgumentException bad(String message) { return new IllegalArgumentException(message); }


    /** Distinct prime divisors, sorted ascending. Every returned prime is proved. */
    static BigInteger[] primeFactors(BigInteger n) {
        if (n.signum() <= 0) throw new IllegalArgumentException("Positive integer required");
        BigInteger[] cached = CACHE.get(n);
        if (cached != null) return cached.clone();
        TreeSet<BigInteger> result = new TreeSet<>();
        factor(n, result);
        // Independently check that the distinct prime set accounts for every factor.
        BigInteger remainder = n;
        for (BigInteger prime : result) {
            if (prime.bitLength() <= 64) {
                if (!prime64(prime)) throw new IllegalStateException("Unproved integer prime");
            } else {
                boolean supplied = ORDER_FACTORS.values().stream()
                        .anyMatch(factors -> Arrays.asList(factors).contains(prime));
                if (!supplied) throw new IllegalStateException("Unproved wide integer prime");
            }
            if (remainder.mod(prime).signum() != 0)
                throw new IllegalStateException("Spurious integer factor");
            do { remainder = remainder.divide(prime); }
            while (remainder.mod(prime).signum() == 0);
        }
        if (!remainder.equals(ONE)) throw new IllegalStateException("Integer factor product mismatch");
        BigInteger[] answer = result.toArray(BigInteger[]::new);
        CACHE.putIfAbsent(n, answer);
        return answer.clone();
    }

    private static void factor(BigInteger n, TreeSet<BigInteger> result) {
        if (n.equals(ONE)) return;
        BigInteger[] cached = CACHE.get(n);
        if (cached != null) {
            for (BigInteger prime : cached) result.add(prime);
            return;
        }
        int twos = n.getLowestSetBit();
        if (twos > 0) {
            result.add(TWO);
            factor(n.shiftRight(twos), result);
            return;
        }
        BigInteger successor = n.add(ONE);
        if (successor.bitCount() == 1) {
            BigInteger[] supplied = ORDER_FACTORS.get(successor.bitLength() - 1);
            if (supplied != null) {
                result.addAll(Arrays.asList(supplied));
                return;
            }
        }
        if (n.bitLength() > 64)
            throw new ArithmeticException("No certified integer factorization supplied for " + n);
        if (prime64(n)) {
            result.add(n);
            return;
        }
        BigInteger divisor = rho(n);
        factor(divisor, result);
        factor(n.divide(divisor), result);
    }

    /** Deterministic Miller--Rabin; rejects use outside its proved range. */
    private static boolean prime64(BigInteger n) {
        if (n.bitLength() > 64)
            throw new ArithmeticException("64-bit primality test received a wider integer");
        if (n.compareTo(TWO) < 0) return false;
        for (int small : SMALL) {
            BigInteger p = BigInteger.valueOf(small);
            if (n.mod(p).signum() == 0) return n.equals(p);
        }
        BigInteger minusOne = n.subtract(ONE);
        int s = minusOne.getLowestSetBit();
        BigInteger d = minusOne.shiftRight(s);
        for (long base : BASES) {
            BigInteger a = BigInteger.valueOf(base).mod(n);
            if (a.signum() == 0) continue;
            BigInteger x = a.modPow(d, n);
            if (x.equals(ONE) || x.equals(minusOne)) continue;
            boolean passed = false;
            for (int r = 1; r < s; r++) {
                x = x.multiply(x).mod(n);
                if (x.equals(minusOne)) { passed = true; break; }
            }
            if (!passed) return false;
        }
        return true;
    }

    /** Deterministic-seeded, bounded Pollard--Brent search; failure is explicit. */
    private static BigInteger rho(BigInteger n) {
        for (int small : SMALL) {
            BigInteger p = BigInteger.valueOf(small);
            if (n.mod(p).signum() == 0) return p;
        }
        for (int attempt = 1; attempt <= 32; attempt++) {
            BigInteger y = BigInteger.valueOf(2L + attempt);
            BigInteger c = BigInteger.valueOf(2L * attempt + 1);
            BigInteger g = ONE, saved = y, x = y;
            int r = 1, steps = 0;
            while (g.equals(ONE) && steps < 262144) {
                x = y;
                for (int i = 0; i < r; i++) y = advance(y, c, n);
                steps += r;
                int k = 0;
                while (k < r && g.equals(ONE)) {
                    saved = y;
                    BigInteger product = ONE;
                    int batch = Math.min(128, r - k);
                    for (int i = 0; i < batch; i++) {
                        y = advance(y, c, n);
                        product = product.multiply(x.subtract(y).abs()).mod(n);
                    }
                    g = product.gcd(n);
                    k += batch;
                    steps += batch;
                }
                r *= 2;
            }
            if (g.equals(n)) {
                for (int i = 0; i < 4096; i++) {
                    saved = advance(saved, c, n);
                    g = x.subtract(saved).abs().gcd(n);
                    if (g.compareTo(ONE) > 0) break;
                }
            }
            if (g.compareTo(ONE) > 0 && g.compareTo(n) < 0) return g;
        }
        throw new ArithmeticException("Bounded integer factorization did not finish for " + n);
    }

    private static BigInteger advance(BigInteger x, BigInteger c, BigInteger modulus) {
        return x.multiply(x).add(c).mod(modulus);
    }
}
