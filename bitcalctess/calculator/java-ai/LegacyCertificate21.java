import java.util.*;

/** Exact descriptors for a disjoint algebraic partition; contains no representative words. */
final class LegacyCertificate21 {
    static Map<String,Object> describe(LegacyCensus21 c) {
        List<Object> irreducibles = new ArrayList<>(), strata = new ArrayList<>();
        for (long f : c.irreducibleFactors) irreducibles.add(Json.object(
                "polynomial", hex(f), "degree", GF2.degree(f), "multiplicity", c.q));
        for (LegacyCensus21.Stratum s : c.strata) {
            List<Integer> exponents = Arrays.stream(s.exponents).boxed().toList();
            strata.add(Json.object("annihilator", hex(s.annihilator), "factor_exponents", exponents,
                    "units", s.states, "rotation_order", s.period, "link_order", s.linkOrder,
                    "cycle_order", s.cycle, "chains", s.actualChains, "bitstrings", s.strings,
                    "bitloops", s.loops, "factors", s.factors, "name", s.name(), "signature", s.signature));
        }
        return Json.object("schema_version", "2.1", "n", c.n, "q", c.q,
                "core_polynomial", hex(c.polynomial), "irreducible_factors", irreducibles,
                "strata", strata, "totals", Json.object("bitstrings", c.totalStrings,
                        "bitloops", c.totalLoops, "factors", c.totalFactors, "chains", c.actualChains,
                        "graphs", c.graphs.size()));
    }
    private static String hex(long value) { return "0x" + Long.toUnsignedString(value, 16); }
}
