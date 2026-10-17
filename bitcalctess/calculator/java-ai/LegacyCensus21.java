import java.math.BigInteger;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.BiConsumer;

/**
 * Read-only compatibility validator for version 2.1 certificates (n <= 64).
 * A class H contributes the cosets U_H / <x,1+x>. Only divisors of the core
 * polynomial are visited: no bitstrings, chains, cosets, or field tables are
 * enumerated. See REFERENCE.md#partition-proof for the partition and graph-shape proofs.
 */
final class LegacyCensus21 {
    final int n, q, dimension;
    final long polynomial;
    final long[] irreducibleFactors;
    final List<Stratum> strata;
    final List<Graph> graphs;
    final long actualChains;
    final BigInteger totalStrings, totalLoops, totalFactors;

    static final class Stratum {
        final long annihilator, states, linkOrder, cycle, actualChains, loops, factors;
        final int period;
        final int[] exponents;
        final String signature;
        final BigInteger strings;

        Stratum(long annihilator, int[] exponents, long states, int period,
                long linkOrder, long cycle, long actualChains, String signature,
                BigInteger strings, long loops, long factors) {
            this.annihilator = annihilator;
            this.exponents = exponents.clone();
            this.states = states;
            this.period = period;
            this.linkOrder = linkOrder;
            this.cycle = cycle;
            this.actualChains = actualChains;
            this.signature = signature;
            this.strings = strings;
            this.loops = loops;
            this.factors = factors;
        }
        String name() { return "G" + cycle + "-" + signature; }
    }

    static final class Graph {
        final String name, signature;
        final long cycle, loops;
        long actualChains;
        BigInteger totalStrings = BigInteger.ZERO;
        BigInteger totalLoops = BigInteger.ZERO;
        BigInteger totalFactors = BigInteger.ZERO;
        Graph(Stratum s) {
            name = s.name(); signature = s.signature; cycle = s.cycle; loops = s.loops;
        }
        void add(Stratum s) {
            if (cycle != s.cycle || loops != s.loops || !signature.equals(s.signature))
                throw new IllegalStateException("Inconsistent graph shape " + name);
            actualChains = Math.addExact(actualChains, s.actualChains);
            BigInteger count = BigInteger.valueOf(s.actualChains);
            totalStrings = totalStrings.add(s.strings.multiply(count));
            totalLoops = totalLoops.add(BigInteger.valueOf(s.loops).multiply(count));
            totalFactors = totalFactors.add(BigInteger.valueOf(s.factors).multiply(count));
        }
    }

    private record Work(long h, int[] exponents, long phi, long bound) { }
    private record OrderKey(long value, long modulus, long bound) { }
    private final Map<OrderKey, Long> orders = new ConcurrentHashMap<>();

    LegacyCensus21(int n) { this(n, Math.min(32, Runtime.getRuntime().availableProcessors()), null); }

    LegacyCensus21(int n, int workers, BiConsumer<Long, Long> progress) {
        if (n < 1 || n > 64) throw new IllegalArgumentException("n must be in 1..64");
        if (workers < 1 || workers > 256)
            throw new IllegalArgumentException("workers must be in 1..256");
        this.n = n;
        q = Integer.lowestOneBit(n);
        dimension = n - q;
        long p = 0;
        for (int i = 0; i < n; i += q) p |= 1L << i;
        polynomial = p;
        int odd = n / q;
        long squareFree = -1L >>> (64 - odd);
        irreducibleFactors = squareFree == 1 ? new long[0] : GF2.factor(squareFree);
        long product = 1, coreProduct = 1;
        for (long f : irreducibleFactors) {
            verifyIrreducible(f);
            product = GF2.multiply(product, f);
            for (int i = 0; i < q; i++) coreProduct = GF2.multiply(coreProduct, f);
        }
        if (product != squareFree || coreProduct != polynomial)
            throw new IllegalStateException("Polynomial factorization failed verification");
        int classCount = 1;
        for (int i = 0; i < irreducibleFactors.length; i++)
            classCount = Math.multiplyExact(classCount, q + 1);
        List<Work> work = new ArrayList<>(classCount);
        enumerate(0, new int[irreducibleFactors.length], 1, 1, q, work);
        if (work.size() != classCount)
            throw new IllegalStateException("Incomplete factor-exponent grid");
        Stratum[] measured = measureAll(work, workers, progress);
        // Work was generated in exponent-lexicographic order. Worker completion
        // order never affects certificates or aggregation.
        strata = List.copyOf(Arrays.asList(measured));
        Map<String, Graph> shapes = new HashMap<>();
        long count = 0;
        BigInteger words = BigInteger.ZERO, necklaces = BigInteger.ZERO;
        BigInteger primitive = BigInteger.ZERO, core = BigInteger.ZERO;
        for (Stratum s : strata) {
            count = Math.addExact(count, s.actualChains);
            core = core.add(BigInteger.valueOf(s.states));
            BigInteger copies = BigInteger.valueOf(s.actualChains);
            words = words.add(s.strings.multiply(copies));
            necklaces = necklaces.add(BigInteger.valueOf(s.loops).multiply(copies));
            primitive = primitive.add(BigInteger.valueOf(s.factors).multiply(copies));
            shapes.computeIfAbsent(s.name(), ignored -> new Graph(s)).add(s);
        }
        if (!core.equals(BigInteger.ONE.shiftLeft(dimension)) || !words.equals(BigInteger.ONE.shiftLeft(n)))
            throw new IllegalStateException("Annihilator census does not cover the power set");
        if (!necklaces.equals(necklaceCount(n)) || !primitive.equals(primitiveCount(n)))
            throw new IllegalStateException("Independent rotation-count verification failed");
        actualChains = count;
        List<Graph> sorted = new ArrayList<>(shapes.values());
        sorted.sort(Comparator.comparingLong((Graph g) -> g.cycle).thenComparing(g -> g.signature));
        graphs = List.copyOf(sorted);
        totalStrings = words; totalLoops = necklaces; totalFactors = primitive;
    }

