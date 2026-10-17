import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Deterministic task 3.5 checks for directly observable failure and cancellation. */
public final class MainRunProgressFailureTest {
    private MainRunProgressFailureTest() {
    }

    public static void main(String[] args) throws Exception {
        uncaughtFailureIsRecordedDelegatedAndRestored();
        liveOwnerShutdownIsCancelledAndBounded();
        observedFailureAndLiveShutdownAreCombined();
        closeRestoresHandlerAndMakesLaterSignalsNoOps();
        interruptedChainPreservesPropagationInterruptAndHandler();
        System.out.println("MainRunProgressFailureTest PASS");
    }

    private static void uncaughtFailureIsRecordedDelegatedAndRestored() {
        Thread owner = Thread.currentThread();
        Thread.UncaughtExceptionHandler before = owner.getUncaughtExceptionHandler();
        AtomicInteger delegated = new AtomicInteger();
        AtomicReference<Throwable> delegatedFailure = new AtomicReference<>();
        Thread.UncaughtExceptionHandler original = (thread, failure) -> {
            assertSame(owner, thread, "delegated owner");
            delegated.incrementAndGet();
            delegatedFailure.set(failure);
        };
        owner.setUncaughtExceptionHandler(original);
        try {
            Harness harness = new Harness(owner);
            harness.progress.start();
            Thread.UncaughtExceptionHandler installed = owner.getUncaughtExceptionHandler();
            assertTrue(installed != original, "delegating handler was not installed");

            IllegalStateException failure = new IllegalStateException("observable owner failure");
            installed.uncaughtException(owner, failure);
            assertEquals(1, delegated.get(), "original handler delegation count");
            assertSame(failure, delegatedFailure.get(), "delegated throwable");
            assertSame(failure, harness.progress.snapshot().observedFailure,
                    "recorded failure evidence");

            harness.progress.finish(MainRunProgress.TerminalOutcome.CANCELLED);
            harness.progress.finish(MainRunProgress.TerminalOutcome.FAILED);
            harness.progress.recordFailure(new AssertionError("late competing failure"));
            harness.progress.heartbeat();

            assertEquals(1, harness.sink.terminalLines.size(), "terminal emission count");
            assertNonSuccess(harness.sink.terminalLines.get(0), "failed/cancelled");
            assertSame(original, owner.getUncaughtExceptionHandler(),
                    "original handler restoration after finish");
            assertEquals(1, harness.scheduler.cancelCount, "heartbeat cancellation count");
            harness.progress.close();
        } finally {
            owner.setUncaughtExceptionHandler(before);
        }
    }

    private static void liveOwnerShutdownIsCancelledAndBounded() throws Exception {
        RunningOwner running = new RunningOwner("live-owner-cancellation");
        Thread.UncaughtExceptionHandler original = (thread, failure) -> { };
        running.thread.setUncaughtExceptionHandler(original);
        running.start();
        try {
            Harness harness = new Harness(running.thread);
            harness.progress.start();
            harness.progress.transferToDownstream(80.0, "downstream work pending", 1);
            harness.progress.runShutdownObservation();
            harness.progress.runShutdownObservation();
            harness.progress.finish(MainRunProgress.TerminalOutcome.FAILED);
            harness.progress.recordFailure(new IllegalStateException("late failure"));
            harness.progress.heartbeat();

            assertEquals(1, harness.sink.terminalLines.size(), "cancelled terminal count");
            assertNonSuccess(harness.sink.terminalLines.get(0), "cancelled");
            assertSame(original, running.thread.getUncaughtExceptionHandler(),
                    "handler restoration after shutdown");
            assertEquals(2, harness.probe.snapshotCount,
                    "baseline plus one bounded final output observation");
            assertEquals(0, harness.probe.readCount, "cancelled output read count");
            assertEquals(1, harness.stack.snapshotCount, "bounded owner stack count");
            assertEquals(1, harness.scheduler.cancelCount, "shutdown heartbeat cancellation");
            assertEquals(1, harness.scheduler.closeCount, "scheduler close count");
        } finally {
            running.stop();
        }
    }

