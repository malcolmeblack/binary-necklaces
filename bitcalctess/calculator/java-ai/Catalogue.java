import java.io.*;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Certificates are authoritative; CSV aggregates are reproducible projections. */
final class Catalogue {
    static final String POWERSETS = "n,bitstrings,bitloops,factors,chains,graphs";
    static final String GRAPHS = "n,name,chains,bitloops-per-chain,bitstrings,bitloops,factors,cycle-order,tree-depth,signature";
    private final Path directory;
    private final Map<Integer,Cached> cache = new HashMap<>();
    private record Cached(String digest, Census census) { }
    Catalogue(Path directory) { this.directory = directory; }

    Map<String,String> publish(Census current) throws Exception { return update(current, false); }
    Map<String,String> rebuild() throws Exception { return update(null, true); }

    private Map<String,String> update(Census current, boolean rebuilding) throws Exception {
        Files.createDirectories(directory);
        // A stable lock file must never be unlinked while another process can use it.
        try (FileChannel lockChannel = FileChannel.open(directory.resolve(".bitloops-output.lock"),
                StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock lock = lockChannel.lock()) {
            if (!lock.isValid()) throw new IOException("Could not acquire output lock");
            checkHeader(directory.resolve("powersets.csv"), POWERSETS, rebuilding);
            checkHeader(directory.resolve("graphs.csv"), GRAPHS, rebuilding);
            TreeMap<Integer,Census> all = readCertificates(current == null ? -1 : current.n);
            if (current != null) all.put(current.n, current);
            if (all.isEmpty()) throw new IllegalArgumentException("No certificates to rebuild in " + directory);
            if (!rebuilding) {
                checkCoveredWidths(directory.resolve("powersets.csv"), all.keySet());
                checkCoveredWidths(directory.resolve("graphs.csv"), all.keySet());
            }

            StringBuilder powers = new StringBuilder(POWERSETS).append("\r\n");
            StringBuilder graphs = new StringBuilder(GRAPHS).append("\r\n");
            for (Census c : all.values()) {
                row(powers, c.n, c.totalStrings, c.totalLoops, c.totalFactors, c.actualChains, c.graphs.size());
                for (Census.Graph g : c.graphs)
                    row(graphs, c.n, g.name, g.actualChains, g.loops, g.totalStrings, g.totalLoops,
                            g.totalFactors, g.cycle, g.signature.length() - 1, g.signature);
            }
            byte[] powersBytes = powers.toString().getBytes(StandardCharsets.UTF_8);
            byte[] graphBytes = graphs.toString().getBytes(StandardCharsets.UTF_8);
            byte[] certificate = current == null ? null : Json.write(Certificate.describe(current)).getBytes(StandardCharsets.UTF_8);
            Path staging = Files.createTempDirectory(directory, ".v2-staging-");
            try {
                stage(staging.resolve("powersets.csv"), powersBytes);
                stage(staging.resolve("graphs.csv"), graphBytes);
                if (current != null) stage(staging.resolve("certificate.json"), certificate);
                // Commit the source certificate first. A stopped multi-file publication is
                // repaired by --rebuild-aggregates; no incomplete JSON/CSV is published.
                if (current != null) {
                    Files.createDirectories(directory.resolve("certificates"));
                    move(staging.resolve("certificate.json"), directory.resolve("certificates/" + current.n + ".json"));
                }
                move(staging.resolve("graphs.csv"), directory.resolve("graphs.csv"));
                move(staging.resolve("powersets.csv"), directory.resolve("powersets.csv"));
                Map<String,String> hashes = new LinkedHashMap<>();
                if (current != null) {
                    String digest = sha256(certificate); cache.put(current.n, new Cached(digest, current));
                    hashes.put("certificates/" + current.n + ".json", digest);
                }
                hashes.put("graphs.csv", sha256(graphBytes)); hashes.put("powersets.csv", sha256(powersBytes));
                return hashes;
            } finally {
                try (var entries = Files.list(staging)) { for (Path p : entries.toList()) Files.deleteIfExists(p); }
                Files.deleteIfExists(staging);
            }
        }
    }

    private TreeMap<Integer,Census> readCertificates(int replacing) throws Exception {
        TreeMap<Integer,Census> all = new TreeMap<>(); Path certificates = directory.resolve("certificates");
        if (!Files.exists(certificates)) return all;
        try (var paths = Files.list(certificates)) {
            for (Path path : paths.sorted().toList()) {
                String filename = path.getFileName().toString();
                if (!filename.endsWith(".json")) continue;
                if (!filename.matches("[1-9][0-9]{0,3}\\.json"))
                    throw new IOException("Unexpected certificate filename: " + filename);
                int n = Integer.parseInt(filename.substring(0, filename.length() - 5));
                if (n > 1024) throw new IOException("Unsupported certificate width: " + filename);
                if (n == replacing) continue; // Explicit rerun may repair this one certificate.
                if (Files.size(path) > 16L * 1024 * 1024) throw new IOException("Certificate is too large: " + filename);
                byte[] bytes = Files.readAllBytes(path); String digest = sha256(bytes);
                Cached existing = cache.get(n); Census census;
                if (existing != null && existing.digest.equals(digest)) census = existing.census;
                else {
                    Object decoded = Json.parse(new String(bytes, StandardCharsets.UTF_8));
                    census = new Census(n, 1, null);
                    Object expected = Certificate.describe(census);
                    if (decoded instanceof Map<?,?> map && "2.1".equals(map.get("schema_version"))) {
                        if (n > 64) throw new IOException("Version 2.1 certificate exceeds its range: " + filename);
                        expected = LegacyCertificate21.describe(new LegacyCensus21(n, 1, null));
                    } else if (decoded instanceof Map<?,?> map && "2.2".equals(map.get("schema_version"))) {
                        if (n > 128) throw new IOException("Version 2.2 certificate exceeds its range: " + filename);
                        expected = Certificate.describe(census, "2.2");
                    } else if (decoded instanceof Map<?,?> map && "2.3".equals(map.get("schema_version"))) {
                        if (n > 256) throw new IOException("Version 2.3 certificate exceeds its range: " + filename);
                        expected = Certificate.describe(census, "2.3");
                    } else if (decoded instanceof Map<?,?> map && "2.4".equals(map.get("schema_version"))) {
                        if (n > 512) throw new IOException("Version 2.4 certificate exceeds its range: " + filename);
                        expected = Certificate.describe(census, "2.4");
                    }
                    if (!Json.equal(decoded, expected))
                        throw new IOException("Certificate failed exact arithmetic validation: " + filename);
                    cache.put(n, new Cached(digest, census));
                }
                all.put(n, census);
            }
        }
        return all;
    }
    private static void checkHeader(Path file, String expected, boolean rebuilding) throws IOException {
        if (!Files.exists(file)) return;
        if (!Files.isRegularFile(file)) throw new IOException("CSV target is not a regular file: " + file);
        try (BufferedReader in = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            String header = in.readLine();
            if (expected.equals(header)) return;
            // Rebuild can repair damaged v2 projections, but never overwrite recognizable v1 data.
            if (!rebuilding || (header != null && (header.contains("sym-chains") || header.contains("asym-chains"))))
                throw new IOException("Refusing legacy or incompatible CSV schema in " + file
                        + "; use a separate directory for version 2 output");
        }
    }
    private static void checkCoveredWidths(Path file, Set<Integer> available) throws IOException {
        if (!Files.exists(file)) return;
        try (BufferedReader in = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            in.readLine(); String line;
            while ((line = in.readLine()) != null) {
                if (line.isEmpty()) continue;
                int comma = line.indexOf(',');
                try {
                    int n = Integer.parseInt(comma < 0 ? line : line.substring(0, comma));
                    if (!available.contains(n)) throw new IOException("Missing source certificate for n=" + n
                            + "; restore it before updating aggregates, or explicitly use --rebuild-aggregates");
                } catch (NumberFormatException bad) { throw new IOException("Malformed aggregate; use --rebuild-aggregates: " + file, bad); }
            }
        }
    }
    private static void row(StringBuilder out, Object... fields) {
        for (int i = 0; i < fields.length; i++) {
            if (i != 0) out.append(','); String text = fields[i].toString();
            if (text.indexOf(',') >= 0 || text.indexOf('"') >= 0 || text.indexOf('\n') >= 0 || text.indexOf('\r') >= 0)
                out.append('"').append(text.replace("\"", "\"\"")).append('"');
            else out.append(text);
        }
        out.append("\r\n");
    }
    private static void stage(Path path, byte[] bytes) throws IOException {
        try (FileChannel out = FileChannel.open(path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            java.nio.ByteBuffer buffer = java.nio.ByteBuffer.wrap(bytes);
            while (buffer.hasRemaining()) out.write(buffer); out.force(true);
        }
    }
    private static void move(Path from, Path to) throws IOException {
        try { Files.move(from, to, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
        catch (AtomicMoveNotSupportedException noAtomic) { throw new IOException("Output filesystem must support atomic file replacement", noAtomic); }
    }
    static String sha256(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