    private void enumerate(int position, int[] exponents, long h, long phi,
                           long orderBound, List<Work> out) {
        if (position == irreducibleFactors.length) {
            out.add(new Work(h, exponents.clone(), phi, orderBound));
            return;
        }
        long f = irreducibleFactors[position];
        int degree = GF2.degree(f);
        long fieldOrder = (1L << degree) - 1;
        long nextH = h, nextPhi = phi;
        for (int e = 0; e <= q; e++) {
            exponents[position] = e;
            enumerate(position + 1, exponents, nextH, nextPhi,
                    e == 0 ? orderBound : lcm(orderBound, fieldOrder), out);
            if (e < q) {
                nextH = GF2.multiply(nextH, f);
                nextPhi = Math.multiplyExact(nextPhi, e == 0 ? fieldOrder : 1L << degree);
            }
        }
    }

    private Stratum[] measureAll(List<Work> work, int requestedWorkers,
                                 BiConsumer<Long, Long> progress) {
        int workerCount = Math.min(requestedWorkers, work.size());
        Stratum[] result = new Stratum[work.size()];
        AtomicInteger next = new AtomicInteger();
        AtomicLong done = new AtomicLong();
        Runnable worker = () -> {
            int i;
            while (!Thread.currentThread().isInterrupted() && (i = next.getAndIncrement()) < work.size()) {
                Work w = work.get(i);
                result[i] = measure(w.h, w.exponents, w.phi, w.bound);
                long completed = done.incrementAndGet();
                if (progress != null) progress.accept(completed, (long)work.size());
            }
        };
        if (workerCount == 1) { worker.run(); return result; }
        ExecutorService pool = Executors.newFixedThreadPool(workerCount);
        List<Future<?>> futures = new ArrayList<>(workerCount);
        try {
            for (int i = 0; i < workerCount; i++) futures.add(pool.submit(worker));
            for (Future<?> f : futures) f.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("LegacyCensus21 interrupted", e);
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            if (cause instanceof RuntimeException r) throw r;
            if (cause instanceof Error error) throw error;
            throw new IllegalStateException("LegacyCensus21 worker failed", cause);
        } finally {
            pool.shutdownNow();
        }
        return result;
    }

    private long order(long value, long modulus, long bound) {
        return orders.computeIfAbsent(new OrderKey(value, modulus, bound),
                key -> multiplicativeOrder(key.value, key.modulus, key.bound));
    }

