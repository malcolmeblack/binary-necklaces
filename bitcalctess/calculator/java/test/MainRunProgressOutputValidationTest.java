import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Deterministic checks for task 3.4 observable-success output validation. */
public final class MainRunProgressOutputValidationTest {
    private static final Path VALID_FIXTURE = Path.of(
            "test", "fixtures", "premature-progress-completion-fix", "p3.csv");

    private MainRunProgressOutputValidationTest() {
    }

    public static void main(String[] args) throws Exception {
        byte[] valid = Files.readAllBytes(VALID_FIXTURE);
        validatesExactReviewedOutput(valid);
        rejectsMalformedAndIncompleteOutput(valid);
        requiresObservableFreshness(valid);
        completesOnlyForDeadOwnerWithFreshValidOutput(valid);
        rejectsStaleFailureAndLiveOwnerOutcomes(valid);
        System.out.println("MainRunProgressOutputValidationTest PASS");
    }

    private static void validatesExactReviewedOutput(byte[] valid) {
        MainRunProgress.OutputValidation result =
                MainRunProgress.validateOutputBytes(valid, 3, 2);
        assertTrue(result.valid, "reviewed fixture rejected: " + result.detail);
    }

    private static void rejectsMalformedAndIncompleteOutput(byte[] valid) {
        assertInvalid(copyWithoutLastByte(valid), 3, 2, "missing final newline");
        assertInvalid(replace(valid, "Graphs\n", "Graphz\n"), 3, 2,
                "reordered/missing section");
        assertInvalid(replace(valid, "8,4,2,2,0,1", "8,4,2,3,0,1"), 3, 2,
                "wrong representative count");
        assertInvalid(replace(valid, "G1-20,2,0,2,1,1,20", "G1-20,2,0,2,1,1"), 3, 2,
                "malformed graph row");
        assertInvalid(replace(valid, "001,6,2,2,1,1,20\n", ""), 3, 2,
                "truncated representative rows");
        assertInvalid(replace(valid, "Symmetric chains\n", "Asymmetric chains\n"), 3, 2,
                "reordered chain sections");
    }

    private static void requiresObservableFreshness(byte[] valid) {
        MainRunProgress.OutputSnapshot current = snapshot(valid.length, 20L, "current");
        MainRunProgress.OutputSnapshot failedBaseline = new MainRunProgress.OutputSnapshot(
                false, false, 0L, 0L, 0L, null, "baseline unavailable");
        assertTrue(!current.isFreshComparedTo(failedBaseline),
                "unobservable baseline must not establish freshness");
        MainRunProgress.OutputSnapshot stale = snapshot(valid.length, 20L, "current");
        assertTrue(!current.isFreshComparedTo(stale), "identical metadata must remain stale");
        assertTrue(current.isFreshComparedTo(MainRunProgress.OutputSnapshot.missing()),
                "new regular output should be fresh against an observed missing baseline");
    }

    private static void completesOnlyForDeadOwnerWithFreshValidOutput(byte[] valid) {
        Harness harness = Harness.deadOwner(MainRunProgress.OutputSnapshot.missing(),
                snapshot(valid.length, 20L, "fresh"), valid);
        harness.progress.start();
        harness.progress.transferToDownstream(80.0, "downstream work pending", 2);
        harness.progress.runShutdownObservation();
        harness.progress.runShutdownObservation();

        assertEquals(1, harness.sink.terminalLines.size(), "terminal emission count");
        String terminal = harness.sink.terminalLines.get(0);
        assertContains(terminal, "progress=100.00%", "observable success percent");
        assertContains(terminal, "ETA=00:00:00", "observable success ETA");
        assertContains(terminal, "[complete]", "observable success state");
        assertEquals(1, harness.probe.readCount, "bounded final artifact read count");
    }

    private static void rejectsStaleFailureAndLiveOwnerOutcomes(byte[] valid) throws Exception {
        MainRunProgress.OutputSnapshot existing = snapshot(valid.length, 20L, "same");
        Harness stale = Harness.deadOwner(existing, existing, valid);
        stale.progress.start();
        stale.progress.transferToDownstream(80.0, "downstream work pending", 2);
        stale.progress.runShutdownObservation();
        assertTerminalNonSuccess(stale, "unverified");
        assertEquals(0, stale.probe.readCount, "stale output read count");

        Harness failed = Harness.deadOwner(MainRunProgress.OutputSnapshot.missing(),
                snapshot(valid.length, 30L, "fresh"), valid);
        failed.progress.start();
        failed.progress.transferToDownstream(80.0, "downstream work pending", 2);
        failed.progress.recordFailure(new IllegalStateException("direct failure"));
        failed.progress.runShutdownObservation();
        assertTerminalNonSuccess(failed, "failed");
        assertEquals(0, failed.probe.readCount, "failed output read count");

        CountDownLatch ownerStarted = new CountDownLatch(1);
        CountDownLatch releaseOwner = new CountDownLatch(1);
        Thread liveOwner = new Thread(() -> {
            ownerStarted.countDown();
            try {
                releaseOwner.await();
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
            }
        }, "deterministic-live-owner");
        liveOwner.start();
        assertTrue(ownerStarted.await(5, TimeUnit.SECONDS), "owner did not start");
        try {
            Harness live = new Harness(liveOwner, MainRunProgress.OutputSnapshot.missing(),
                    snapshot(valid.length, 40L, "fresh"), valid);
            live.progress.start();
            live.progress.transferToDownstream(80.0, "downstream work pending", 2);
            live.progress.runShutdownObservation();
            assertTerminalNonSuccess(live, "cancelled");
            assertEquals(0, live.probe.readCount, "live-owner output read count");
        } finally {
            releaseOwner.countDown();
            liveOwner.join(5_000L);
            assertTrue(!liveOwner.isAlive(), "owner did not terminate");
        }
    }

