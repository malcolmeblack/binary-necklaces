import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * Tractable child-JVM fixture that mirrors the protected orchestration order:
 * construct a Powerset, pause if requested, then call print().
 */
public final class PrematureProgressChild {
    private PrematureProgressChild() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("usage: PrematureProgressChild <pause-before-print|invalid-output> <n>");
        }
        String mode = args[0];
        int n = Integer.parseInt(args[1]);

        Powerset ps = new Powerset(n);
        System.out.println("CONSTRUCTED");
        System.out.flush();

        if ("pause-before-print".equals(mode)) {
            BufferedReader commands = new BufferedReader(
                    new InputStreamReader(System.in, StandardCharsets.UTF_8));
            String command = commands.readLine();
            if (command == null || !command.startsWith("WAIT ")) {
                throw new IllegalStateException("expected WAIT command");
            }
            long pauseMillis = Long.parseLong(command.substring("WAIT ".length()));
            Thread.sleep(pauseMillis);
            System.out.println("PAUSE_COMPLETE");
            System.out.flush();
            command = commands.readLine();
            if (!"PRINT".equals(command)) {
                throw new IllegalStateException("expected PRINT command");
            }
        } else if (!"invalid-output".equals(mode)) {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }

        ps.print();
        System.out.println("PRINT_RETURNED");
        System.out.flush();
    }
}