    private static void observedFailureAndLiveShutdownAreCombined() throws Exception {
        RunningOwner running = new RunningOwner("live-owner-failure");
        AtomicInteger delegated = new AtomicInteger();
        Thread.UncaughtExceptionHandler original = (thread, failure) -> delegated.incrementAndGet();
        running.thread.setUncaughtExceptionHandler(original);
        running.start();
        try {
            Harness harness = new Harness(running.thread);
            harness.progress.start();
            RuntimeException failure = new RuntimeException("uncaught downstream failure");
            running.thread.getUncaughtExceptionHandler()
                    .uncaughtException(running.thread, failure);
            harness.progress.runShutdownObservation();

            assertEquals(1, delegated.get(), "downstream uncaught delegation count");
            assertSame(failure, harness.progress.snapshot().observedFailure,
                    "downstream failure evidence");
            assertEquals(1, harness.sink.terminalLines.size(), "combined terminal count");
            assertNonSuccess(harness.sink.terminalLines.get(0), "failed/cancelled");
            assertSame(original, running.thread.getUncaughtExceptionHandler(),
                    "handler restoration after combined outcome");
        } finally {
            running.stop();
        }
    }

    private static void closeRestoresHandlerAndMakesLaterSignalsNoOps() {
        Thread owner = Thread.currentThread();
        Thread.UncaughtExceptionHandler before = owner.getUncaughtExceptionHandler();
        Thread.UncaughtExceptionHandler original = (thread, failure) -> { };
        owner.setUncaughtExceptionHandler(original);
        try {
            Harness harness = new Harness(owner);
            harness.progress.start();
            harness.progress.close();
            harness.progress.close();
            harness.progress.recordFailure(new IllegalStateException("after close"));
            harness.progress.finish(MainRunProgress.TerminalOutcome.CANCELLED);
            harness.progress.heartbeat();

            assertSame(original, owner.getUncaughtExceptionHandler(),
                    "handler restoration after close");
            assertEquals(0, harness.sink.terminalLines.size(), "close terminal count");
            assertEquals(1, harness.shutdown.removeCount, "shutdown removal count");
            assertEquals(1, harness.scheduler.cancelCount, "close heartbeat cancellation");
            assertEquals(1, harness.scheduler.closeCount, "close scheduler count");
        } finally {
            owner.setUncaughtExceptionHandler(before);
        }
    }

    private static void interruptedChainPreservesPropagationInterruptAndHandler()
            throws Exception {
        Thread owner = Thread.currentThread();
        Thread.UncaughtExceptionHandler original = owner.getUncaughtExceptionHandler();
        PrintStream previousErr = System.err;
        ByteArrayOutputStream capturedBytes = new ByteArrayOutputStream();
        boolean interruptRetained = false;
        System.setErr(new PrintStream(capturedBytes, true, StandardCharsets.UTF_8));
        try (ParallelCalculator.InvocationStackOverride ignored =
                ParallelCalculator.useInvocationStackForTesting(mainPathStack())) {
            owner.interrupt();
            try {
                ParallelCalculator.chainReps(6, 2);
                throw new AssertionError("interrupted chain unexpectedly returned");
            } catch (IllegalStateException expected) {
                assertContains(expected.getMessage(), "interrupted",
                        "interruption propagation message");
                assertTrue(expected.getCause() instanceof InterruptedException,
                        "interruption cause was not preserved");
                interruptRetained = owner.isInterrupted();
            } finally {
                Thread.interrupted();
            }
        } finally {
            System.setErr(previousErr);
        }

        assertTrue(interruptRetained, "owner interrupt status was not retained");
        assertSame(original, owner.getUncaughtExceptionHandler(),
                "handler changed by interrupted chain");
        String progress = capturedBytes.toString(StandardCharsets.UTF_8);
        assertContains(progress, "[failed/cancelled]", "interrupted chain terminal state");
        assertTrue(!progress.contains("progress=100.00%"),
                "interrupted chain reported 100%: " + progress);
        assertTrue(!progress.contains("ETA=00:00:00"),
                "interrupted chain reported zero ETA: " + progress);
        assertTrue(!progress.contains("[complete]"),
                "interrupted chain reported complete: " + progress);
    }