    private Stratum measure(long h, int[] exponents, long phi, long bound) {
        int period = 1;
        long linkOrder = 1, intersection = 1, cycle = 1;
        if (h != 1) {
            period = Math.toIntExact(order(2, h, n));
            linkOrder = order(3, h, bound);
            // The cyclic subgroup intersection has order dividing d <= n.
            // Testing its possible order requires at most n operator residues,
            // never one item per bitstring or chain.
            long common = gcd(period, linkOrder);
            for (long k = common; k >= 1; k--) {
                if (common % k != 0) continue;
                long candidate = GF2.powMod(3, linkOrder / k, h);
                long rotation = 1;
                boolean found = false;
                for (int i = 0; i < period; i++) {
                    if (rotation == candidate) { found = true; break; }
                    rotation = GF2.multiplyMod(rotation, 2, h);
                }
                if (found) { intersection = k; break; }
            }
            cycle = linkOrder / intersection;
        }
        long orbit = Math.multiplyExact(period, cycle);
        if (phi % orbit != 0) throw new IllegalStateException("Nonintegral annihilator component count");
        long count = phi / orbit;
        int rotationTwoPart = Integer.lowestOneBit(period);
        StringBuilder sig = new StringBuilder(q + 1).append('2');
        for (int j = 1; j < q; j++)
            sig.append((j & (j - 1)) == 0 && j >= rotationTwoPart ? '1' : '2');
        sig.append('0');
        BigInteger orbitSize = BigInteger.valueOf(orbit);
        BigInteger loops = BigInteger.ZERO, factors = BigInteger.ZERO;
        for (int e = 1; e <= q; e *= 2) {
            BigInteger kernel = BigInteger.ONE.shiftLeft(e);
            if (e > 1) kernel = kernel.subtract(BigInteger.ONE.shiftLeft(e / 2));
            long liftedPeriod = lcm(period, e);
            BigInteger[] qr = orbitSize.multiply(kernel).divideAndRemainder(BigInteger.valueOf(liftedPeriod));
            if (qr[1].signum() != 0) throw new IllegalStateException("Nonintegral lifted necklace count");
            loops = loops.add(qr[0]);
            if (liftedPeriod == n) factors = factors.add(qr[0]);
        }
        // Independently count the vertices at each depth of the nilpotent
        // quotient tree and verify every branching symbol in the signature.
        BigInteger tree = BigInteger.ONE, previousLevel = BigInteger.ONE;
        int previousRho = 1;
        for (int j = 1; j <= q; j++) {
            int rho = 1;
            while (Math.multiplyExact(rotationTwoPart, rho) < j) rho *= 2;
            BigInteger[] qr = BigInteger.ONE.shiftLeft(j - 1).divideAndRemainder(BigInteger.valueOf(rho));
            if (qr[1].signum() != 0) throw new IllegalStateException("Nonintegral tree level");
            BigInteger level = qr[0];
            if (j > 1) {
                int branch = 2 * previousRho / rho;
                if (sig.charAt(j - 1) - '0' != branch
                        || !previousLevel.multiply(BigInteger.valueOf(branch)).equals(level))
                    throw new IllegalStateException("Tree signature verification failed");
            }
            tree = tree.add(level);
            previousLevel = level;
            previousRho = rho;
        }
        if (!tree.multiply(BigInteger.valueOf(cycle)).equals(loops))
            throw new IllegalStateException("Tree and rotation bitloop counts differ");
        return new Stratum(h, exponents, phi, period, linkOrder, cycle, count,
                sig.toString(), orbitSize.shiftLeft(q), loops.longValueExact(), factors.longValueExact());
    }

    /** Burnside's rotation formula, independent of the annihilator census. */
    static BigInteger necklaceCount(int n) {
        BigInteger sum = BigInteger.ZERO;
        for (int d = 1; d <= n; d++) if (n % d == 0)
            sum = sum.add(BigInteger.ONE.shiftLeft(n / d).multiply(BigInteger.valueOf(totient(d))));
        return divideInteger(sum, n);
    }

    /** Mobius inversion for rotation classes having exactly period n. */
    static BigInteger primitiveCount(int n) {
        BigInteger sum = BigInteger.ZERO;
        for (int d = 1; d <= n; d++) if (n % d == 0)
            sum = sum.add(BigInteger.ONE.shiftLeft(n / d).multiply(BigInteger.valueOf(mobius(d))));
        return divideInteger(sum, n);
    }

    private static BigInteger divideInteger(BigInteger sum, int n) {
        BigInteger[] qr = sum.divideAndRemainder(BigInteger.valueOf(n));
        if (qr[1].signum() != 0) throw new IllegalStateException("Nonintegral independent rotation count");
        return qr[0];
    }
    private static int totient(int n) {
        int result = n, rest = n;
        for (int p = 2; p <= rest / p; p++) if (rest % p == 0) {
            result -= result / p;
            do { rest /= p; } while (rest % p == 0);
        }
        if (rest > 1) result -= result / rest;
        return result;
    }
    private static int mobius(int n) {
        int result = 1, rest = n;
        for (int p = 2; p <= rest / p; p++) if (rest % p == 0) {
            rest /= p;
            if (rest % p == 0) return 0;
            result = -result;
        }
        if (rest > 1) result = -result;
        return result;
    }

