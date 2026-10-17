#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "calc.h"
#include "util.h"


int main() {

	printf("\nEnter a binary word: ");

	// load bit string into temp
	// n = number of bits
	// copy to ca[], which has n elements  
	char temp[31];
	int n = 0;
	int ch;
	while ((ch = getchar()) != '\n' && ch != EOF && n < 30) {
		temp[n++] = ch;
	}
	char *ca = (char *)malloc(n + 1);
	for (int i = 0; i <= n; i++) {
		ca[i] = temp[i];
	}

	// initialize bit array used for further calculations
	unsigned char* bs = charsToBitArray(n, ca);
	unsigned char* bscpy = (unsigned char *)malloc(n);
	memcpy(bscpy, bs, n);

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
	int nP;
	printArray(n, pattern(n, bs, &nP));

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
	printf("\nList of components:\n");
	ArrayList* cns = chains(n);
	for (int i = 0; i < cns->size; i++) {
		printArray(n, getArray(cns, i));
	}
	printf("\n");

	free(bs);
	free(ca);
	return 0;
}
























