import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Observation-first exploration for Property 1.
 *
 * <p><b>Validates: Requirements 1.1, 1.2, 2.1, 2.2, 3.5</b>
 *
 * <p>This test intentionally fails on the unfixed implementation. The assertion describes
 * required whole-run behavior, while the child executes the unchanged orchestration order.
 */
public final class PrematureProgressExplorationTest {
    private static final int N = 4;
    private static final long CONTROLLED_PAUSE_MILLIS = 1_500L;
    private static final Duration CHILD_TIMEOUT = Duration.ofSeconds(15);
    private static final Pattern PROGRESS = Pattern.compile(
            "^n=(\\d+) progress=\\s*([0-9]+(?:\\.[0-9]+)?)% elapsed=([0-9:]+) ETA=(.*?) \\[(.*)]$");

    private PrematureProgressExplorationTest() {
    }

    public static void main(String[] args) throws Exception {
        Path build = Path.of(".test-build").toAbsolutePath().normalize();
        if (!Files.isDirectory(build)) {
            throw new AssertionError("missing compiled test directory: " + build);
        }

        Observation observation = observePauseBeforePrint(build);
        IOExceptionCharacterization io = characterizeSwallowedIOException(build);

        if (!observation.bugCondition) {
            throw new AssertionError("exploration did not reproduce the documented bug condition");
        }
        if (!io.printReturned || io.exitCode != 0 || !io.stackTracePrinted) {
            throw new AssertionError("protected print() did not exhibit the expected swallowed-IOException behavior: " + io);
        }

        System.err.println("PROPERTY_SEED=6168471");
        System.err.println("COUNTEREXAMPLE n=" + N);
        System.err.println("premature_terminal=" + observation.prematureTerminal.line);
        System.err.println("owner_alive_during_pause=" + observation.ownerAliveDuringPause);
        System.err.println("observable_success=" + observation.observableSuccess);
        System.err.println("progress_records_before_pause=" + observation.recordsBeforePause);
        System.err.println("progress_records_after_pause=" + observation.recordsAfterPause);
        System.err.println("downstream_heartbeat_emitted=" + observation.downstreamHeartbeatEmitted);
        System.err.println("frozen_elapsed=" + observation.prematureTerminal.elapsed);
        System.err.println("invalid_output_print_returned=" + io.printReturned);
        System.err.println("invalid_output_exit_code=" + io.exitCode);
        System.err.println("invalid_output_stack_trace=" + io.stackTracePrinted);
        System.err.println("AMBIGUITY: Powerset.print() swallows IOException; when all bytes are visible, a close error can be observationally indistinguishable from successful output.");

        if (!expectedBehavior(observation)) {
            throw new AssertionError("Expected behavior violated: incomplete Main-path work reported terminal progress; "
                    + observation.prematureTerminal.line + "; no downstream heartbeat advanced elapsed during the controlled pause");
        }
    }

    private static Observation observePauseBeforePrint(Path build) throws Exception {
        Path run = Files.createTempDirectory("premature-progress-pause-");
        Files.createDirectory(run.resolve("output"));
        Path stdout = run.resolve("stdout.txt");
        Path stderr = run.resolve("stderr.txt");
        Process child = startChild(build, run, stdout, stderr, "pause-before-print");
        try (BufferedWriter commands = new BufferedWriter(
                new OutputStreamWriter(child.getOutputStream(), StandardCharsets.UTF_8))) {
            awaitFileContains(stdout, "CONSTRUCTED", child, CHILD_TIMEOUT);
            List<ProgressRecord> before = parseProgress(Files.readString(stderr, StandardCharsets.UTF_8));
            if (before.isEmpty()) {
                throw new AssertionError("child emitted no progress records");
            }
            ProgressRecord terminal = before.get(before.size() - 1);
            boolean ownerAlive = child.isAlive();
            boolean observableSuccess = false;
            boolean bugCondition = isBugCondition(true, ownerAlive, observableSuccess, terminal);

            commands.write("WAIT " + CONTROLLED_PAUSE_MILLIS);
            commands.newLine();
            commands.flush();
            awaitFileContains(stdout, "PAUSE_COMPLETE", child, CHILD_TIMEOUT);

            List<ProgressRecord> after = parseProgress(Files.readString(stderr, StandardCharsets.UTF_8));
            boolean heartbeat = after.size() > before.size()
                    && elapsedSeconds(after.get(after.size() - 1).elapsed) > elapsedSeconds(terminal.elapsed);

            commands.write("PRINT");
            commands.newLine();
            commands.flush();
            int exit = waitFor(child, CHILD_TIMEOUT);
            if (exit != 0) {
                throw new AssertionError("pause child exited " + exit + ": "
                        + Files.readString(stderr, StandardCharsets.UTF_8));
            }
            awaitFileContains(stdout, "PRINT_RETURNED", child, CHILD_TIMEOUT);
            return new Observation(terminal, ownerAlive, observableSuccess, bugCondition,
                    before.size(), after.size(), heartbeat);
        } finally {
            if (child.isAlive()) {
                child.destroyForcibly();
                child.waitFor();
            }
            deleteRecursively(run);
        }
    }

