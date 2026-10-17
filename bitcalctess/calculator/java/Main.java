import java.util.Scanner;
import java.time.Instant;

public class Main {

	public static void main(String[] args) {

		//Scanner sc = new Scanner(System.in);
		//System.out.println("Number of bits?");
		//int n = sc.nextInt();
		int n;
		for (n = 29; n <= 29; n++) {
			long startTime = Instant.now().getEpochSecond();
			Powerset ps = new Powerset(n);
			ps.print();
			long totalTime = Instant.now().getEpochSecond() - startTime;
			System.out.println("n: " + n + "\nTotal time: " + totalTime + "\n");
		}
	}

}