    private static StackTraceElement[] mainPathStack() {
        return new StackTraceElement[] {
            new StackTraceElement("ParallelCalculator", "chainReps",
                    "ParallelCalculator.java", 1),
            new StackTraceElement("Powerset", "<init>", "Powerset.java", 1),
            new StackTraceElement("Main", "main", "Main.java", 1)
        };
    }

    private static void assertNonSuccess(String line, String state) {
        assertContains(line, "[" + state + "]", "non-success state");
        assertContains(line, "ETA=unavailable", "non-success ETA");
        assertTrue(!line.contains("progress=100.00%"),
                "non-success reached 100%: " + line);
        assertTrue(!line.contains("ETA=00:00:00"),
                "non-success used zero ETA: " + line);
        assertTrue(!line.contains("[complete]"),
                "non-success completed: " + line);
    }

    private static void assertContains(String actual, String expected, String context) {
        assertTrue(actual != null && actual.contains(expected),
                context + " missing " + expected + ": " + actual);
    }

    private static void assertSame(Object expected, Object actual, String context) {
        if (expected != actual) {
            throw new AssertionError(context + " expected same instance");
        }
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
        final IncrementingClock clock = new IncrementingClock();
        final CapturingSink sink = new CapturingSink();
        final CountingStackSource stack = new CountingStackSource();
        final MissingProbe probe = new MissingProbe();
        final FakeShutdownRegistrar shutdown = new FakeShutdownRegistrar();
        final FakeScheduler scheduler = new FakeScheduler();
        final MainRunProgress progress;

        Harness(Thread owner) {
            progress = new MainRunProgress(
                    3,
                    owner,
                    clock,
                    sink,
                    stack,
                    probe,
                    Path.of("output", "p3.csv"),
                    shutdown,
                    scheduler,
                    TimeUnit.SECONDS.toNanos(1));
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

    private static final class CountingStackSource
            implements MainRunProgress.StackSnapshotSource {
        int snapshotCount;

        @Override
        public StackTraceElement[] snapshot(Thread thread) {
            snapshotCount++;
            return new StackTraceElement[] {
                new StackTraceElement("Powerset", "print", "Powerset.java", 1)
            };
        }
    }

    private static final class MissingProbe implements MainRunProgress.OutputProbe {
        int snapshotCount;
        int readCount;

        @Override
        public MainRunProgress.OutputSnapshot snapshot(Path path) {
            snapshotCount++;
            return MainRunProgress.OutputSnapshot.missing();
        }

        @Override
        public byte[] readAllBytes(Path path) throws IOException {
            readCount++;
            throw new IOException("missing output must not be read");
        }
    }

    private static final class FakeShutdownRegistrar
            implements MainRunProgress.ShutdownRegistrar {
        Runnable action;
        int removeCount;

        @Override
        public MainRunProgress.ShutdownRegistration register(Runnable registeredAction) {
            action = registeredAction;
            return () -> removeCount++;
        }
    }

    private static final class FakeScheduler implements MainRunProgress.HeartbeatScheduler {
        int cancelCount;
        int closeCount;

        @Override
        public MainRunProgress.HeartbeatTask scheduleAtFixedRate(
                Runnable action, long initialDelay, long period, TimeUnit unit) {
            return () -> cancelCount++;
        }

        @Override
        public boolean usesDaemonThread() {
            return true;
        }

        @Override
        public void close() {
            closeCount++;
        }
    }

    private static final class RunningOwner {
        final CountDownLatch started = new CountDownLatch(1);
        final CountDownLatch release = new CountDownLatch(1);
        final Thread thread;

        RunningOwner(String name) {
            thread = new Thread(() -> {
                started.countDown();
                try {
                    release.await();
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                }
            }, name);
        }

        void start() throws InterruptedException {
            thread.start();
            assertTrue(started.await(5, TimeUnit.SECONDS), "owner did not start");
        }

        void stop() throws InterruptedException {
            release.countDown();
            thread.join(5_000L);
            assertTrue(!thread.isAlive(), "owner did not terminate");
        }
    }
}