    private static IOExceptionCharacterization characterizeSwallowedIOException(Path build) throws Exception {
        Path run = Files.createTempDirectory("premature-progress-invalid-output-");
        Path stdout = run.resolve("stdout.txt");
        Path stderr = run.resolve("stderr.txt");
        Process child = startChild(build, run, stdout, stderr, "invalid-output");
        try {
            int exit = waitFor(child, CHILD_TIMEOUT);
            String out = Files.readString(stdout, StandardCharsets.UTF_8);
            String err = Files.readString(stderr, StandardCharsets.UTF_8);
            return new IOExceptionCharacterization(exit, out.contains("PRINT_RETURNED"),
                    err.contains("java.io.FileNotFoundException") || err.contains("java.nio.file.NoSuchFileException"));
        } finally {
            if (child.isAlive()) {
                child.destroyForcibly();
                child.waitFor();
            }
            deleteRecursively(run);
        }
    }

    private static Process startChild(Path build, Path run, Path stdout, Path stderr, String mode)
            throws IOException {
        Path java = Path.of(System.getProperty("java.home"), "bin", "java");
        ProcessBuilder builder = new ProcessBuilder(java.toString(), "-ea", "-cp", build.toString(),
                "PrematureProgressChild", mode, Integer.toString(N));
        builder.directory(run.toFile());
        builder.redirectOutput(stdout.toFile());
        builder.redirectError(stderr.toFile());
        return builder.start();
    }

    private static boolean isBugCondition(boolean mainPath, boolean ownerAlive,
            boolean observableSuccess, ProgressRecord record) {
        boolean observableWorkRemains = ownerAlive || !observableSuccess;
        boolean terminalDisplay = record.percent == 100.0
                || "00:00:00".equals(record.eta)
                || "complete".equals(record.state);
        return mainPath && observableWorkRemains && terminalDisplay;
    }

    private static boolean expectedBehavior(Observation observation) {
        ProgressRecord record = observation.prematureTerminal;
        return record.percent < 100.0
                && !"complete".equals(record.state)
                && !"00:00:00".equals(record.eta)
                && ("calculating".equals(record.eta) || "unavailable".equals(record.eta))
                && observation.downstreamHeartbeatEmitted;
    }

    private static List<ProgressRecord> parseProgress(String stderr) {
        List<ProgressRecord> records = new ArrayList<>();
        for (String line : stderr.split("\\R")) {
            Matcher matcher = PROGRESS.matcher(line);
            if (matcher.matches()) {
                records.add(new ProgressRecord(line, Integer.parseInt(matcher.group(1)),
                        Double.parseDouble(matcher.group(2)), matcher.group(3), matcher.group(4), matcher.group(5)));
            }
        }
        return records;
    }

    private static long elapsedSeconds(String duration) {
        String[] fields = duration.split(":");
        return Long.parseLong(fields[0]) * 3_600L + Long.parseLong(fields[1]) * 60L
                + Long.parseLong(fields[2]);
    }

    private static void awaitFileContains(Path file, String marker, Process child, Duration timeout)
            throws Exception {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            if (Files.exists(file) && Files.readString(file, StandardCharsets.UTF_8).contains(marker)) {
                return;
            }
            if (!child.isAlive()) {
                String content = Files.exists(file) ? Files.readString(file, StandardCharsets.UTF_8) : "";
                throw new AssertionError("child exited before marker " + marker + "; stdout=" + content);
            }
            Thread.sleep(10L);
        }
        throw new AssertionError("timed out waiting for child marker " + marker);
    }

    private static int waitFor(Process child, Duration timeout) throws Exception {
        if (!child.waitFor(timeout.toMillis(), java.util.concurrent.TimeUnit.MILLISECONDS)) {
            throw new AssertionError("child did not terminate within " + timeout);
        }
        return child.exitValue();
    }

    private static void deleteRecursively(Path root) throws IOException {
        if (!Files.exists(root)) {
            return;
        }
        try (java.util.stream.Stream<Path> paths = Files.walk(root)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) {
                Files.deleteIfExists(path);
            }
        }
    }

    private static final class ProgressRecord {
        final String line;
        final int n;
        final double percent;
        final String elapsed;
        final String eta;
        final String state;

        ProgressRecord(String line, int n, double percent, String elapsed, String eta, String state) {
            this.line = line;
            this.n = n;
            this.percent = percent;
            this.elapsed = elapsed;
            this.eta = eta;
            this.state = state;
        }
    }

    private static final class Observation {
        final ProgressRecord prematureTerminal;
        final boolean ownerAliveDuringPause;
        final boolean observableSuccess;
        final boolean bugCondition;
        final int recordsBeforePause;
        final int recordsAfterPause;
        final boolean downstreamHeartbeatEmitted;

        Observation(ProgressRecord prematureTerminal, boolean ownerAliveDuringPause,
                boolean observableSuccess, boolean bugCondition, int recordsBeforePause,
                int recordsAfterPause, boolean downstreamHeartbeatEmitted) {
            this.prematureTerminal = prematureTerminal;
            this.ownerAliveDuringPause = ownerAliveDuringPause;
            this.observableSuccess = observableSuccess;
            this.bugCondition = bugCondition;
            this.recordsBeforePause = recordsBeforePause;
            this.recordsAfterPause = recordsAfterPause;
            this.downstreamHeartbeatEmitted = downstreamHeartbeatEmitted;
        }
    }

    private static final class IOExceptionCharacterization {
        final int exitCode;
        final boolean printReturned;
        final boolean stackTracePrinted;

        IOExceptionCharacterization(int exitCode, boolean printReturned, boolean stackTracePrinted) {
            this.exitCode = exitCode;
            this.printReturned = printReturned;
            this.stackTracePrinted = stackTracePrinted;
        }

        @Override
        public String toString() {
            return String.format(Locale.ROOT, "exit=%d printReturned=%s stackTracePrinted=%s",
                    exitCode, printReturned, stackTracePrinted);
        }
    }
}
