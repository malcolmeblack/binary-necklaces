# Binary Necklace Calculator (Java)

Requires JDK.

Compile
`javac Main.java`

Run
`java Main`

Enter a value for *n*, and the program outputs a .csv file with properties of the power set of *n*. Execution time gets very long for values of *n* higher than 20, mostly due to the chainReps method that finds one representative binary necklace for every chain that partitions a power set. There are two versions of chainReps, v1 and v2, and one may be faster than the other depending on the value of *n*.

The table below gives the time (in seconds unless otherwise noted) to execute the program for some value *n* on my MacBook. max-cycle-length is the maximum cycle length comparing chains in the power set, and cycle length is how many binary necklaces are in a chain's cycle. Larger power sets mostly consist of many isomorphic chains having the maximum cycle length.

n		|v1		|v2		|max-cycle-length
---|---|---|---
15		|3		|1		|15
17		|10		|1		|15
18		|6		|1		|14
19		|32		|>600	|511
20		|>600	|2		|12
21		|>600	|74		|63
22		|>600	|67		|62
23		|>600	|>3600	|2047
24		|		|129	|8
25		|		|30h35m	|1023
26		|		|53m26s	|126
27		|		|35h56m	|511
28		|		|43m	|28










