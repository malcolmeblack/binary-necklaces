import java.math.BigInteger;
import java.util.*;

/** Exact local relations and weighted lattice states; no representative lists. */
final class Certificate {
    static Map<String,Object> describe(Census c) { return describe(c, Main.VERSION); }
    static Map<String,Object> describe(Census c, String schemaVersion) {
        List<Object> irreducibles = new ArrayList<>(), states = new ArrayList<>();
        for (Census.Factor f : c.factors) {
            List<Object> powers = new ArrayList<>();
            for (Census.Local p : f.powers)
                powers.add(Json.object("exponent", p.exponent, "units", p.units,
                        "rotation_order", p.period, "link_order", p.linkOrder,
                        "cycle_order", p.cycle, "rotation_shift", p.shift));
            irreducibles.add(Json.object("polynomial", hex(f.polynomial), "degree", f.degree,
                    "multiplicity", c.q, "powers", powers));
        }
        for (Census.State s : c.states)
            states.add(Json.object("rotation_order", s.period, "cycle_order", s.cycle,
                    "rotation_shift", s.shift, "units", s.units, "chains", s.actualChains,
                    "bitstrings", s.strings, "bitloops", s.loops, "factors", s.factors,
                    "name", s.name(), "signature", s.signature));
        return Json.object("schema_version", schemaVersion, "n", c.n, "q", c.q,
                "core_polynomial", hex(c.polynomial), "annihilator_strata", c.stratumCount,
                "irreducible_factors", irreducibles, "states", states,
                "totals", Json.object("bitstrings", c.totalStrings, "bitloops", c.totalLoops,
                        "factors", c.totalFactors, "chains", c.actualChains, "graphs", c.graphs.size()));
    }
    private static String hex(BigInteger value) { return "0x" + value.toString(16); }
}