    private static void assertTerminalNonSuccess(Harness harness, String state) {
        assertEquals(1, harness.sink.terminalLines.size(), "non-success terminal count");
        String terminal = harness.sink.terminalLines.get(0);
        assertTrue(!terminal.contains("progress=100.00%"), "non-success reached 100%: " + terminal);
        assertTrue(!terminal.contains("ETA=00:00:00"), "non-success used zero ETA: " + terminal);
        assertTrue(!terminal.contains("[complete]"), "non-success completed: " + terminal);
        assertContains(terminal, "[" + state + "]", "non-success state");
    }

    private static void assertInvalid(byte[] bytes, int n, int representatives, String context) {
        MainRunProgress.OutputValidation result =
                MainRunProgress.validateOutputBytes(bytes, n, representatives);
        assertTrue(!result.valid, context + " unexpectedly validated");
    }

    private static byte[] copyWithoutLastByte(byte[] source) {
        byte[] result = new byte[source.length - 1];
        System.arraycopy(source, 0, result, 0, result.length);
        return result;
    }

    private static byte[] replace(byte[] source, String target, String replacement) {
        String text = new String(source, java.nio.charset.StandardCharsets.UTF_8);
        if (!text.contains(target)) {
            throw new AssertionError("test mutation target not found: " + target);
        }
        return text.replace(target, replacement)
                .getBytes(java.nio.charset.StandardCharsets.UTF_8);
    }

    private static MainRunProgress.OutputSnapshot snapshot(long size, long modified, String key) {
        return new MainRunProgress.OutputSnapshot(
                true, true, size, modified, 10L, key, null);
    }

    private static void assertContains(String actual, String expected, String context) {
        assertTrue(actual.contains(expected), context + " missing " + expected + ": " + actual);
    }

    private static void assertEquals(int expected, int actual, String context) {
        if (expected != actual) {
            throw new AssertionError(context + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void assertTrue(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static final class Harness {
        final CapturingSink sink = new CapturingSink();
        final FakeProbe probe;
        final MainRunProgress progress;

        Harness(Thread owner, MainRunProgress.OutputSnapshot baseline,
                MainRunProgress.OutputSnapshot current, byte[] bytes) {
            probe = new FakeProbe(baseline, current, bytes);
            progress = new MainRunProgress(
                    3,
                    owner,
                    new IncrementingClock(),
                    sink,
                    ignored -> new StackTraceElement[0],
                    probe,
                    Path.of("output", "p3.csv"),
                    ignored -> () -> { },
                    new FakeScheduler(),
                    TimeUnit.SECONDS.toNanos(1));
        }

        static Harness deadOwner(MainRunProgress.OutputSnapshot baseline,
                MainRunProgress.OutputSnapshot current, byte[] bytes) {
            return new Harness(new Thread("never-started-owner"), baseline, current, bytes);
        }
    }

    private static final class IncrementingClock implements MainRunProgress.MonotonicClock {
        private long now;

        @Override
        public long nanoTime() {
            now += TimeUnit.SECONDS.toNanos(1);
            return now;
        }
    }

    private static final class CapturingSink implements MainRunProgress.LineSink {
        final List<String> terminalLines = new ArrayList<>();

        @Override
        public void write(String line, boolean terminal) {
            if (terminal) {
                terminalLines.add(line);
            }
        }
    }

    private static final class FakeProbe implements MainRunProgress.OutputProbe {
        private final MainRunProgress.OutputSnapshot baseline;
        private final MainRunProgress.OutputSnapshot current;
        private final byte[] bytes;
        private int snapshots;
        int readCount;

        FakeProbe(MainRunProgress.OutputSnapshot baseline,
                MainRunProgress.OutputSnapshot current, byte[] bytes) {
            this.baseline = baseline;
            this.current = current;
            this.bytes = bytes.clone();
        }

        @Override
        public MainRunProgress.OutputSnapshot snapshot(Path path) {
            return snapshots++ == 0 ? baseline : current;
        }

        @Override
        public byte[] readAllBytes(Path path) throws IOException {
            readCount++;
            return bytes.clone();
        }
    }

    private static final class FakeScheduler implements MainRunProgress.HeartbeatScheduler {
        @Override
        public MainRunProgress.HeartbeatTask scheduleAtFixedRate(
                Runnable action, long initialDelay, long period, TimeUnit unit) {
            return () -> { };
        }

        @Override
        public boolean usesDaemonThread() {
            return true;
        }

        @Override
        public void close() {
        }
    }
}
