import java.nio.file.*;
import java.util.*;

/** Representative-free graph catalogue and partition certificates for n=1..1024. */
public final class Main {
    static final String VERSION = "2";
    public static void main(String[] args) {
        try {
            Options options = Options.parse(args);
            if (options.help) { usage(); return; }
            Catalogue output = new Catalogue(options.output);
            if (options.rebuild) {
                Map<String,String> hashes = output.rebuild();
                System.out.println("Rebuilt graphs.csv and powersets.csv from validated certificates.");
                hashes.forEach((file, digest) -> System.out.println(file + " sha256=" + digest)); return;
            }
            for (int n = options.from; n <= options.to; n++) {
                if (options.plan) { printPlan(new Census(n, options.workers, null)); continue; }
                try (RunLog log = new RunLog(n, options.workers, options.logs, options.interval)) {
                    try {
                        Census census = new Census(n, options.workers, log::progress);
                        log.event("census_complete", "annihilator_strata", census.stratumCount, "states", census.states.size(), "chains", census.actualChains,
                                "graphs", census.graphs.size(), "bitstrings", census.totalStrings,
                                "bitloops", census.totalLoops, "factors", census.totalFactors);
                        Map<String,String> hashes = output.publish(census);
                        log.finish(true, "output_sha256", hashes);
                        System.err.printf(Locale.ROOT, "n=%d COMPLETE | %d graph types | %d actual chains | %.3f s%n",
                                n, census.graphs.size(), census.actualChains, log.elapsed());
                    } catch (Exception | Error failure) {
                        try { log.finish(false, "message", failure.toString()); }
                        catch (Exception loggingFailure) { failure.addSuppressed(loggingFailure); }
                        throw failure;
                    }
                }
            }
        } catch (Exception | OutOfMemoryError failure) {
            System.err.println("ERROR: " + failure.getMessage()); System.exit(1);
        }
    }
    private static void printPlan(Census c) {
        System.out.printf("n=%d%nengine=relation-lattice-census%nannihilator_strata=%s%nstates=%d%ngraphs=%d%nactual_chains=%d%nbitstrings=%s%nbitloops=%s%nfactors=%s%n",
                c.n, c.stratumCount, c.states.size(), c.graphs.size(), c.actualChains, c.totalStrings, c.totalLoops, c.totalFactors);
        System.out.println("representative_enumeration=false\noutput=not-written");
    }
    private static void usage() {
        System.out.println("""
                Bitloop Calculator 2 — exact graph catalogues without chain representatives
                java -jar java-ai.jar                 Calculate n=1..1024 (default)
                java -jar java-ai.jar 63              Calculate one n
                java -jar java-ai.jar --from 1 --to 20 Calculate an inclusive range
                java -jar java-ai.jar --plan          Arithmetic census only; no files written
                java -jar java-ai.jar --rebuild-aggregates
                Options: --threads 1..256 (default 32), --output DIR (default ./output)
                         --log DIR (default ./log), --progress-seconds 0.1..3600 (default 2)
                         --help
                Scope: n=1..1024. With no width or range, every supported n runs sequentially.
                Output: powersets.csv, graphs.csv, certificates/{n}.json. No chainrep files.
                Counts refer to actual chains, before reversal pairing. No representative symmetry flags.
                Logs append JSON Lines with version 2 and a UUID per run.
                No shell script, interactive prompt, large heap, swap, or GPU is required.
                """);
    }
    static final class Options {
        int from = -1, to = -1, workers = 32;
        double interval = 2;
        boolean help, plan, rebuild;
        Path output = Path.of("output"), logs = Path.of("log");
        static Options parse(String[] args) {
            Options o = new Options(); Integer single = null; boolean from = false, to = false;
            for (int i = 0; i < args.length; i++) {
                String key = args[i];
                if (key.equals("--help") || key.equals("-h")) { o.help = true; return o; }
                if (key.equals("--plan")) { o.plan = true; continue; }
                if (key.equals("--rebuild-aggregates")) { o.rebuild = true; continue; }
                if (!key.startsWith("--")) {
                    if (single != null) throw new IllegalArgumentException("Specify one n or a --from/--to range");
                    single = Integer.valueOf(key); continue;
                }
                if (++i == args.length) throw new IllegalArgumentException("Missing value for " + key);
                String value = args[i];
                switch (key) {
                    case "--from" -> { o.from = Integer.parseInt(value); from = true; }
                    case "--to" -> { o.to = Integer.parseInt(value); to = true; }
                    case "--threads" -> o.workers = Integer.parseInt(value);
                    case "--output" -> o.output = Path.of(value);
                    case "--log" -> o.logs = Path.of(value);
                    case "--progress-seconds" -> o.interval = Double.parseDouble(value);
                    default -> throw new IllegalArgumentException("Unknown option " + key + "; see --help for version 2 options");
                }
            }
            if (single != null) {
                if (from || to) throw new IllegalArgumentException("Do not combine n with --from/--to");
                o.from = single; o.to = single;
            } else if (!from && !to) { o.from = 1; o.to = 1024; }
            if (o.from < 1 || o.to > 1024 || o.to < o.from)
                throw new IllegalArgumentException("Specify n in 1..1024 or a complete ascending --from/--to range");
            if (o.rebuild && (o.plan || single != null || from || to))
                throw new IllegalArgumentException("--rebuild-aggregates cannot be combined with a width, range or --plan");
            if (o.workers < 1 || o.workers > 256) throw new IllegalArgumentException("--threads must be in 1..256");
            if (!Double.isFinite(o.interval) || o.interval < .1 || o.interval > 3600)
                throw new IllegalArgumentException("--progress-seconds must be in 0.1..3600");
            return o;
        }
    }
}
