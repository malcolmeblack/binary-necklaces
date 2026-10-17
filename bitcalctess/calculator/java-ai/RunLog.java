import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Append-only JSON Lines, separate UUID per execution. */
final class RunLog implements AutoCloseable {
    private final BufferedWriter out;
    private final String runId = UUID.randomUUID().toString();
    private final int n;
    private final long start = System.nanoTime(), interval;
    private long lastPrint = start;
    private long completed;
    private boolean terminal;
    RunLog(int n, int workers, Path dir, double seconds) throws IOException {
        this.n = n; interval = (long)(seconds * 1_000_000_000L); Files.createDirectories(dir);
        out = Files.newBufferedWriter(dir.resolve(n + ".log"), StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        event("run_start", "version", Main.VERSION, "engine", "relation-lattice-census", "workers", workers,
                "max_heap_bytes", Runtime.getRuntime().maxMemory(), "representatives", false);
    }
    synchronized void progress(Long done, Long total) {
        if (done <= completed) return;
        completed = done;
        if (System.nanoTime() - lastPrint < interval && !done.equals(total)) return;
        lastPrint = System.nanoTime();
        event("progress", "phase", "local-factor-powers", "done", done, "total", total);
        System.err.printf(Locale.ROOT, "n=%d | factor powers %d/%d | elapsed %.3f s%n", n, done, total, elapsed());
    }
    synchronized void event(String kind, Object... fields) {
        Map<String,Object> row = Json.object("time", Instant.now().toString(), "version", Main.VERSION, "run_id", runId,
                "n", n, "event", kind, "elapsed_ns", System.nanoTime() - start);
        for (int i = 0; i < fields.length; i += 2) row.put((String)fields[i], fields[i+1]);
        try {
            // Json's formatting has record newlines; flatten whitespace outside strings for JSONL.
            out.write(Json.write(row).replace("\n", "").replace("\r", "")); out.newLine(); out.flush();
        } catch (IOException failure) { throw new UncheckedIOException(failure); }
    }
    synchronized void finish(boolean success, Object... fields) {
        if (terminal) return;
        Object[] all = new Object[fields.length + 2]; all[0] = "status"; all[1] = success ? "SUCCESS" : "FAILED";
        System.arraycopy(fields, 0, all, 2, fields.length); event("run_end", all); terminal = true;
    }
    double elapsed() { return (System.nanoTime() - start) / 1_000_000_000.0; }
    @Override public synchronized void close() throws IOException { out.close(); }
}
