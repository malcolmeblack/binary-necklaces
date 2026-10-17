import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Deterministic unit and generated checks for path ownership and live progress.
 *
 * <p>Property 1: Expected Behavior - Observable Incomplete Main-Path Work Is Never Complete.
 * <b>Validates: Requirements 2.1, 2.2</b>
 *
 * <p>Property 3: Preservation - Monotonic Complete Progress Records.
 * <b>Validates: Requirements 3.1, 3.4, 3.5</b>
 */
public final class MainRunProgressUnitTest {
    private static final long PROPERTY_SEED = 3_606_202_503L;
    private static final long SECOND = TimeUnit.SECONDS.toNanos(1);
    private static final Pattern RECORD = Pattern.compile(
            "^n=(\\d+) progress=\\s*([0-9]+(?:\\.[0-9]+)?)% "
                    + "elapsed=([0-9]+):([0-9]{2}):([0-9]{2}) ETA=(.*?) \\[(.*)]$");

    private MainRunProgressUnitTest() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length > 0 && "standalone-child".equals(args[0])) {
            ParallelCalculator.chainReps(4, 2);
            return;
        }

        System.err.println("PROPERTY_SEED=" + PROPERTY_SEED);
        pathDetectionRequiresExactFramesInOneSnapshot();
        workerAggregationExcludesActiveCandidatesAndScalesChainWork();
        mainPathAssemblyRemainsLiveAndStandaloneStillCompletes();
        fixedRateHeartbeatUsesOneDaemonSchedulerAndDoesNotOverlap();
        liveRecordsKeepCompleteFieldsAndHighWaterMarks();
        etaStatesAreTruthfulAndZeroIsReserved();
        downstreamMilestonesAreConservativeHighWaterEvidence();
        liveOutputObservationIsReadOnlyAndExpectedArtifactOnly();
        generatedLiveHistoriesSatisfyPropertiesOneAndThree();
        generatedWorkerSnapshotsPreserveAggregationInvariants();
        System.out.println("MainRunProgressUnitTest PASS: seed=" + PROPERTY_SEED);
    }

    private static void pathDetectionRequiresExactFramesInOneSnapshot() {
        StackTraceElement chain = frame("ParallelCalculator", "chainReps");
        StackTraceElement main = frame("Main", "main");
        StackTraceElement constructor = frame("Powerset", "<init>");
        assertTrue(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {
            chain, frame("java.lang.Thread", "run"), constructor, main
        }), "realistic Main path was rejected");
        assertTrue(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {
            main, frame("helper.Layer", "invoke"), constructor, chain
        }), "exact frames should be accepted regardless of captured depth/order");

        assertFalse(ParallelCalculator.isMainPathInvocation(null), "null stack classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {chain, main}),
                "missing Powerset constructor classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(
                new StackTraceElement[] {chain, constructor}),
                "missing Main.main classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {
            chain, frame("MainLike", "main"), constructor
        }), "similar Main class classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {
            chain, main, frame("PowersetLike", "<init>")
        }), "similar Powerset class classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {
            chain, frame("Main", "mainly"), frame("Powerset", "init")
        }), "similar method names classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {
            frame("ParallelCalculator", "main"), chain
        }), "ParallelCalculator.main classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {main}),
                "Main frame from first snapshot classified Main");
        assertFalse(ParallelCalculator.isMainPathInvocation(new StackTraceElement[] {constructor}),
                "Powerset frame from separate snapshot classified Main");
    }

    private static void workerAggregationExcludesActiveCandidatesAndScalesChainWork() {
        ParallelRunLog.Worker activeA = worker(0, 10L, false);
        ParallelRunLog.Worker activeB = worker(1, 7L, false);
        ParallelCalculator.ChainProgressObservation active =
                ParallelCalculator.observeWorkerProgress(
                        new ParallelRunLog.Worker[] {activeA, activeB}, 32L);
        assertEquals(15L, active.completed,
                "each active worker's in-flight candidate must be excluded");
        assertEquals(2, active.activeWorkers, "active worker count");

        ParallelRunLog.Worker finished = worker(2, 10L, true);
        ParallelCalculator.ChainProgressObservation mixed =
                ParallelCalculator.observeWorkerProgress(
                        new ParallelRunLog.Worker[] {finished, activeB}, 32L);
        assertEquals(16L, mixed.completed,
                "finished worker must include its final scanned candidate");
        assertEquals(1, mixed.activeWorkers, "mixed active worker count");

        assertDoubleEquals(0.0, ParallelCalculator.scaleMainChainProgress(0L, 32L),
                "zero chain scaling");
        assertDoubleEquals(37.5, ParallelCalculator.scaleMainChainProgress(16L, 32L),
                "half chain scaling");
        assertDoubleEquals(75.0, ParallelCalculator.scaleMainChainProgress(32L, 32L),
                "complete chain scan scaling");
        assertDoubleEquals(75.0, ParallelCalculator.scaleMainChainProgress(40L, 32L),
                "chain scaling cap");
    }

    private static void mainPathAssemblyRemainsLiveAndStandaloneStillCompletes()
            throws Exception {
        Harness harness = new Harness(7);
        try {
            harness.progress.start();
            harness.progress.transferToDownstream(
                    80.0, "downstream work pending", 3);
            MainRunProgress.SessionState state = harness.progress.snapshot();
            assertEquals(MainRunProgress.Phase.DOWNSTREAM, state.phase,
                    "chain assembly did not transfer downstream");
            assertFalse(state.terminalEmitted,
                    "Main-path chain assembly emitted a terminal record");
            assertEquals(0, harness.sink.terminalCount(),
                    "Main-path chain assembly terminal line count");
            assertLiveRecord(harness.sink.last(), 7);
            assertContains(harness.sink.last(), "[downstream work pending]",
                    "Main-path post-chain state");
        } finally {
            harness.progress.close();
        }

        Path directory = Files.createTempDirectory("standalone-progress-");
        try {
            List<String> command = List.of(
                    Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                    "-ea", "-cp", absoluteClassPath(),
                    MainRunProgressUnitTest.class.getName(), "standalone-child");
            Process process = new ProcessBuilder(command).directory(directory.toFile()).start();
            assertTrue(process.waitFor(15L, TimeUnit.SECONDS),
                    "standalone child timed out");
            String stderr = new String(process.getErrorStream().readAllBytes(),
                    StandardCharsets.UTF_8);
            String stdout = new String(process.getInputStream().readAllBytes(),
                    StandardCharsets.UTF_8);
            assertEquals(0, process.exitValue(),
                    "standalone child failed stdout=" + stdout + " stderr=" + stderr);
            List<Record> records = parseRecords(stderr);
            assertTrue(!records.isEmpty(), "standalone child emitted no progress records");
            Record terminal = records.get(records.size() - 1);
            assertDoubleEquals(100.0, terminal.percent, "standalone terminal percent");
            assertEquals("00:00:00", terminal.eta, "standalone terminal ETA");
            assertEquals("complete", terminal.state, "standalone terminal state");
        } finally {
            deleteRecursively(directory);
        }
    }

    private static void fixedRateHeartbeatUsesOneDaemonSchedulerAndDoesNotOverlap()
            throws Exception {
        BlockingSink sink = new BlockingSink();
        Harness harness = new Harness(7, sink);
        try {
            harness.progress.start();
            assertEquals(1, harness.scheduler.scheduleCount,
                    "heartbeat scheduler count");
            assertEquals(SECOND, harness.scheduler.initialDelayNanos,
                    "fixed-rate initial delay");
            assertEquals(SECOND, harness.scheduler.periodNanos,
                    "fixed-rate period");
            assertTrue(harness.progress.heartbeatUsesDaemonThread(),
                    "heartbeat scheduler is not daemon-backed");

            sink.blockNextWrite();
            CountDownLatch secondAttempted = new CountDownLatch(1);
            Thread first = new Thread(harness.progress::heartbeat, "heartbeat-one");
            Thread second = new Thread(() -> {
                secondAttempted.countDown();
                harness.progress.heartbeat();
            }, "heartbeat-two");
            first.start();
            assertTrue(sink.firstBlocked.await(5L, TimeUnit.SECONDS),
                    "first heartbeat did not reach sink");
            second.start();
            assertTrue(secondAttempted.await(5L, TimeUnit.SECONDS),
                    "second heartbeat did not attempt execution");
            sink.release.countDown();
            first.join(5_000L);
            second.join(5_000L);
            assertFalse(first.isAlive() || second.isAlive(),
                    "concurrent heartbeat threads did not finish");
            assertEquals(1, sink.maxConcurrentWrites.get(),
                    "heartbeat emissions overlapped");
        } finally {
            harness.progress.close();
        }
    }

    private static void liveRecordsKeepCompleteFieldsAndHighWaterMarks() {
        Harness harness = new Harness(7);
        try {
            harness.progress.start();
            harness.clock.advance(2L * SECOND);
            harness.progress.publish(MainRunProgress.Phase.CHAIN, 45.0,
                    MainRunProgress.estimatedChainEta(12L), "scanning; active workers=2");
            harness.clock.advance(3L * SECOND);
            harness.progress.publish(MainRunProgress.Phase.CHAIN, 20.0,
                    "calculating", "out-of-order scan snapshot");
            harness.clock.advance(SECOND);
            harness.progress.publish(MainRunProgress.Phase.CHAIN, 99.999,
                    "calculating", "rounding boundary");
            harness.clock.advance(SECOND);
            harness.scheduler.tick();

            List<Record> records = parseRecords(harness.sink.lines());
            assertMonotonicLiveRecords(records, 7);
            assertDoubleEquals(99.99, records.get(records.size() - 1).percent,
                    "nonterminal clamp");
        } finally {
            harness.progress.close();
        }
    }

    private static void etaStatesAreTruthfulAndZeroIsReserved() {
        assertEquals("calculating", MainRunProgress.estimatedChainEta(0L),
                "zero estimate must calculate");
        assertEquals("calculating", MainRunProgress.estimatedChainEta(-4L),
                "negative estimate must calculate");
        assertContains(MainRunProgress.estimatedChainEta(65L), "~00:01:05 (chain scan)",
                "positive chain estimate");

        Harness harness = new Harness(7);
        try {
            harness.progress.start();
            harness.progress.publish(MainRunProgress.Phase.CHAIN, 10.0,
                    "00:00:00", "invalid zero estimate");
            assertEquals("calculating", harness.progress.snapshot().eta,
                    "live zero ETA was not normalized");
            harness.progress.publish(MainRunProgress.Phase.CHAIN, 20.0,
                    MainRunProgress.estimatedChainEta(20L), "measured chain scan");
            assertTrue(harness.progress.snapshot().eta.startsWith("~"),
                    "measured chain ETA was not retained");
            harness.clock.advance(MainRunProgress.STALE_EVIDENCE_NANOS);
            harness.scheduler.tick();
            assertEquals("unavailable", harness.progress.snapshot().eta,
                    "stale chain evidence did not make ETA unavailable");
            harness.progress.transferToDownstream(80.0, "downstream work pending", 3);
            assertEquals("unavailable", harness.progress.snapshot().eta,
                    "opaque downstream ETA must be unavailable");
            assertMonotonicLiveRecords(parseRecords(harness.sink.lines()), 7);
        } finally {
            harness.progress.close();
        }
    }

    private static void downstreamMilestonesAreConservativeHighWaterEvidence() {
        assertEquals(MainRunProgress.DownstreamMilestone.NONE,
                MainRunProgress.downstreamMilestone(null), "null milestone");
        assertEquals(MainRunProgress.DownstreamMilestone.NONE,
                MainRunProgress.downstreamMilestone(new StackTraceElement[] {
                    frame("PowersetLike", "printChainReps"), frame("Powerset", "printChains")
                }), "ambiguous milestone");
        assertEquals(MainRunProgress.DownstreamMilestone.CHAIN_REPORT,
                MainRunProgress.downstreamMilestone(new StackTraceElement[] {
                    frame("Powerset", "partitionChainReps"),
                    frame("Powerset", "printChainReps")
                }), "strongest exact milestone");

        Harness harness = new Harness(7);
        try {
            harness.progress.start();
            harness.progress.transferToDownstream(80.0, "downstream work pending", 3);
            harness.stack.stack = new StackTraceElement[] {frame("Powerset", "graphReps")};
            harness.clock.advance(SECOND);
            harness.scheduler.tick();
            assertDoubleEquals(MainRunProgress.GRAPHING_PERCENT,
                    harness.progress.snapshot().percent, "graph milestone");

            harness.stack.stack = new StackTraceElement[] {
                frame("Powerset", "partitionChainReps")
            };
            harness.clock.advance(SECOND);
            harness.scheduler.tick();
            assertDoubleEquals(MainRunProgress.GRAPHING_PERCENT,
                    harness.progress.snapshot().percent,
                    "regressive stack sample lowered milestone");

            harness.stack.stack = new StackTraceElement[] {
                frame("PowersetLike", "printChainReps")
            };
            harness.clock.advance(SECOND);
            harness.scheduler.tick();
            assertDoubleEquals(MainRunProgress.GRAPHING_PERCENT,
                    harness.progress.snapshot().percent,
                    "ambiguous frame advanced milestone");

            harness.stack.stack = new StackTraceElement[] {
                frame("Powerset", "printChainReps")
            };
            harness.clock.advance(SECOND);
            harness.scheduler.tick();
            assertDoubleEquals(MainRunProgress.CHAIN_REPORT_PERCENT,
                    harness.progress.snapshot().percent, "chain report milestone");
            assertMonotonicLiveRecords(parseRecords(harness.sink.lines()), 7);
        } finally {
            harness.progress.close();
        }
    }

    private static void liveOutputObservationIsReadOnlyAndExpectedArtifactOnly() {
        Harness harness = new Harness(7);
        try {
            harness.progress.start();
            harness.progress.transferToDownstream(80.0, "downstream work pending", 3);
            harness.probe.current = snapshot(128L, 2L, "fresh-file");
            harness.clock.advance(SECOND);
            harness.scheduler.tick();
            assertDoubleEquals(MainRunProgress.OUTPUT_ACTIVITY_PERCENT,
                    harness.progress.snapshot().percent, "fresh output metadata credit");
            assertEquals(0, harness.probe.readCount,
                    "live heartbeat read output content");
            assertTrue(harness.probe.paths.size() >= 2,
                    "baseline and live output metadata were not observed");
            for (Path path : harness.probe.paths) {
                assertEquals(Path.of("output", "p7.csv"), path,
                        "observer probed an unexpected artifact");
            }
            assertMonotonicLiveRecords(parseRecords(harness.sink.lines()), 7);
        } finally {
            harness.progress.close();
        }
    }

    private static void generatedLiveHistoriesSatisfyPropertiesOneAndThree() {
        Random random = new Random(PROPERTY_SEED);
        Harness harness = new Harness(7);
        try {
            harness.progress.start();
            boolean downstream = false;
            for (int index = 0; index < 256; index++) {
                harness.clock.advance(random.nextInt(5) * SECOND);
                int action = random.nextInt(6);
                if (!downstream && action < 3) {
                    double percent = random.nextDouble() * 90.0;
                    String eta = action == 0 ? "calculating"
                            : MainRunProgress.estimatedChainEta(1L + random.nextInt(600));
                    harness.progress.publish(MainRunProgress.Phase.CHAIN,
                            percent, eta, "generated chain case=" + index);
                } else {
                    if (!downstream) {
                        harness.progress.transferToDownstream(80.0,
                                "generated downstream case=" + index, 3);
                        downstream = true;
                    }
                    harness.stack.stack = generatedStack(random);
                    harness.probe.current = random.nextBoolean()
                            ? MainRunProgress.OutputSnapshot.missing()
                            : snapshot(100L + index, 10L + index, "generated-" + index);
                    harness.scheduler.tick();
                    if (action == 5) {
                        harness.progress.publish(MainRunProgress.Phase.CHAIN,
                                random.nextDouble() * 75.0, "calculating",
                                "generated stale phase case=" + index);
                    }
                }
            }
            List<Record> records = parseRecords(harness.sink.lines());
            assertTrue(records.size() >= 256, "generated history omitted records");
            assertMonotonicLiveRecords(records, 7);
            assertEquals(0, harness.sink.terminalCount(),
                    "generated live history emitted terminal output");
            assertEquals(0, harness.probe.readCount,
                    "generated live history read artifact content");
        } catch (AssertionError failure) {
            throw new AssertionError("seed=" + PROPERTY_SEED + " " + failure.getMessage(), failure);
        } finally {
            harness.progress.close();
        }
    }

    private static void generatedWorkerSnapshotsPreserveAggregationInvariants() {
        Random random = new Random(PROPERTY_SEED ^ 0x5EED5EEDL);
        for (int caseIndex = 0; caseIndex < 200; caseIndex++) {
            int workerCount = 1 + random.nextInt(8);
            long total = 1L + random.nextInt(10_000);
            ParallelRunLog.Worker[] workers = new ParallelRunLog.Worker[workerCount];
            long expected = 0L;
            int expectedActive = 0;
            for (int workerIndex = 0; workerIndex < workerCount; workerIndex++) {
                long scanned = random.nextInt(2_000);
                boolean finished = random.nextBoolean();
                workers[workerIndex] = worker(workerIndex, scanned, finished);
                expected += Math.max(0L, scanned - (finished ? 0L : 1L));
                if (!finished) expectedActive++;
            }
            expected = Math.min(total, expected);
            ParallelCalculator.ChainProgressObservation observation =
                    ParallelCalculator.observeWorkerProgress(workers, total);
            assertEquals(expected, observation.completed,
                    "generated aggregation case=" + caseIndex + " seed=" + PROPERTY_SEED);
            assertEquals(expectedActive, observation.activeWorkers,
                    "generated active count case=" + caseIndex + " seed=" + PROPERTY_SEED);
            double scaled = ParallelCalculator.scaleMainChainProgress(
                    observation.completed, total);
            assertTrue(scaled >= 0.0 && scaled <= 75.0,
                    "generated scaling out of range case=" + caseIndex
                            + " seed=" + PROPERTY_SEED + " scaled=" + scaled);
        }
    }

    private static StackTraceElement[] generatedStack(Random random) {
        switch (random.nextInt(8)) {
            case 0:
                return new StackTraceElement[] {frame("Powerset", "partitionChainReps")};
            case 1:
                return new StackTraceElement[] {frame("Powerset", "graphReps")};
            case 2:
                return new StackTraceElement[] {frame("Powerset", "print")};
            case 3:
                return new StackTraceElement[] {frame("Powerset", "printPowerset")};
            case 4:
                return new StackTraceElement[] {frame("Powerset", "printGraphs")};
            case 5:
                return new StackTraceElement[] {frame("Powerset", "printChainReps")};
            case 6:
                return new StackTraceElement[] {frame("PowersetLike", "printChainReps")};
            default:
                return new StackTraceElement[0];
        }
    }

    private static ParallelRunLog.Worker worker(int id, long scanned, boolean finished) {
        ParallelRunLog.Worker worker = new ParallelRunLog.Worker(id, System.nanoTime());
        worker.start();
        worker.scanned = scanned;
        worker.publish();
        if (finished) {
            worker.finish();
        }
        return worker;
    }

    private static void assertMonotonicLiveRecords(List<Record> records, int expectedN) {
        assertTrue(!records.isEmpty(), "progress history is empty");
        double previousPercent = -1.0;
        long previousElapsed = -1L;
        for (Record record : records) {
            assertEquals(expectedN, record.n, "record n field");
            assertTrue(record.percent >= previousPercent,
                    "percentage regressed from " + previousPercent + " in " + record.line);
            assertTrue(record.elapsedSeconds >= previousElapsed,
                    "elapsed regressed from " + previousElapsed + " in " + record.line);
            assertTrue(record.percent < 100.0,
                    "live work reached terminal percentage: " + record.line);
            assertFalse("00:00:00".equals(record.eta),
                    "live work used zero ETA: " + record.line);
            assertFalse("complete".equals(record.state),
                    "live work reported complete: " + record.line);
            assertTrue("calculating".equals(record.eta)
                            || "unavailable".equals(record.eta)
                            || (record.eta.startsWith("~")
                                    && record.eta.endsWith(" (chain scan)")),
                    "live work used unsupported ETA: " + record.line);
            assertTrue(!record.state.isEmpty(), "record state is empty: " + record.line);
            previousPercent = record.percent;
            previousElapsed = record.elapsedSeconds;
        }
    }

    private static void assertLiveRecord(String line, int n) {
        List<Record> records = parseRecords(line);
        assertEquals(1, records.size(), "single live record parse");
        assertMonotonicLiveRecords(records, n);
    }

    private static List<Record> parseRecords(String output) {
        List<Record> records = new ArrayList<>();
        for (String line : output.split("\\R")) {
            Matcher matcher = RECORD.matcher(line);
            if (!matcher.matches()) {
                if (!line.isEmpty()) {
                    throw new AssertionError("malformed progress record: " + line);
                }
                continue;
            }
            long elapsed = Long.parseLong(matcher.group(3)) * 3_600L
                    + Long.parseLong(matcher.group(4)) * 60L
                    + Long.parseLong(matcher.group(5));
            records.add(new Record(line, Integer.parseInt(matcher.group(1)),
                    Double.parseDouble(matcher.group(2)), elapsed,
                    matcher.group(6), matcher.group(7)));
        }
        return records;
    }

    private static StackTraceElement frame(String className, String methodName) {
        return new StackTraceElement(className, methodName, className + ".java", 1);
    }

    private static MainRunProgress.OutputSnapshot snapshot(
            long size, long modifiedMillis, String key) {
        return new MainRunProgress.OutputSnapshot(
                true, true, size, modifiedMillis, 1L, key, null);
    }

    private static String absoluteClassPath() {
        Path base = Path.of("").toAbsolutePath().normalize();
        String[] entries = System.getProperty("java.class.path")
                .split(Pattern.quote(System.getProperty("path.separator")));
        List<String> absolute = new ArrayList<>();
        for (String entry : entries) {
            Path path = Path.of(entry);
            absolute.add((path.isAbsolute() ? path : base.resolve(path)).normalize().toString());
        }
        return String.join(System.getProperty("path.separator"), absolute);
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

    private static void assertContains(String actual, String expected, String context) {
        assertTrue(actual != null && actual.contains(expected),
                context + " missing " + expected + ": " + actual);
    }

    private static void assertDoubleEquals(double expected, double actual, String context) {
        if (Math.abs(expected - actual) > 0.000_001) {
            throw new AssertionError(context + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void assertEquals(Object expected, Object actual, String context) {
        if (!java.util.Objects.equals(expected, actual)) {
            throw new AssertionError(context + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void assertEquals(long expected, long actual, String context) {
        if (expected != actual) {
            throw new AssertionError(context + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void assertTrue(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static void assertFalse(boolean condition, String message) {
        assertTrue(!condition, message);
    }

    private static final class Record {
        final String line;
        final int n;
        final double percent;
        final long elapsedSeconds;
        final String eta;
        final String state;

        Record(String line, int n, double percent, long elapsedSeconds,
                String eta, String state) {
            this.line = line;
            this.n = n;
            this.percent = percent;
            this.elapsedSeconds = elapsedSeconds;
            this.eta = eta;
            this.state = state;
        }
    }

    private static final class Harness {
        final FakeClock clock = new FakeClock();
        final CapturingSink sink;
        final FakeStackSource stack = new FakeStackSource();
        final MetadataProbe probe = new MetadataProbe();
        final FakeShutdownRegistrar shutdown = new FakeShutdownRegistrar();
        final FakeScheduler scheduler = new FakeScheduler();
        final MainRunProgress progress;

        Harness(int n) {
            this(n, new CapturingSink());
        }

        Harness(int n, CapturingSink sink) {
            this.sink = sink;
            progress = new MainRunProgress(
                    n,
                    Thread.currentThread(),
                    clock,
                    sink,
                    stack,
                    probe,
                    Path.of("output", "p" + n + ".csv"),
                    shutdown,
                    scheduler,
                    SECOND);
        }
    }

    private static final class FakeClock implements MainRunProgress.MonotonicClock {
        private long now;

        synchronized void advance(long nanos) {
            if (nanos < 0L) {
                throw new IllegalArgumentException("clock cannot move backward");
            }
            now += nanos;
        }

        @Override
        public synchronized long nanoTime() {
            return now;
        }
    }

    private static class CapturingSink implements MainRunProgress.LineSink {
        private final List<String> lines = new ArrayList<>();
        private int terminalCount;

        @Override
        public synchronized void write(String line, boolean terminal) {
            lines.add(line);
            if (terminal) {
                terminalCount++;
            }
        }

        synchronized String lines() {
            return String.join(System.lineSeparator(), lines);
        }

        synchronized String last() {
            if (lines.isEmpty()) {
                throw new AssertionError("sink is empty");
            }
            return lines.get(lines.size() - 1);
        }

        synchronized int terminalCount() {
            return terminalCount;
        }
    }

    private static final class BlockingSink extends CapturingSink {
        final CountDownLatch firstBlocked = new CountDownLatch(1);
        final CountDownLatch release = new CountDownLatch(1);
        final AtomicInteger maxConcurrentWrites = new AtomicInteger();
        private final AtomicInteger concurrentWrites = new AtomicInteger();
        private volatile boolean block;

        void blockNextWrite() {
            block = true;
        }

        @Override
        public void write(String line, boolean terminal) {
            int concurrent = concurrentWrites.incrementAndGet();
            maxConcurrentWrites.accumulateAndGet(concurrent, Math::max);
            try {
                if (block) {
                    block = false;
                    firstBlocked.countDown();
                    try {
                        release.await();
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError("blocking sink interrupted", interrupted);
                    }
                }
                super.write(line, terminal);
            } finally {
                concurrentWrites.decrementAndGet();
            }
        }
    }

    private static final class FakeStackSource
            implements MainRunProgress.StackSnapshotSource {
        volatile StackTraceElement[] stack = new StackTraceElement[0];

        @Override
        public StackTraceElement[] snapshot(Thread thread) {
            return stack.clone();
        }
    }

    private static final class MetadataProbe implements MainRunProgress.OutputProbe {
        MainRunProgress.OutputSnapshot current = MainRunProgress.OutputSnapshot.missing();
        final List<Path> paths = new ArrayList<>();
        int readCount;

        @Override
        public synchronized MainRunProgress.OutputSnapshot snapshot(Path path) {
            paths.add(path);
            return current;
        }

        @Override
        public synchronized byte[] readAllBytes(Path path) throws IOException {
            readCount++;
            throw new IOException("live progress must not read output content");
        }
    }

    private static final class FakeShutdownRegistrar
            implements MainRunProgress.ShutdownRegistrar {
        Runnable action;

        @Override
        public MainRunProgress.ShutdownRegistration register(Runnable registeredAction) {
            action = registeredAction;
            return () -> { };
        }
    }

    private static final class FakeScheduler
            implements MainRunProgress.HeartbeatScheduler {
        Runnable action;
        int scheduleCount;
        long initialDelayNanos;
        long periodNanos;

        @Override
        public MainRunProgress.HeartbeatTask scheduleAtFixedRate(
                Runnable scheduledAction, long initialDelay, long period, TimeUnit unit) {
            action = scheduledAction;
            scheduleCount++;
            initialDelayNanos = unit.toNanos(initialDelay);
            periodNanos = unit.toNanos(period);
            return () -> { };
        }

        void tick() {
            if (action == null) {
                throw new AssertionError("heartbeat was not scheduled");
            }
            action.run();
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
