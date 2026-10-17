# Mathematical and Format Reference

- [Partition proof](#partition-proof)
- [Compressed census](#compressed-census)
- [Integer certificates](#integer-certificates)
- [Certificate examples](#certificate-examples)
- [Legacy certificate format](#legacy-certificate-format)


<a id="partition-proof"></a>

## A representative-free classification of bitloop graphs

### Result and meaning of the conjecture

**The conjecture is true for the adjacent-XOR link operation used by the calculator, with the precise meaning below.** For every positive integer \(n\), one can determine all graph types, the exact number of chains of each type, and an exact symbolic partition of the \(2^n\) bitstrings, without enumerating the bitstrings or finding a representative bitstring for each chain.

This is a mathematical classification theorem for every positive \(n\), not merely for \(n\le64\). It does not assert that the computation is polynomial-time, that every future implementation will be correct, or that expanding a large catalogue becomes inexpensive.

“Without listing elements” means that the output consists of algebraic descriptors, graph types, and integer counts. Polynomial arithmetic is allowed; listing individual original bitstrings or choosing one from every chain is unnecessary. A finite set can be specified exactly by a formula without printing its members. The proof gives both that formula and a procedure for expanding a selected part on demand.

The companion [v2-certificate-and-examples.md](#certificate-examples) explains the implications for version 2, the \(n=14\) example, and the independently checkable partition certificate.

### 1. Definitions and the three reconstruction lemmas

Let \(V_n=\mathbb F_2^n\), the set of bitstrings identified with the power set of a fixed labelled \(n\)-element set. Let \(R\) be cyclic rotation by one position and

\[
L=I+R
\]

be the link operation; addition is XOR. The choice of rotation direction only changes the coordinate convention.

A **bitloop** is a rotation class \([v]=\{R^iv:0\le i<n\}\). Linking gives a well-defined map on bitloops because \(LR=RL\).

The **bitloop functional graph** has these classes as vertices, with the edge \([v]\to[Lv]\). An **actual chain** means a weakly connected component of this graph: its cycle together with every attached predecessor tree. A **graph type** is the directed-graph isomorphism type of an actual chain, including its cycle and trees but forgetting its bitstring labels.

The individual chains partition the bitloops and, by taking their rotation classes, partition the bitstrings. Grouping those chains by graph type gives a coarser partition. A list of distinct graph names alone is insufficient: multiplicities and bitstring accounting matter.

Reversal-related chains are counted separately throughout the theorem. Version 1 sometimes stores two of them in one CSV row with `multiplicity=2`; that storage convention is not the definition of a connected component.

#### Lemma 1: a bitloop determines its bitstrings

For a supplied word \(v\), let \(d(v)\) be its least positive rotation period. Its bitloop consists exactly of

\[
v,Rv,\ldots,R^{d(v)-1}v.
\]

They are distinct by minimality of \(d(v)\), and all other rotations repeat them. Thus a representative and the rotation operation determine the entire bitloop. Notice that \(d(v)\) may be smaller than \(n\).

#### Lemma 2: any bitloop in a chain determines the chain

Starting from any bitloop in an actual chain, close the set under both forward links and inverse links. This recovers exactly that chain.

To compute inverse links, choose the coordinate convention in which \(Lw=v\) means

\[
w_i+w_{i+1}=v_i,\qquad i\pmod n.
\]

Choose \(w_0\), then propagate \(w_{i+1}=w_i+v_i\). Cyclic consistency holds exactly when \(\sum_i v_i=0\). In that case there are two complementary solutions; otherwise there are none. Passing to their rotation classes gives all predecessor bitloops: if \(Lw=R^iv\), rotating \(w\) back gives a solution of \(Lw'=v\).

Taking this closure terminates because the graph is finite, and it is precisely the definition of its weakly connected component. An equivalent procedure first finds the eventual cycle and then expands all its predecessors.

**Forward linking alone is insufficient:** it follows one path into a cycle and does not recover every branch. This qualification leaves the intended uniform reconstruction principle intact.

#### Lemma 3, in a stronger form

**Given \(n\) and a graph type, all chains of that type have a uniform algebraic parametrization. No seed chain is necessary.** Sections 2–7 construct and prove this statement.

The operations generating that family are richer than rotation and linking. Those two operations, even with inverse links, stay within one chain. The missing higher-level operation is multiplication in a finite polynomial unit group, together with a classification of the strata that yield the desired graph type.

### 2. Separate the transient and periodic coordinates

Represent words by polynomials modulo \(x^n+1\):

\[
V_n\cong\mathbb F_2[x]/(x^n+1).
\]

Rotation is multiplication by \(x\), and linking is multiplication by \(1+x\).

Write uniquely

\[
n=qm,\qquad q=2^{v_2(n)},\qquad m\text{ odd}.
\]

In characteristic two,

\[
x^n+1=(x^m+1)^q=(x+1)^qP(x),
\qquad
P(x)=\left(\frac{x^m+1}{x+1}\right)^q.
\]

The oddness of \(m\) implies that \(x+1\) is a simple factor of \(x^m+1\). Consequently \(P\) and \((x+1)^q\) are coprime. The Chinese remainder theorem gives a unique decomposition

\[
V_n\cong K\times W,
\qquad
K=\mathbb F_2[x]/((x+1)^q),\qquad
W=\mathbb F_2[x]/P.
\tag{1}
\]

Both operations act coordinatewise. On \(K\), linking is nilpotent: \(L^q=0\). On \(W\), both \(x\) and \(1+x\) are units, so rotation and linking are permutations. Also

\[
|K|=2^q,\qquad |W|=2^{n-q}.
\]

Thus \(K\) describes the part that eventually disappears under linking; \(W\) describes the periodic core. When \(m=1\), \(P=1\) and \(W\) is the one-element coordinate space.

#### Component correspondence

Let \(G=\langle x,1+x\rangle\) act on \(W\). Actual chains correspond bijectively to its orbits \(O\), and the bitstrings of the corresponding chain are exactly the inverse CRT image of

\[
K\times O.
\tag{2}
\]

**Proof.** Every point reaches a point with zero \(K\)-coordinate after at most \(q\) links. Its \(W\)-coordinate remains in the same \(G\)-orbit. Rotation and links cannot join different \(G\)-orbits; neither can inverse links, since linking on \(W\) is invertible.

Within the zero-\(K\) core, taking rotation classes quotients by \(\langle x\rangle\). Linking then traverses exactly one cycle for each \(\langle x,1+x\rangle\)-orbit. Every point of \(K\times O\) feeds into that cycle. Hence (2) is one entire chain, and different such sets are disjoint. ∎

### 3. Classify periodic coordinates by annihilator

For \(z\in W\), define its **annihilator polynomial**

\[
H=\frac{P}{\gcd(P,z)}.
\]

Equivalently, the polynomials that kill \(z\) by multiplication are precisely the multiples of \(H\). Each \(H\) is a monic divisor of \(P\).

Fix such an \(H\), and write \(F_H=P/H\). The elements of exact annihilator \(H\) are uniquely

\[
z=F_Hu\pmod P,
\qquad
u\in U_H:=\left(\mathbb F_2[x]/H\right)^\times.
\tag{3}
\]

Indeed, \(\gcd(P,F_Hu)=F_H\gcd(H,u)\). Having exact annihilator \(H\) is therefore equivalent to \(u\) being a unit modulo \(H\). Multiplication by \(F_H\) identifies residues modulo \(H\) injectively with these multiples modulo \(P\), establishing uniqueness.

If

\[
H=\prod_i f_i^{e_i},\qquad r_i=\deg f_i,
\]

where the \(f_i\) are distinct monic irreducibles, then

\[
\Phi(H):=|U_H|
=\prod_{e_i>0}2^{r_i(e_i-1)}(2^{r_i}-1).
\tag{4}
\]

For one prime-power factor, the nonunits are exactly the multiples of \(f_i\). Subtracting their number from all residues gives the corresponding factor in (4); CRT multiplies these counts.

For \(H=1\), adopt the conventions \(\Phi(1)=1\) and trivial unit/action groups. This is the zero-core stratum, handled without exceptional bitstring enumeration.

### 4. Chains are unit-group cosets

Define

\[
G_H=\langle x\bmod H,(1+x)\bmod H\rangle\subseteq U_H.
\]

Under (3), its multiplication action is exactly the rotation/link action on the stratum. The action is free: if \(gu=u\) and \(u\) is a unit, cancellation gives \(g=1\). Therefore

\[
\boxed{\quad
\{\text{actual chains at }n\}
\longleftrightarrow
\bigsqcup_{H\mid P} U_H/G_H.
\quad}
\tag{5}
\]

Let

\[
d_H=\operatorname{ord}_H(x),\qquad
t_H=\operatorname{ord}_{U_H/\langle x\rangle}((1+x)\langle x\rangle).
\]

Then \(d_H\) is the rotation period of every core word in the stratum, and \(t_H\) is its bitloop cycle length. The quotient \(G_H/\langle x\rangle\) is cyclic, generated by the image of \(1+x\), so

\[
|G_H|=d_Ht_H,
\qquad
\boxed{A_H=\frac{\Phi(H)}{d_Ht_H}}
\tag{6}
\]

is the number of actual chains in that stratum. Each has

\[
\boxed{B_H=2^q d_Ht_H}
\tag{7}
\]

original bitstrings. For \(H=1\), set \(d_H=t_H=A_H=1\).

#### An exact symbolic decoder

For a formal coset \(c\in U_H/G_H\), define

\[
\mathcal C_{H,c}
=\operatorname{CRT}^{-1}
\left\{(a,F_Hu):a\in K,\ u\in c\right\}.
\tag{8}
\]

This specifies a particular chain as a set of original bitstrings, without listing one. Its bitloops are the rotation classes of that set; its edges are supplied by \(L\).

If expansion is requested, one can choose any \(u\) in the selected coset, apply the generators of \(G_H\), range over \(K\), and invert CRT. This is a uniform finite decoder. It does not need the smallest numerical bitstring of the chain. Efficient indexing or minimum-finding is a separate computational question.

Multiplication by \(U_H\) acts transitively on this stratum’s chain family, with stabilizer \(G_H\). It also preserves the graph structure: the map from one core coset to another commutes with rotation and linking, while leaving the \(K\)-coordinate unchanged. This explains the algebraic operation that replaces a stored list of chainreps.

### 5. Derive the complete graph shape

Counts alone would not prove that the graph types are correct. We now derive their actual directed-graph isomorphism types for every \(q\), including higher repeated-factor cases.

Fix \(H\), abbreviate \(d=d_H\), \(t=t_H\), and set

\[
h=\gcd(d,q).
\]

Because \(d\mid n\), \(h\) is the power-of-two part of \(d\), and divides \(q\). Put \(y=1+x\), so that

\[
K=\mathbb F_2[y]/y^q,\qquad R_K=1+y,\qquad L_K=y.
\]

#### 5.1 Normalize core rotations

Choose a formal origin for the core coset for purposes of this proof. Its core states can be uniquely written

\[
x^a(1+x)^i u,\qquad 0\le a<d,\quad 0\le i<t.
\]

Normalizing \(a\) by rotation leaves an ambiguity of rotations by multiples of \(d\) on \(K\). Hence the bitloop vertices of this chain are

\[
\bigl(K/\langle R_K^d\rangle\bigr)\times\mathbb Z/t\mathbb Z.
\tag{9}
\]

The rotation \(R_K\) has order \(q\), so \(\langle R_K^d\rangle=\langle R_K^h\rangle\).

There can appear to be a twist at the end of the cycle. Choose \(r\) with \((1+x)^t=x^r\pmod H\). In (9), linking is

\[
([a],i)\longmapsto
\begin{cases}
([ya],i+1),&i<t-1,\\
([R_K^{-r}ya],0),&i=t-1.
\end{cases}
\tag{10}
\]

#### 5.2 The apparent twist introduces no new graph invariant

Define the nilpotent height \(j(a)=\min\{j\ge0:y^ja=0\}\). Height is rotation-invariant; for \(a\ne0\), linking reduces it by exactly one.

Set \(c_i=0\) except \(c_{t-1}=-r\). Define integer exponents recursively by

\[
e(i,0)=0,\qquad e(i,j)=c_i+e(i+1\bmod t,j-1).
\]

The bijection

\[
([a],i)\longmapsto([R_K^{e(i,j(a))}a],i)
\]

conjugates (10) to the untwisted map

\[
([a],i)\longmapsto([ya],i+1\bmod t).
\tag{11}
\]

To check this, for a nonzero vertex substitute \(j(ya)=j(a)-1\); the recursive identity makes the powers of \(R_K\) on the two sides equal. At zero, every rotation fixes the coordinate. The map is invertible on each height and phase, so this is a graph isomorphism, not merely an equality of counts.

The zero coordinates form a cycle of length \(t\). A vertex of height \(j\) in phase \(i\) first reaches cycle position \(i+j\pmod t\). Consequently the graph is a \(t\)-cycle with an identical rooted tree attached at each cycle vertex. That rooted tree is the quotient

\[
T_{q,h}=K/\langle R_K^h\rangle
\]

with nonroot edge \([a]\to[ya]\). Its root’s self-edge is omitted from the tree and replaced by the cycle edge in the full graph.

#### 5.3 Derive every branching number

At height \(j\ge1\), the elements of \(K\) are \(y^{q-j}u\), where \(u\) is a unit modulo \(y^j\). There are \(2^{j-1}\) such elements. Their orbits under \(R_K^h=1+y^h\) all have length

\[
\rho_h(j)=\min\{2^a:a\ge0,\ h2^a\ge j\}.
\tag{12}
\]

This follows from \((1+y^h)^{2^a}=1+y^{h2^a}\); this power fixes a height-\(j\) element exactly when \(h2^a\ge j\). The acting group has power-of-two order, so these tests find its orbit length.

Each nonzero height-\(j\) orbit, for \(j<q\), has \(2\rho_h(j)\) preimage elements at height \(j+1\). Every orbit there has length \(\rho_h(j+1)\). Thus **every** vertex at height \(j\) has exactly

\[
b_j=\frac{2\rho_h(j)}{\rho_h(j+1)}
=\begin{cases}
1,&j\text{ is a power of two and }j\ge h,\\
2,&\text{otherwise}
\end{cases}
\tag{13}
\]

children. At height \(q\), vertices are leaves. The root has one nonroot child: the unique nonzero element of \(\ker y\), which is fixed by rotation.

All vertices at the same depth therefore have the same number of children. These branching numbers determine the rooted tree up to isomorphism by induction from its leaves. This establishes the full topology, not just a depth histogram.

In the calculator’s convention the cycle vertex has indegree two: its cycle predecessor and its one transient predecessor. Accordingly the exact signature is

\[
\sigma(q,h)=2\,b_1b_2\cdots b_{q-1}\,0.
\tag{14}
\]

The graph type is precisely

\[
\boxed{\Gamma_H=G\{t_H\}\text{-}\{\sigma(q,h_H)\}.}
\tag{15}
\]

Different \(H\) can produce the same graph type. The number of actual chains of a type \(\Gamma\) is consequently

\[
\boxed{M_\Gamma=\sum_{H:\Gamma_H=\Gamma}A_H.}
\tag{16}
\]

Together with (8), the union of the corresponding coset families proves Lemma 3. The input \(n\) and graph type determine the entire family; one representative chain is optional illustration.

### 6. Prove coverage, without relying on a matching total alone

Every original word has one CRT pair. Its \(W\)-coordinate has one annihilator \(H\), one unit coordinate in (3), and one coset in \(U_H/G_H\). Therefore it belongs to **exactly one** set \(\mathcal C_{H,c}\) in (8).

This establishes both exhaustiveness and disjointness before any summation. It excludes the possibility that missing words are concealed by duplicated ones.

The numerical coverage certificate then follows:

\[
\sum_{H\mid P}\Phi(H)=|W|=2^{n-q},
\]

and hence

\[
\boxed{
\sum_{H\mid P} A_H B_H
=\sum_{H\mid P}\frac{\Phi(H)}{d_Ht_H}\,2^qd_Ht_H
=2^n.
}
\tag{17}
\]

There is also a direct factorization check. For an irreducible \(f\) of degree \(r\),

\[
1+\sum_{e=1}^q\Phi(f^e)
=1+\sum_{e=1}^q\bigl(2^{re}-2^{r(e-1)}\bigr)
=2^{rq}.
\]

Multiplying over the irreducible factors of \(P\) gives the same \(2^{n-q}\) identity.

**The coverage argument is therefore a disjoint-partition theorem plus exact arithmetic. The chainrep list is not a premise.**

### 7. Recover bitloop and factor counts as well

Let \(e\) run through \(1,2,4,\ldots,q\). The number of \(K\)-coordinates of exact rotation period \(e\) is

\[
c(1)=2,\qquad c(e)=2^e-2^{e/2}\quad(e>1).
\]

For these powers of two, \(R_K^e-I\) is multiplication by \(y^e\), so it has \(2^e\) fixed elements. Subtracting the \(e/2\)-periodic elements proves the formula.

Every core coordinate in a stratum has period \(d_H\). A pair with periods \(e\) and \(d_H\) has period \(\operatorname{lcm}(e,d_H)\), because rotation fixes the pair exactly when it fixes both coordinates. Thus per actual chain,

\[
\begin{aligned}
\text{bitstrings}\quad B_H&=2^q d_Ht_H,\\
\text{bitloops}\quad N_H&=\sum_{e\mid q}\frac{d_Ht_Hc(e)}{\operatorname{lcm}(d_H,e)},\\
\text{full-period bitloops}\quad F_H^{\rm count}
&=\sum_{\substack{e\mid q\\\operatorname{lcm}(d_H,e)=n}}
\frac{d_Ht_Hc(e)}{n}.
\end{aligned}
\tag{18}
\]

The last quantity is the calculator’s `factors` count; it is distinct from polynomial factorization. Since \(q\) is a power of two, its positive divisors are exactly the values of \(e\) just listed.

Independently, the tree formula gives

\[
N_H=t_H\left(1+\sum_{j=1}^q\frac{2^{j-1}}{\rho_{h_H}(j)}\right).
\tag{19}
\]

These formulas count complete chains without traversing their bitloops.

**Retain \(d_H\) when combining graph types.** The topology only uses its power-of-two part \(h_H\), whereas bitstring masses can depend on the entire \(d_H\). Equal graph names need not mean equal numbers of bitstrings per chain.

### 8. A finite computation that does not enumerate chains

The theorem is effective. The following procedure computes its descriptors and counts.

1. Compute \(q,m,P\), and factor the squarefree polynomial \((x^m+1)/(x+1)\) into irreducibles \(f_1,\ldots,f_r\).
2. Visit each exponent tuple \((e_1,\ldots,e_r)\in\{0,\ldots,q\}^r\), defining \(H=\prod f_i^{e_i}\).
3. Compute \(\Phi(H)\), \(d_H\), and \(t_H\) by exact polynomial and integer arithmetic.
4. Compute (6), (7), (14), and (18); add the stratum’s multiplicity to its graph type.
5. Retain the formal family \(U_H/\langle x,1+x\rangle\) and decoder (8), and verify the coverage identities.

Here is one explicit way to perform step 3 without building all of \(U_H\) or \(G_H\). The order \(d_H\) divides \(n\), so it can be found by modular-power tests on divisors of \(n\). The order \(a_H=\operatorname{ord}_H(1+x)\) divides \(\Phi(H)\) and can be found by prime-divisor reductions of that bound.

To find \(t_H\), start with \(a_H\) and remove prime factors whenever

\[
(1+x)^{t_H/p}\bmod H\in\langle x\bmod H\rangle.
\]

This membership test compares with at most \(d_H\le n\) rotation powers. Prime reduction gives the exact order in the quotient group. All these residues describe operators modulo an annihilator, not a catalogue of original bitstrings or one word per chain.

There are \((q+1)^r\) divisor strata. That number can be much smaller than the number of chains. No field-log table, minimum-representative store, visited-state bitmap, or list of cosets is required for this census. Factorization and order computations can nevertheless become difficult, and the stratum count can itself grow. This avoids bitstring and chain enumeration; it is not a universal efficiency guarantee.

### 9. What the theorem does and does not establish

The theorem establishes exact graph topology, exact actual-chain multiplicity, exact word/bitloop accounting, and a uniform symbolic description of membership. It establishes these for arbitrary positive \(n\), without assuming the patterns observed at smaller \(n\) continue.

It does not automatically reproduce the old numerical ordering of chainreps, their minimum bitstrings, or a symmetry flag defined by such a chosen minimum. Those are additional choices. Reversal is an optional involution on the chain family, not needed for the partition proof. Its treatment is discussed in the companion document.

The proof is a mathematical argument, not a machine-checked formalization. Small exhaustive checks and agreement with existing data can test an implementation; they do not replace the proof, and the proof does not certify an unchecked program.

### Mathematical context

The algebraic treatment of binary adjacent-difference dynamics has precedent. Breuer, Lötter, and van der Merwe relate Ducci periods to polynomial and finite-field orders in [*Ducci-sequences and cyclotomic polynomials*](https://doi.org/10.1016/j.ffa.2005.11.003), *Finite Fields and Their Applications* 13 (2007), 293–304. Bors discusses nilpotent/periodic decomposition for finite-group endomorphism graphs in [*On the dynamics of endomorphisms of finite groups*](https://arxiv.org/abs/1409.3756).

These are background references, not a claim that either paper states this exact rotation-quotient catalogue theorem. The chain-coset correspondence, removal of the rotation twist, branching calculation, and coverage argument needed here are supplied explicitly above. No novelty claim is made.


<a id="compressed-census"></a>

## Exact compression of the graph census

> The compression theorem introduced in iteration 2.2 is retained in the version-2 release. See the current README for the supported range and integer-proof implementation.


Version 2 supports every integer width \(1\le n\le1024\). Its census uses weighted relation lattices instead of enumerating the annihilator divisors used by version 2.1. This document proves that the compression preserves the complete graph census and its exact accounting. The underlying partition theorem remains [v2-proof.md](#partition-proof).

The argument is mathematical; it does not imply a uniform runtime bound for larger ranges. The implementation and certificate format are deliberately limited to the version's supported range.

### 1. The partition being counted

Represent a binary word by a polynomial modulo \(x^n+1\) over \(\mathbb F_2\). Rotation multiplies by \(x\), and the adjacent-XOR link multiplies by \(1+x\). Write

\[
n=qm,\qquad q=2^{v_2(n)},\qquad m\text{ odd},
\]

and define

\[
Q=\frac{x^m+1}{x+1},\qquad P=Q^q
  =\frac{x^n+1}{(x+1)^q}.
\]

The Chinese remainder theorem separates the transient coordinate
\(K=\mathbb F_2[x]/((x+1)^q)\), with \(|K|=2^q\), from the periodic coordinate \(W=\mathbb F_2[x]/P\). The polynomial \(Q\) is squarefree. Neither \(x\) nor \(x+1\) divides it.

For every monic divisor \(H\mid P\), let

\[
U_H=(\mathbb F_2[x]/H)^\times,\qquad
G_H=\langle x,1+x\rangle\subseteq U_H.
\]

An actual chain, meaning one connected component of the bitloop functional graph, corresponds to exactly one coset in exactly one family \(U_H/G_H\). If \(c\) is that coset, its words are the inverse CRT image of

\[
K\times\{(P/H)u\pmod P:u\in c\}.
\]

The families are disjoint and exhaustive because each periodic coordinate has one exact annihilator and one coset. This is the set-level partition proof; matching a numerical total is an additional check, not its replacement.

The aim of compression is to count and describe all these families without storing one record for each \(H\).

### 2. A canonical relation lattice

Fix \(H\). Define the group homomorphism

\[
\psi_H:\mathbb Z^2\longrightarrow U_H,
\qquad (a,b)\longmapsto x^a(1+x)^b\pmod H.
\]

Negative exponents are legitimate because both residues are units. Its kernel is the relation lattice \(\Lambda_H\), and its image is \(G_H\).

Let

\[
d=\operatorname{ord}_H(x),\qquad
t=\operatorname{ord}_{U_H/\langle x\rangle}((1+x)\langle x\rangle).
\]

There is a unique \(s\in\{0,\ldots,d-1\}\) satisfying

\[
(1+x)^t=x^s\pmod H.
\]

Then the entire kernel, not just two of its relations, is

\[
\boxed{\Lambda(d,t,s)=\langle(d,0),(-s,t)\rangle_{\mathbb Z}.}
\tag{1}
\]

Indeed, if \((a,b)\) is a relation, the definition of the quotient order gives \(b=kt\) for some integer \(k\). The relation then says \(x^{a+ks}=1\), so \(a+ks\) is a multiple of \(d\). Conversely, each integer combination of the two displayed generators is a relation.

Thus the normalized triple \((d,t,s)\) determines the kernel uniquely. Its index is \(dt\), the absolute determinant of these generators, and therefore

\[
|G_H|=dt.
\tag{2}
\]

The ordinary link order \(a_H=\operatorname{ord}_H(1+x)\) can also be recovered:

\[
\boxed{a_H=\frac{td}{\gcd(d,s)}.}
\tag{3}
\]

Every exponent giving \((1+x)^b=1\) must be a multiple \(b=kt\). The smallest positive such \(k\) has \(d\mid ks\), giving (3). In particular, retaining a separate ordinary link order in a final merged state is unnecessary.

For the trivial annihilator \(H=1\), set \(d=t=1\), \(s=0\), \(\Phi(H)=1\). Its lattice is all of \(\mathbb Z^2\). The associated periodic coordinate is zero. These conventions make the formulas work without enumerating even that word.

### 3. Local data for each irreducible factor power

Factor \(Q=\prod_{i=1}^r f_i\), where the distinct irreducible factors have degrees \(r_i\). An annihilator has the unique form

\[
H=\prod_{i=1}^r f_i^{e_i},\qquad 0\le e_i\le q.
\]

For each factor, compute only its \(q\) nonzero choices \(f_i^e\), together with the implicit choice \(e=0\). Their unit counts are

\[
w_i(0)=1,\qquad
w_i(e)=\Phi(f_i^e)=2^{r_i(e-1)}(2^{r_i}-1)\quad(e\ge1).
\tag{4}
\]

For a nonzero choice, exact polynomial arithmetic determines its triple \((d_i,t_i,s_i)\). The rotation order divides \(n\). The ordinary link order divides

\[
q(2^{r_i}-1).
\tag{5}
\]

To see the latter bound, reduction modulo \(f_i\) gives a nonzero field element, whose order divides \(2^{r_i}-1\). Raising to that order leaves a unit of the form \(1+f_i z\). Raising this to \(q\), a power of two at least \(e\), gives \(1+f_i^qz^q=1\pmod{f_i^e}\).

Orders can therefore be established by a verified bound and successive prime-factor reductions, with exact modular-power tests. The quotient order \(t_i\) and its shift are determined by testing membership in \(\langle x\rangle\), which contains only \(d_i\le n\) rotation operators. These operator residues are not chain representatives or a listing of original words.

All order bounds and their prime factorizations must be checked exactly. A probable-prime test alone is insufficient as a final certificate for an integer outside the proven range of that test.

### 4. Intersect two relation lattices

For coprime polynomials \(A,B\), CRT gives

\[
\Lambda_{AB}=\Lambda_A\cap\Lambda_B.
\tag{6}
\]

A relation holds modulo \(AB\) exactly when it holds modulo both factors. Equation (6) also makes the compression associative: factors may be processed in a fixed order without losing any relation.

Here is the exact normalized intersection formula. Suppose the two triples are \((d_1,t_1,s_1)\) and \((d_2,t_2,s_2)\). Put

\[
T=\operatorname{lcm}(t_1,t_2),\qquad g=\gcd(d_1,d_2),
\]

\[
\Delta=\frac{T}{t_1}s_1-\frac{T}{t_2}s_2\pmod g,
\qquad k=\frac{g}{\gcd(g,\Delta)}.
\]

Then

\[
\boxed{
d=\operatorname{lcm}(d_1,d_2),\qquad t=Tk,
\qquad s\equiv \frac{t}{t_i}s_i\pmod{d_i}\ (i=1,2),
\quad 0\le s<d.
}
\tag{7}
\]

The two congruences for \(s\) have a unique solution modulo \(d\), obtained by generalized CRT.

**Proof of minimality.** A relation with second coordinate \(b\) in the intersection must have both \(t_1\mid b\) and \(t_2\mid b\); write \(b=Tu\). Its first coordinate must satisfy both local rotation congruences. Their compatibility is exactly \(u\Delta=0\pmod g\). The smallest positive compatible \(u\) is \(k=g/\gcd(g,\Delta)\). Thus \(t=Tk\) is the smallest positive second coordinate in the intersection. The relations with second coordinate zero have first coordinate divisible by both \(d_i\), hence by \(d\). Section 2 then proves that (7) is the complete normalized lattice. ∎

The conventions include \(g=1\), \(\Delta=0\), and \(\gcd(g,0)=g\). No exceptional CRT search over a large interval is needed: \(d\mid n\le1024\), even when \(t\) is a large integer.

#### Why a graph name or two orders cannot replace the full relation

The compatibility term \(\Delta\) depends on the shifts. Discarding them before combining factors loses information.

For an actual example, at \(n=7\) the two irreducible factors of the periodic core are

\[
f=x^3+x+1,\qquad g=x^3+x^2+1.
\]

Both have rotation order \(7\) and quotient link order \(1\). Modulo \(f\), \(1+x=x^3\), so its triple is \((7,1,3)\). Modulo \(g\), \(1+x=x^5\), so its triple is \((7,1,5)\). Each individually gives the graph type `G1-20`.

Their intersection has \(T=1\), \(\Delta=-2\pmod7\), and \(k=7\), yielding \((7,7,0)\). The combined annihilator therefore gives `G7-20`. In particular, taking the least common multiple of the two quotient link orders would give the wrong answer. The phase relationship between the operators is essential during composition, even though it disappears from the final graph topology.

### 5. Weighted dynamic programming is exact

After processing the first \(j\) irreducible factors, define a map from normalized lattices to positive integer weights:

\[
W_j(\Lambda)=
\sum_{\substack{0\le e_1,\ldots,e_j\le q\\
\bigcap_{i=1}^j\Lambda_{f_i^{e_i}}=\Lambda}}
\prod_{i=1}^j w_i(e_i).
\tag{8}
\]

Initially \(W_0(\mathbb Z^2)=1\). To add factor \(f_{j+1}\), visit each current state and each of this factor's \(q+1\) choices, form their intersection using (7), and add

\[
W_j(\Lambda)\,w_{j+1}(e)
\]

to that destination state. If several contributions have the same normalized triple, add their weights immediately.

Equation (8) follows by induction: every exponent choice has one prefix and one final exponent, the product of its unit counts is its weight by CRT, and (6) gives its new relation lattice. Every choice contributes once. Merging equal triples is valid because their future intersections depend only on that triple, and multiplication distributes over the sum of their weights.

At the end,

\[
\boxed{W(\Lambda)=\sum_{H:\Lambda_H=\Lambda}\Phi(H).}
\tag{9}
\]

This recurrence does not visit all \((q+1)^r\) tuples. It visits the distinct intermediate states and the local choices. Its certificate stores the local choices and final weighted states; an independent verifier can reconstruct every intermediate map from those inputs.

The exponent tuples remain an implicit, precisely defined family. Compression changes their representation and summation, not the partition theorem. There is no claim that the number of distinct relation states stays small for arbitrarily large \(n\).

### 6. Recover graphs and all counts from a merged state

Let a final state be \((d,t,s)\) with weight \(W\). Every underlying stratum has the same group order \(dt\). Its accumulated actual-chain count is therefore

\[
\boxed{A=\frac{W}{dt}.}
\tag{10}
\]

This division is exact: each individual \(\Phi(H)\) in (9) is divisible by \(dt\), since the group acts freely on \(U_H\). Every chain represented by this state has the same word count

\[
\boxed{B=2^qdt.}
\tag{11}
\]

To derive its graph shape, let \(h=\gcd(d,q)\), which is the power-of-two part of \(d\). The tree attached to each cycle vertex has maximum depth \(q\). Its signature is

\[
\sigma=2b_1b_2\cdots b_{q-1}0,
\qquad
b_j=\begin{cases}
1,&j\text{ is a power of two and }j\ge h,\\
2,&\text{otherwise}.
\end{cases}
\tag{12}
\]

The graph name is `G` followed by \(t\), a hyphen, and \(\sigma\). The leading 2 counts the cycle predecessor and the unique transient predecessor. The proof in [v2-proof.md](#partition-proof), Section 5, shows that the shift \(s\) can be removed by a graph isomorphism organized by nilpotent height. Thus it is needed for exact composition but is not an additional graph invariant.

For \(e\in\{1,2,4,\ldots,q\}\), define

\[
c(1)=2,\qquad c(e)=2^e-2^{e/2}\quad(e>1).
\]

These are the numbers of transient coordinates of exact rotation period \(e\). Consequently the per-chain bitloop and full-period-bitloop counts are

\[
N=\sum_{e\mid q}\frac{dt\,c(e)}{\operatorname{lcm}(d,e)},
\qquad
F=\sum_{\substack{e\mid q\\\operatorname{lcm}(d,e)=n}}
\frac{dt\,c(e)}{n}.
\tag{13}
\]

Here `factors` in the CSV output means \(F\), the full-period-bitloop count, not a number of irreducible polynomial factors.

The merged state contributes \(AB\) words, \(AN\) bitloops, and \(AF\) full-period bitloops. Only after computing these quantities should states be grouped by graph name. The full odd part of \(d\) affects word mass, even though the tree depends only on \(h\). Distinct states with the same graph name can therefore have different word masses per chain.

#### Repeated factors and powers of two

The exponents \(e_i\) must not be reduced to a present/absent flag when \(q>1\). Repeated factors change the local relations and weights. Likewise, the two-part of the rotation order is retained through \(d\) and determines \(h\) in (12).

If \(n\) itself is a power of two, then \(P=1\), there are no irreducible factors, and the initial state is already the final state. It has \((d,t,s,W)=(1,1,0,1)\): one actual chain with \(2^n\) words. Formula (12) still gives its full tree. In particular, \(n=1024\) does not require a special enumeration or prediction.

### 7. Certificate checks and integer representation

For each \(n\), independent verification can establish:

1. The stated irreducible factors are distinct, irreducible, and multiply to \(Q\); their stated powers multiply to \(P\).
2. Every local unit count, ordinary order, quotient order, and rotation shift is exact.
3. The weighted recurrence produces exactly the stated final states, with no missing or additional states.
4. Each final state has the claimed integral chain count, graph signature, and per-chain masses.
5. The final CSV rows are the exact weighted sums over these states.

The factorwise identity

\[
1+\sum_{e=1}^q\Phi(f_i^e)=2^{qr_i}
\]

also gives

\[
\sum_\Lambda W(\Lambda)=2^{n-q},\qquad
\sum_\Lambda A_\Lambda B_\Lambda=2^n.
\tag{14}
\]

Independent rotation formulas provide two more checks:

\[
\sum_\Lambda A_\Lambda N_\Lambda
=\frac1n\sum_{d\mid n}\varphi(d)2^{n/d},
\qquad
\sum_\Lambda A_\Lambda F_\Lambda
=\frac1n\sum_{d\mid n}\mu(d)2^{n/d}.
\tag{15}
\]

The arithmetic must not silently overflow. Polynomial coefficient vectors, potentially large link orders and cycle lengths, weights, chain counts, and word/bitloop totals use exact arbitrary-precision integers. Rotation orders, shifts, depths, and factor exponents are small because they are bounded by \(n\le1024\), but they are converted to exact integers before multiplication by large quantities. For example, the word count at \(n=1024\) is exactly \(2^{1024}\), not a signed 64-bit integer or a floating-point approximation.

The final certificate supplies a checkable compressed calculation of a partition already justified at set level. It does not supply a list of chains, and it does not need one.


<a id="integer-certificates"></a>

## Exact integer order bounds in version 2

The calculator and Python verifier use exact, independently checked prime
factorizations to determine multiplicative orders. Neither accepts a
probable-prime result as a proof. No factoring service or network connection is
needed at runtime.

### Finite coverage

For an irreducible polynomial of degree \(d\), and a local power at most the
power-of-two part \(q\) of \(n\), an order bound is

\[
q(2^d-1).
\]

The required degrees through \(n=1024\) are exactly the multiplicative orders
\(\operatorname{ord}_m(2)\) for odd \(3\le m\le1023\). Every nontrivial
cyclotomic factor arises in this set; the factor \(x+1\) has already been
removed. The two implementations independently derive this set when checking
the supplied integer data. It contains 215 degrees, with maximum 1018:

```text
2,3,4,5,6,7,8,9,10,11,12,14,15,16,18,20,21,22,23,24,25,28,29,30,33,35,36,
37,39,40,42,43,44,45,46,48,50,51,52,54,55,56,58,60,64,66,68,69,70,72,73,
74,76,78,82,83,84,88,90,91,92,94,95,96,99,100,102,104,105,106,108,110,
114,116,117,119,121,126,130,131,132,135,136,138,140,144,147,148,153,154,
155,156,162,164,166,168,172,174,178,179,180,183,184,190,191,194,196,198,
200,204,210,212,214,220,224,226,230,231,232,238,239,243,244,246,251,252,
253,260,262,268,270,276,284,290,292,299,300,303,308,310,316,318,323,324,
330,332,340,342,346,348,356,359,371,372,375,378,380,384,388,390,396,404,
410,411,414,418,419,420,428,431,442,443,460,464,466,468,483,486,488,490,
491,495,500,504,508,522,540,546,556,562,586,612,618,652,658,660,676,700,
708,756,772,786,796,812,820,826,828,852,858,876,882,906,940,946,1018
```

`order-factors.json` includes complete prime factorizations of \(2^d-1\) for
each of these degrees. Both implementations check every supplied factor for
primality and multiply the factors, including repetitions, to recover the
exact bound. Multiplication by \(q\) adds only the already proved prime 2.
The dataset contains 951 distinct order-bound primes. Of these, 184 exceed
the 64-bit primality routine's range; the largest has 388 bits.

### Primality proofs

For integers smaller than \(2^{64}\), deterministic Miller–Rabin uses bases
2, 325, 9375, 28178, 450775, 9780504 and 1795265022. That routine explicitly
rejects wider inputs. It is never extrapolated to arbitrary precision.

For wider integers the dataset includes 301 Pocklington certificates: the
184 order-bound primes and 117 additional primes needed to prove them
recursively. Including the smaller factors used in these proofs, the complete
dataset proves 1,546 distinct primes.
For a candidate \(p\), its certificate supplies a factored integer
\(F\mid p-1\) with \(F^2>p\), and a witness \(a\) such that

\[
a^{p-1}\equiv1\pmod p,
\qquad
\gcd\bigl(a^{(p-1)/r}-1,p\bigr)=1
\quad\text{for every prime }r\mid F.
\]

These conditions prove that \(p\) is prime. To see why, take any prime
divisor \(\ell\) of \(p\). The first congruence makes the order of \(a\)
modulo \(\ell\) divide \(p-1\). Each gcd condition forces that order to
contain the full power of \(r\) dividing \(p-1\), so in particular
\(F\mid\ell-1\). Thus every prime divisor of \(p\) exceeds
\(\sqrt p\), which is impossible for a composite integer.

Ten supplied certificates use only a partial factorization of \(p-1\); the
other 291 use the complete factorization. A partial certificate demonstrates
that the unused cofactor need not itself be proved prime. One example uses

\[
\begin{aligned}
p&=1729586057112292441473210838016372059864829552367799,\\
F&=76862122612744357228952527938,\\
a&=3,
\end{aligned}
\]

where

\[
F=2\cdot3^2\cdot11\cdot17\cdot131\cdot445789\cdot1147621
  \cdot340721180537,
\]

and

\[
p-1=F\cdot22502449819483819230971,\qquad F^2>p.
\]

Every displayed prime factor of \(F\) is below \(2^{64}\). The remaining
cofactor is unused in the proof; it is not treated as prime. Other certificates
use recursive proofs for larger factors, requiring each factor to be strictly
smaller than its parent. Unknown primes, insufficient factored products,
incorrect witnesses, malformed data and incomplete degree coverage cause
verification to fail.

### Data and implementation

The JSON has exactly three top-level fields:

- `schema_version`: the string `"1"` for this auxiliary data format.
- `mersenne_factors`: degree keys mapped to numerically sorted decimal prime
  strings, repeated according to multiplicity.
- `prime_certificates`: decimal prime keys mapped to `factors` and `witness`.
  Each factor entry is `["prime", exponent]`, with distinct sorted primes and
  positive integer exponents. Witnesses are decimal strings.

`ExactInteger.verifyFactorData` verifies the entire dataset on first use.
`verify_output.py` implements the corresponding checks independently in Python.
All proofs are checked, even if a particular calculation does not use them.
Order calculations subsequently divide their candidate bounds by these proved
prime factors and test the resulting polynomial powers. A complete bound
factorization is essential to proving that the reported order is minimal.
Integer certificate values are bounded below \(2^{1024}\), encoded as canonical
positive decimal strings with at most 309 digits. Exponents are bounded by
1023, and the required degree set is checked explicitly.

`OrderFactorData.java` embeds the same JSON so both the executable JAR and a
plain `javac -d build *.java` build work without copying resource files. To
regenerate the embedded source after editing the JSON:

```sh
python3 tools/embed_order_factors.py
```

The generated source joins bounded text blocks at runtime. Each block is well
below Java's 65,535-byte constant-pool limit; the concatenation is not a folded
compile-time string constant. The acceptance tests compare the embedded data
with the JSON and test rejection of damaged factors and primality witnesses
in both languages.

### Provenance

The initial factor candidates were extracted from Samuel S. Wagstaff Jr.'s
[Cunningham Project main tables, January 5, 2026](https://homes.cerias.purdue.edu/~ssw/cun/pmain126.txt),
specifically the base-2 minus, plus and Aurifeuillean tables. The
[project index](https://homes.cerias.purdue.edu/~ssw/cun/) describes the source.
Some table entries abbreviate a final prime as `P` followed by its decimal
length. Those integer values were recovered by exact division of the
corresponding cyclotomic values. Their published status is not trusted by the
calculator: complete products and primality proofs are rechecked locally.

The factorizations of \(p-1\) and their witnesses were generated during
development. Candidates for difficult recursive factorizations were obtained
from [FactorDB](https://factordb.com/), accessed October 8, 2026. Its prime and
composite status labels are not accepted as evidence. Every candidate split
was checked by exact multiplication, and each factor used as a prime is
proved by the deterministic checks or recursive Pocklington certificates.
The development cache contains 36 such factor queries. Small remaining
composite factors were split locally during development.
Only the resulting finite certificates are included in the release.

Development primality screens were only candidate filters. The shipped
proofs discharge every primality obligation using deterministic 64-bit checks
or the Pocklington conditions above. No development factoring package is a
dependency of either the calculator or its verifier.

This auxiliary dataset covers version 2's finite range. A future increase
must derive its new degree set and provide complete proved factorizations for
any additional order bounds; changing the input limit alone is insufficient.


<a id="certificate-examples"></a>

## Partition certificates and examples

This document explains the partition certificate used by version 2. The formulas describe individual annihilator strata; the implementation combines strata with identical relations by the exact method in [compressed-census.md](#compressed-census). For file schemas and commands, see [OUTPUT.md](OUTPUT.md) and [README.md](README.md).

### The change in what constitutes a complete result

The proof in [v2-proof.md](#partition-proof) supports the transition to a calculator whose primary result is a graph catalogue plus an algebraic certificate, rather than a list of chainreps.

The essential statement is

\[
\{\text{actual chains at width }n\}
\longleftrightarrow
\bigsqcup_{H\mid P}
\frac{(\mathbb F_2[x]/H)^\times}{\langle x,1+x\rangle},
\qquad
P=\frac{x^n+1}{(x+1)^q},\quad q=2^{v_2(n)}.
\]

The right side describes all chains, including which bitstrings belong to each, without choosing a minimum bitstring from every chain. Its disjointness and exhaustiveness are proved, rather than inferred from a numerical coincidence.

This extends the reconstruction principle behind version 1:

| Level | Compact information | Uniform reconstruction rule |
|---|---|---|
| Bitstrings in a bitloop | One word, or a symbolic rotation class | Cyclic rotation |
| Bitloops in an actual chain | One bitloop, or a symbolic component label | Links and inverse links |
| Chains in an annihilator stratum | Polynomial \(H\) and quotient \(U_H/\langle x,1+x\rangle\) | Unit multiplication and CRT reconstruction |
| All chains of a graph type | \(n\), the type, and all matching annihilator strata | Union of their disjoint coset families |

The third level does require additional algebra. One cannot reach a different chain just by repeatedly linking the first chain. But one also does not need to discover a seed representative for each new chain: the quotient-group description supplies the whole family.

The computation need not materialize even one coset per chain. A quotient group can remain a formula; its cardinality follows from the orders of its groups. Expanding a selected chain is an optional later operation.

### What replaces the chainrep file

The version-2 result has two related parts: a graph catalogue and an algebraic partition certificate. The following describes their mathematical contents. The serialized certificate stores local factor data and weighted relation states, which determine the stratum families below without listing every stratum.

#### A graph catalogue

For each graph type, record:

- Cycle order and tree signature, which together specify the complete directed topology.
- Number of **actual chains** of that type.
- Bitloops per chain, and total bitloops of that type.
- Total original bitstrings and total full-period bitloops of that type.

Actual-chain count is not the old reversal-paired CSV row count. If a version-1 row has multiplicity two, it contributes two actual chains.

#### An algebraic partition certificate

Retain \(n\), \(q\), and a verified irreducible factorization of \(P\). Each divisor stratum \(H\) has the following descriptors:

| Descriptor | Meaning |
|---|---|
| Factor-exponent tuple | Specifies \(H\) using the shared factorization |
| \(\Phi(H)\) | Number of periodic-core coordinates in the stratum |
| \(d_H\) | Core rotation period |
| \(t_H\) | Bitloop cycle length |
| \(A_H=\Phi(H)/(d_Ht_H)\) | Number of actual chains |
| \(\sigma(q,\gcd(d_H,q))\) | Tree signature |
| \(B_H=2^qd_Ht_H\) | Bitstrings per actual chain |
| Bitloops and full-period bitloops per chain | The formulas in Section 7 of the proof |
| \(U_H/\langle x,1+x\rangle\) | Symbolic labels for all those chains |

The final entry is a shared interpretation rule, not a field containing an enormous list. The factor tuple and the two specified generators define the quotient.

Preserving the information needed to distinguish strata is useful even after merging graph types. Equal graph topology can conceal different word masses. At \(n=3\), both actual chains have type `G1-20`, but one accounts for two bitstrings and the other for six. Thus multiplying a graph’s chain count by a single assumed word mass can be wrong.

The certificate can include exact order witnesses. To verify \(d_H\), check \(x^{d_H}=1\pmod H\) and \(x^{d_H/p}\ne1\pmod H\) for each prime divisor \(p\) of \(d_H\). To verify \(t_H\), check that \((1+x)^{t_H}\) belongs to \(\langle x\rangle\), while \((1+x)^{t_H/p}\) does not for any prime divisor \(p\) of \(t_H\). Membership requires at most \(d_H\le n\) rotation powers. Factor primality and polynomial irreducibility must also be verified, rather than trusted merely because a file labels them as such.

The independent verifier checks:

1. The polynomial factorization and every local factor-exponent choice.
2. The unit counts, modular orders, and complete rotation/link relations.
3. The weighted relation-lattice recurrence representing all factor-exponent tuples.
4. The signatures, component multiplicities, per-component masses, and graph aggregation.
5. The bitstring coverage identity and independent necklace counts.

It verifies the supplied certificate against the theorem without reconstructing the chainrep file. The theorem supplies the reason that the declared symbolic families are disjoint; the checks establish that the file correctly instantiates that theorem.

### The \(n=14\) case, including `G2-220`

Here \(q=2\), \(m=7\), and

\[
f=x^3+x+1,\qquad g=x^3+x^2+1,\qquad P=f^2g^2.
\]

There are only nine annihilator strata. Their exact data are:

| \(H\) | \(\Phi(H)\) | \(d_H\) | \(t_H\) | Actual chains \(A_H\) | Words per chain \(B_H\) | Graph type |
|---|---:|---:|---:|---:|---:|---|
| \(1\) | 1 | 1 | 1 | 1 | 4 | `G1-210` |
| \(f\) | 7 | 7 | 1 | 1 | 28 | `G1-210` |
| \(g\) | 7 | 7 | 1 | 1 | 28 | `G1-210` |
| \(fg\) | 49 | 7 | 7 | 1 | 196 | `G7-210` |
| \(f^2\) | 56 | 14 | 2 | 2 | 112 | `G2-220` |
| \(g^2\) | 56 | 14 | 2 | 2 | 112 | `G2-220` |
| \(f^2g\) | 392 | 14 | 14 | 2 | 784 | `G14-220` |
| \(fg^2\) | 392 | 14 | 14 | 2 | 784 | `G14-220` |
| \(f^2g^2\) | 3,136 | 14 | 14 | 16 | 784 | `G14-220` |

For \(H=f^2\), the unit group has 56 elements and the rotation/link subgroup has order \(14\cdot2=28\). Hence there are exactly two cosets, each defining one actual chain. The same argument applies to \(g^2\). These are four actual `G2-220` chains, each with 112 words.

Their existence does not depend on finding four minimum bitstrings. They exist because the two quotient groups each have order two, and the component correspondence is a bijection. The formula for their labelled word sets is already provided by CRT and the relevant coset.

Aggregating gives:

| Graph type | Actual chains | Bitloops per chain | Total bitstrings |
|---|---:|---:|---:|
| `G1-210` | 3 | 3 | 60 |
| `G7-210` | 1 | 21 | 196 |
| `G2-220` | 4 | 8 | 448 |
| `G14-220` | 20 | 56 | 15,680 |
| **Total** | **28** | — | **16,384** |

The total number of bitloops is independently recovered as

\[
3\cdot3+1\cdot21+4\cdot8+20\cdot56=1,182.
\]

In the retained version-1 fixture, the four actual `G2-220` components appear as two reversal-paired rows of multiplicity two. This distinction matters when relating the word “instance” to an old list or hand count; the theorem counts the actual disjoint components.

A missing-representative problem therefore has a different completion criterion in version 2: verify the appropriate quotient-group count and its symbolic component family. The missing sample is no longer required to establish existence or coverage.

### Why this changes the situation above 50

Arithmetic-only evaluation of the census gives the following scale comparison. These are actual component counts before reversal pairing:

| \(n\) | Annihilator strata | Graph types | Actual chains |
|---:|---:|---:|---:|
| 50 | 9 | 5 | 2,751,466,546 |
| 51 | 128 | 5 | 86,574,392,968 |
| 63 | 4,096 | 6 | 1,161,926,434,509,632 |
| 64 | 1 | 1 | 1 |

For \(n=63\), describing six graph types and 4,096 strata does not require printing roughly 581 trillion reversal-paired chainreps. The information omitted is the expanded list of particular representatives, not the mathematical accounting of the power set.

For \(n=64\), the periodic coordinate space is trivial. Every word has only a transient coordinate, and all bitloops feed into one component. That component still has an enormous number of vertices, but its depth and branching pattern are specified by the signature formula. Even explicitly drawing the graph is unnecessary for defining it exactly.

Version 1.6 already contains much of the census arithmetic in `AlgebraicCensus.java`; the later minimum search and CSV generation do substantially more work. Its explicit classifier supports only certain repeated-factor structures, but that limitation is different from the scope of the census theorem. The proof here establishes the graph shape for arbitrary \(q\), including \(q\ge4\).

The mathematical argument has no 50-bit or 64-bit boundary. The implementation uses arbitrary-precision integer and polynomial types and accepts `1 <= n <= 1024`. Its compressed census avoids enumerating the annihilator strata. Extending the supported range would still require verified integer order bounds and testing the polynomial factorization, modular-order computation, and growth of distinct relation states. The theorem does not supply a runtime guarantee for larger ranges.

### Reversal and the meaning of symmetry

The partition theorem treats actual connected components as its fundamental objects. It does not need a reversal quotient.

Reversal normalizes rotation and linking: if \(J\) is reversal, then

\[
JRJ=R^{-1},\qquad JLJ=R^{-1}L.
\]

It therefore permutes actual chains and preserves their graph types. An intrinsic refinement could record the number of self-reversing components and the number of pairs exchanged by reversal. If \(A\) is the actual-chain count and \(S\) is the self-reversing count, the number of reversal orbits is \((A+S)/2\).

This does **not** make \(S\) the old `sym-chains` count. In version 1, the `symmetric` flag tests the selected minimum bitloop. A self-reversing component can have an asymmetric selected representative; the retained \(n=12\) fixture includes an asymmetric `G4-22220` row with multiplicity one.

The scope is therefore:

- **Proved here:** the graph catalogue, actual-chain multiplicities, symbolic partition and complete bitstring accounting.
- **Optional further refinement:** intrinsic reversal counts, with an exact method and proof for the intended range.
- **A different request:** reproducing the old minimum-dependent flags, row order or minimum samples. The present theorem does not establish a fast representative-free method for those conventions.

This distinction allows the new output to describe the mathematical partition directly while retaining precise meaning for any extra symmetry statistics.

### What was checked for these documents

The proof was checked against the version-1.6 definitions of rotation, link, actual components, signatures, multiplicity, and full-period bitloops. It supplies the disjointness and graph-isomorphism arguments explicitly, rather than treating the calculator as proof.

A separate bounded check enumerated all 131,070 words across \(n=1..16\), formed rotation classes and link edges directly, and recovered their connected components. It checked the cycle lengths and the indegree of every vertex at every depth, not just total counts. For every graph type, the actual-chain count, bitstring mass, bitloop count and full-period-bitloop count agreed with the algebraic census.

For the initial \(n=50..64\) examples, the algebraic census was evaluated without chain enumeration; its weighted bitstring totals equalled \(2^n\). The release acceptance suite and current coverage are recorded in [VALIDATION.md](VALIDATION.md). These checks support the arithmetic examples and detect possible implementation discrepancies. They are not the reason the all-\(n\) theorem holds.

The self-contained proof establishes the partition. The executable calculator and independent verifier check its arithmetic instances within the supported range.


<a id="legacy-certificate-format"></a>

## Output contract — version 2.1

This historical schema remains readable for `n <= 64`. New calculations write the current schema described in [OUTPUT.md](OUTPUT.md).

All counts are exact, nonnegative integers. CSV uses UTF-8, a header row, comma separators, and CRLF record endings. JSON uses exact decimal integer literals. Read large counts using arbitrary-precision integers or decimal text; floating-point JSON/CSV import can lose precision above \(2^{53}\). Graph names and signatures are text, including the 65-character signature at `n=64`.

### `powersets.csv`

```csv
n,bitstrings,bitloops,factors,chains,graphs
```

| Column | Meaning |
|---|---|
| `n` | Width, 1..64; primary key |
| `bitstrings` | All original words, exactly \(2^n\) |
| `bitloops` | All cyclic rotation classes of words |
| `factors` | Bitloops whose least rotation period is exactly `n` |
| `chains` | Actual connected components of the link graph |
| `graphs` | Number of distinct directed graph types at this width |

Rows are sorted by `n`. The term `factors` retains its original calculator meaning: full-period bitloops. It does **not** mean the number of irreducible polynomial factors.

### `graphs.csv`

```csv
n,name,chains,bitloops-per-chain,bitstrings,bitloops,factors,cycle-order,tree-depth,signature
```

The primary key is `(n,name)`. Rows are sorted by `n`, then numerical `cycle-order`, then lexical `signature`.

| Column | Meaning |
|---|---|
| `n` | Width of the power set |
| `name` | `G{cycle-order}-{signature}` |
| `chains` | Number of actual chains of this type at this width |
| `bitloops-per-chain` | Number of vertices in each such chain |
| `bitstrings` | Total original words in **all** chains represented by this row |
| `bitloops` | Total bitloops in all those chains |
| `factors` | Total full-period bitloops in all those chains |
| `cycle-order` | Number of bitloops in the directed cycle of each chain |
| `tree-depth` | Maximum distance of a vertex from its cycle; equals \(q=2^{v_2(n)}\) |
| `signature` | Indegrees by distance from the cycle, including the cycle vertex and terminal leaves |

The signature begins with `2`: the cycle predecessor plus one transient predecessor. Its internal digits give the common number of children at each nonzero depth; the final `0` denotes leaves. Together with the cycle length, it specifies the full directed topology. At a cycle of length one, its self-loop supplies the cycle predecessor.

For each `n`, summing the graph rows' `chains`, `bitstrings`, `bitloops`, and `factors` reproduces `powersets.csv`. Every graph row also satisfies

\[
\text{bitloops}=\text{chains}\times\text{bitloops-per-chain}.
\]

Identical graph topology does not imply identical bitstring mass per chain. At `n=3`, the two chains of type `G1-20` account for two and six words. Their combined row records eight words. The certificate retains the separate strata needed to explain this distinction.

### `certificates/{n}.json`

One certificate records the full disjoint partition for its width. The following tables specify all fields; unknown or missing fields are rejected by the verifier.

| Top-level field | Meaning |
|---|---|
| `schema_version` | String `"2.1"` |
| `n` | Width |
| `q` | Largest power of two dividing `n` |
| `core_polynomial` | \(P=(x^n+1)/(x+1)^q\), encoded as a polynomial |
| `irreducible_factors` | Distinct irreducible factors of \(P\), with degree and multiplicity |
| `strata` | One entry for every monic divisor \(H\mid P\), including \(H=1\) |
| `totals` | Object with `bitstrings`, `bitloops`, `factors`, `chains`, and `graphs`, matching the powerset row |

Polynomial values are lowercase hexadecimal strings: bit `i` is the coefficient of \(x^i\). For example, `0xb` denotes \(x^3+x+1\). These are operator polynomials, not selected bitstring representatives. Each factor object has `polynomial`, `degree`, and `multiplicity`; every multiplicity is `q`.

Each stratum has:

| Field | Meaning |
|---|---|
| `annihilator` | The divisor \(H\), in hexadecimal polynomial form |
| `factor_exponents` | Exponents aligned with `irreducible_factors`, each in 0..q |
| `units` | \(\Phi(H)=|(\mathbb F_2[x]/H)^\times|\) |
| `rotation_order` | \(d_H=\operatorname{ord}_H(x)\) |
| `link_order` | \(a_H=\operatorname{ord}_H(1+x)\), before quotienting by rotations |
| `cycle_order` | \(t_H\), the order of \(1+x\) modulo the rotation subgroup |
| `chains` | \(A_H=\Phi(H)/(d_Ht_H)\), actual chains in this stratum |
| `bitstrings` | \(B_H=2^q d_Ht_H\), original words **per actual chain** |
| `bitloops` | Bitloops **per actual chain** |
| `factors` | Full-period bitloops **per actual chain** |
| `name` | Graph name for these chains |
| `signature` | Graph tree signature |

For \(H=1\), the unit group is interpreted as trivial and its unit count and orders are all one. The empty factor list at power-of-two widths therefore gives one valid stratum.

The per-chain quantities in a stratum must be multiplied by `chains` before aggregation. In particular,

\[
\sum_{H\mid P}\text{chains}_H\,\text{bitstrings}_H=2^n.
\]

The shared symbolic interpretation of the chains in a stratum is

\[
U_H/\langle x,1+x\rangle,
\qquad U_H=(\mathbb F_2[x]/H)^\times.
\]

This quotient is defined by the annihilator and the two fixed generators. There is no field containing its list of elements. The correspondence with the original word partition, and reconstruction by the Chinese remainder theorem, are established in [v2-proof.md](#partition-proof).

Strata are stored in lexicographic order of their factor-exponent tuples. No timestamps or run identifiers enter a certificate, so rerunning the same width reproduces identical certificate bytes.

### `log/{n}.log`

Each line is a complete JSON object. Common fields are `time` (UTC ISO instant), `version`, `run_id` (UUID), `n`, `event`, and `elapsed_ns`.

| Event | Additional information |
|---|---|
| `run_start` | Engine, workers, maximum JVM heap bytes, and `representatives: false` |
| `progress` | `phase: "strata"`, `done`, and `total` |
| `census_complete` | Measured strata and exact coverage totals |
| `run_end` | `status`; on success, `output_sha256`; on failure, an error `message` |

Multiple executions append to the same width's log. Filter on `run_id` to recover one run. Successful publication, rather than merely finishing the arithmetic census, determines a successful terminal record.