    static long multiplicativeOrder(long value, long modulus, long bound) {
        if (modulus == 1) return 1;
        value = GF2.remainder(value, modulus);
        if (bound < 1 || GF2.powMod(value, bound, modulus) != 1)
            throw new IllegalArgumentException("Invalid multiplicative-order bound");
        long order = bound;
        for (long prime : primeFactors(bound))
            while (order % prime == 0 && GF2.powMod(value, order / prime, modulus) == 1)
                order /= prime;
        return order;
    }

    private static void verifyIrreducible(long f) {
        int degree = GF2.degree(f);
        long x = GF2.remainder(2, f), v = x;
        for (int j = 0; j < degree; j++) v = GF2.multiplyMod(v, v, f);
        if (v != x) throw new IllegalStateException("Nonirreducible factor");
        for (long prime : primeFactors(degree)) {
            v = x;
            for (int j = 0; j < degree / prime; j++) v = GF2.multiplyMod(v, v, f);
            if (GF2.gcd(f, v ^ x) != 1) throw new IllegalStateException("Nonirreducible factor");
        }
    }

    static long gcd(long a, long b) {
        while (b != 0) { long r = a % b; a = b; b = r; }
        return a;
    }
    static long lcm(long a, long b) { return Math.multiplyExact(a / gcd(a, b), b); }

    private static final Map<Long, long[]> PRIME_CACHE = new ConcurrentHashMap<>();
    /** Distinct ascending prime factors, exact for every positive signed long. */
    static long[] primeFactors(long n) {
        if (n < 1) throw new IllegalArgumentException("Positive factorization input required");
        return PRIME_CACHE.computeIfAbsent(n, value -> {
            TreeSet<Long> factors = new TreeSet<>();
            long remainder = value;
            for (long p = 2; p <= 1000 && p <= remainder / p; p += p == 2 ? 1 : 2) {
                if (remainder % p != 0) continue;
                factors.add(p);
                while (remainder % p == 0) remainder /= p;
            }
            splitInteger(remainder, factors);
            long[] out = new long[factors.size()];
            int i = 0;
            for (long p : factors) out[i++] = p;
            return out;
        }).clone();
    }

    // These Miller-Rabin bases are deterministic on unsigned 64-bit integers.
    private static boolean prime(long n) {
        if (n < 2) return false;
        if ((n & 1) == 0) return n == 2;
        long d = n - 1;
        int s = Long.numberOfTrailingZeros(d);
        d >>>= s;
        BigInteger modulus = BigInteger.valueOf(n), minusOne = modulus.subtract(BigInteger.ONE);
        for (long base : new long[]{2, 325, 9375, 28178, 450775, 9780504, 1795265022}) {
            long a = base % n;
            if (a == 0) continue;
            BigInteger x = BigInteger.valueOf(a).modPow(BigInteger.valueOf(d), modulus);
            if (x.equals(BigInteger.ONE) || x.equals(minusOne)) continue;
            boolean passed = false;
            for (int r = 1; r < s; r++) {
                x = x.multiply(x).mod(modulus);
                if (x.equals(minusOne)) { passed = true; break; }
            }
            if (!passed) return false;
        }
        return true;
    }

    private static void splitInteger(long n, Set<Long> out) {
        if (n == 1) return;
        if (prime(n)) { out.add(n); return; }
        BigInteger modulus = BigInteger.valueOf(n);
        // Bounded deterministic Pollard rho. Failure is explicit, never a guessed factor.
        for (int attempt = 1; attempt <= 32; attempt++) {
            BigInteger c = BigInteger.valueOf(attempt), x = BigInteger.valueOf(2 + attempt), y = x;
            BigInteger divisor = BigInteger.ONE;
            for (int step = 0; step < 262144 && divisor.equals(BigInteger.ONE); step++) {
                x = x.multiply(x).add(c).mod(modulus);
                y = y.multiply(y).add(c).mod(modulus);
                y = y.multiply(y).add(c).mod(modulus);
                divisor = x.subtract(y).abs().gcd(modulus);
            }
            if (!divisor.equals(BigInteger.ONE) && !divisor.equals(modulus)) {
                long d = divisor.longValueExact();
                splitInteger(d, out); splitInteger(n / d, out);
                return;
            }
        }
        throw new IllegalArgumentException("Exact integer factorization exceeded its bounded work limit for " + n);
    }
}
