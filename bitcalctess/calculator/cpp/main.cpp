#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include "calc.h"
#include "util.h"
using namespace std;


int main1() {

	int n = 10;
	vector<vector<unsigned char>> chs = chains(n);

	ofstream file;
	file.open ("output/" + to_string(n) + ".txt");
	file << "n: " << n << "\n";
	for (int i = 0; i < chs.size(); i++) {
		file << arrayToString(n, chs[i]);
	}
	file.close();

	return 0;
}

int main() {

	printf("\nEnter a binary word: ");

	// load bit string into temp
	// n = number of bits
	// copy to ca[], which has n elements  
	char temp[31];
	int n = 0;
	int ch;
	while ((ch = getchar()) != '\n' && n < 30) {
		temp[n++] = ch;
	}
	vector<unsigned char> ca(temp, temp + 1 + 1);
	for (int i = 0; i <= n; i++) {
		ca[i] = temp[i];
	}

	vector<unsigned char> bs = charsToBitArray(n, ca);
	vector<unsigned char> bscpy = bs;

	printf("\nBinary word: ");
	printArray(n, bs);

	printf("\nProperties of the binary word:\n");
	printf("# of bits: %d\n", n);
	printf("Parity: ");
	bool p = parity(n, bs);
	if (p) {
		printf("Odd\n");
	} else {
		printf("Even\n");
	}
	printf("Complement: ");
	printArray(n, inverse(n, bs));
	bscpy = inverse(n, bs); // reset bs
	printf("Reversal: ");
	printArray(n, reverse(n, bs));
	printf("Primitive root: ");
	printArray(n, pattern(n, bs));

	printf("\nProperties of the necklace to which the binary word belongs:");
	printf("\nChirality: ");
	bool s = isSymmetric(n, bs);
	if (s) {
		printf("Achiral\n");
	} else {
		printf("Chiral\n");
	}
	printf("Adjacent-XOR image representative: ");
	printArray(n, link(n, bs));
	printf("One preimage representative: ");
	printArray(n, sublink(n, bs));
	minValRot(n, bs);
	printf("Min value rotation: ");
	printArray(n, bs);

	printf("\nProperties of the tree to which the necklace belongs:");
	printf("\nRoot: ");
	printArray(n, root(n, bs));

	printf("\nProperties of the power set to which the component belongs:");
	printf("\nSee \"output/%d.txt\"", n);
	printf("\n\n");

	vector<vector<unsigned char>> chs = chains(n);
	ofstream file;
	file.open ("output/" + to_string(n) + ".txt");
	file << "Components in the word space of n = "<< n << ":\n";
	for (int i = 0; i < chs.size(); i++) {
		file << arrayToString(n, chs[i]);
	}
	file.close();

	return 0;

}
















