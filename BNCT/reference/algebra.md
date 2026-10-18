# Algebraic basis of the calculator

- [Partition proof](#partition-proof)
- [Compressed graph census](#compressed-census)
- [Relation to the Python implementation](#python-implementation)

Binary words are identified with subsets of a labelled finite set. Their rotation classes are binary necklaces. The adjacent-XOR map acts on these classes, and its weakly connected components partition the power set. The proofs below give the component families, their graph shapes, and their exact multiplicities without enumerating component representatives.

Equation numbers restart in each of the two proofs.

<a id="partition-proof"></a>

## A representative-free classification of binary necklace graphs

### Classification theorem

**The binary-necklace graph of the adjacent-XOR map admits a representative-free classification.** For every positive integer \(n\), one can determine all graph types, the exact number of components of each type, and an exact symbolic partition of the \(2^n\) binary words, without enumerating the binary words or finding a representative binary word for each component.

This is a mathematical classification theorem for every positive \(n\). It does not assert that the computation is polynomial-time, that every future implementation will be correct, or that expanding a large catalogue becomes inexpensive.

“Without listing elements” means that the output consists of algebraic descriptors, graph types, and integer counts. Polynomial arithmetic is allowed; listing individual original binary words or choosing one from every component is unnecessary. A finite set can be specified exactly by a formula without printing its members. The proof gives both that formula and a procedure for expanding a selected part on demand.

### 1. Definitions and the three reconstruction lemmas

Let \(V_n=\mathbb F_2^n\), the set of binary words identified with the power set of a fixed labelled \(n\)-element set. Let \(R\) be cyclic rotation by one position and

\[
L=I+R
\]

be the adjacent-XOR operation, also called linking below; addition is XOR. The choice of rotation direction only changes the coordinate convention.

A **binary necklace** is a rotation class \([v]=\{R^iv:0\le i<n\}\). Linking gives a well-defined map on binary necklaces because \(LR=RL\).

The **binary necklace functional graph** has these classes as vertices, with the edge \([v]\to[Lv]\). A **component** means a weakly connected component of this graph: its cycle together with every attached predecessor tree. A **graph type** is the directed-graph isomorphism type of a component, including its cycle and trees but forgetting its binary word labels.

The individual components partition the binary necklaces and, by taking their rotation classes, partition the binary words. Grouping those components by graph type gives a coarser partition. A list of distinct graph names alone is insufficient: multiplicities and binary word accounting matter.

Reversal-related components are counted separately throughout the theorem. Pairing components under reversal does not change the definition of a connected component.

#### Lemma 1: a binary necklace determines its binary words

For a supplied word \(v\), let \(d(v)\) be its least positive rotation period. Its binary necklace consists exactly of

\[
v,Rv,\ldots,R^{d(v)-1}v.
\]

They are distinct by minimality of \(d(v)\), and all other rotations repeat them. Thus a representative and the rotation operation determine the entire binary necklace. Notice that \(d(v)\) may be smaller than \(n\).

#### Lemma 2: any binary necklace in a component determines the component

Starting from any binary necklace in a component, close the set under both forward links and inverse links. This recovers exactly that component.

To compute inverse links, choose the coordinate convention in which \(Lw=v\) means

\[
w_i+w_{i+1}=v_i,\qquad i\pmod n.
\]

Choose \(w_0\), then propagate \(w_{i+1}=w_i+v_i\). Cyclic consistency holds exactly when \(\sum_i v_i=0\). In that case there are two complementary solutions; otherwise there are none. Passing to their rotation classes gives all predecessor binary necklaces: if \(Lw=R^iv\), rotating \(w\) back gives a solution of \(Lw'=v\).

Taking this closure terminates because the graph is finite, and it is precisely the definition of its weakly connected component. An equivalent procedure first finds the eventual cycle and then expands all its predecessors.

**Forward linking alone is insufficient:** it follows one path into a cycle and does not recover every branch. This qualification leaves the intended uniform reconstruction principle intact.

#### Lemma 3, in a stronger form

**Given \(n\) and a graph type, all components of that type have a uniform algebraic parametrization. No seed component is necessary.** Sections 2–7 construct and prove this statement.

The operations generating that family are richer than rotation and linking. Those two operations, even with inverse links, stay within one component. The missing higher-level operation is multiplication in a finite polynomial unit group, together with a classification of the strata that yield the desired graph type.

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

Let \(G=\langle x,1+x\rangle\) act on \(W\). Components correspond bijectively to its orbits \(O\), and the binary words of the corresponding component are exactly the inverse CRT image of

\[
K\times O.
\tag{2}
\]

**Proof.** Every point reaches a point with zero \(K\)-coordinate after at most \(q\) links. Its \(W\)-coordinate remains in the same \(G\)-orbit. Rotation and links cannot join different \(G\)-orbits; neither can inverse links, since linking on \(W\) is invertible.

Within the zero-\(K\) core, taking rotation classes quotients by \(\langle x\rangle\). Linking then traverses exactly one cycle for each \(\langle x,1+x\rangle\)-orbit. Every point of \(K\times O\) feeds into that cycle. Hence (2) is one entire component, and different such sets are disjoint. ∎

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

For \(H=1\), adopt the conventions \(\Phi(1)=1\) and trivial unit/action groups. This is the zero-core stratum, handled without exceptional binary word enumeration.

### 4. Components are unit-group cosets

Define

\[
G_H=\langle x\bmod H,(1+x)\bmod H\rangle\subseteq U_H.
\]

Under (3), its multiplication action is exactly the rotation/link action on the stratum. The action is free: if \(gu=u\) and \(u\) is a unit, cancellation gives \(g=1\). Therefore

\[
\boxed{\quad
\{\text{components at }n\}
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

Then \(d_H\) is the rotation period of every core word in the stratum, and \(t_H\) is its binary necklace cycle length. The quotient \(G_H/\langle x\rangle\) is cyclic, generated by the image of \(1+x\), so

\[
|G_H|=d_Ht_H,
\qquad
\boxed{A_H=\frac{\Phi(H)}{d_Ht_H}}
\tag{6}
\]

is the number of components in that stratum. Each has

\[
\boxed{B_H=2^q d_Ht_H}
\tag{7}
\]

original binary words. For \(H=1\), set \(d_H=t_H=A_H=1\).

#### An exact symbolic decoder

For a formal coset \(c\in U_H/G_H\), define

\[
\mathcal C_{H,c}
=\operatorname{CRT}^{-1}
\left\{(a,F_Hu):a\in K,\ u\in c\right\}.
\tag{8}
\]

This specifies a particular component as a set of original binary words, without listing one. Its binary necklaces are the rotation classes of that set; its edges are supplied by \(L\).

If expansion is requested, one can choose any \(u\) in the selected coset, apply the generators of \(G_H\), range over \(K\), and invert CRT. This is a uniform finite decoder. It does not need the smallest numerical binary word of the component. Efficient indexing or minimum-finding is a separate computational question.

Multiplication by \(U_H\) acts transitively on this stratum’s component family, with stabilizer \(G_H\). It also preserves the graph structure: the map from one core coset to another commutes with rotation and linking, while leaving the \(K\)-coordinate unchanged. This explains the algebraic operation that replaces a stored list of component representatives.

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

Normalizing \(a\) by rotation leaves an ambiguity of rotations by multiples of \(d\) on \(K\). Hence the binary necklace vertices of this component are

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

The cycle vertex has indegree two: its cycle predecessor and its one transient predecessor. Accordingly the exact branching sequence is

\[
\sigma(q,h)=2\,b_1b_2\cdots b_{q-1}\,0.
\tag{14}
\]

The graph type is precisely

\[
\boxed{\Gamma_H=G\{t_H\}\text{-}\{\sigma(q,h_H)\}.}
\tag{15}
\]

Different \(H\) can produce the same graph type. The number of components of a type \(\Gamma\) is consequently

\[
\boxed{M_\Gamma=\sum_{H:\Gamma_H=\Gamma}A_H.}
\tag{16}
\]

Together with (8), the union of the corresponding coset families proves Lemma 3. The input \(n\) and graph type determine the entire family; one representative component is optional illustration.

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

**The coverage argument is therefore a disjoint-partition theorem plus exact arithmetic. A list of component representatives is not a premise.**

### 7. Recover necklace and primitive-necklace counts

Let \(e\) run through \(1,2,4,\ldots,q\). The number of \(K\)-coordinates of exact rotation period \(e\) is

\[
c(1)=2,\qquad c(e)=2^e-2^{e/2}\quad(e>1).
\]

For these powers of two, \(R_K^e-I\) is multiplication by \(y^e\), so it has \(2^e\) fixed elements. Subtracting the \(e/2\)-periodic elements proves the formula.

Every core coordinate in a stratum has period \(d_H\). A pair with periods \(e\) and \(d_H\) has period \(\operatorname{lcm}(e,d_H)\), because rotation fixes the pair exactly when it fixes both coordinates. Thus per component,

\[
\begin{aligned}
\text{binary words}\quad B_H&=2^q d_Ht_H,\\
\text{binary necklaces}\quad N_H&=\sum_{e\mid q}\frac{d_Ht_Hc(e)}{\operatorname{lcm}(d_H,e)},\\
\text{primitive necklaces}\quad F_H^{\rm count}
&=\sum_{\substack{e\mid q\\\operatorname{lcm}(d_H,e)=n}}
\frac{d_Ht_Hc(e)}{n}.
\end{aligned}
\tag{18}
\]

The last quantity counts primitive necklaces: rotation classes with full spatial period \(n\). It is distinct from a count of polynomial factors. Since \(q\) is a power of two, its positive divisors are exactly the values of \(e\) just listed.

Independently, the tree formula gives

\[
N_H=t_H\left(1+\sum_{j=1}^q\frac{2^{j-1}}{\rho_{h_H}(j)}\right).
\tag{19}
\]

These formulas count complete components without traversing their binary necklaces.

**Retain \(d_H\) when combining graph types.** The topology only uses its power-of-two part \(h_H\), whereas binary word masses can depend on the entire \(d_H\). Equal graph names need not mean equal numbers of binary words per component.

### 8. A finite computation that does not enumerate components

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

This membership test compares with at most \(d_H\le n\) rotation powers. Prime reduction gives the exact order in the quotient group. All these residues describe operators modulo an annihilator, not a catalogue of original binary words or one word per component.

There are \((q+1)^r\) divisor strata. That number can be much smaller than the number of components. No field-log table, minimum-representative store, visited-state bitmap, or list of cosets is required for this census. Factorization and order computations can nevertheless become difficult, and the stratum count can itself grow. This avoids binary word and component enumeration; it is not a universal efficiency guarantee.

### 9. What the theorem does and does not establish

The theorem establishes exact graph topology, exact component multiplicity, exact word and necklace accounting, and a uniform symbolic description of membership. It establishes these for arbitrary positive \(n\), without assuming the patterns observed at smaller \(n\) continue.

It does not determine an ordering of component representatives, minimum binary words, or a symmetry flag defined by a chosen minimum. Those are additional choices. Reversal is an optional involution on the component family, not needed for the partition proof.

The proof is a mathematical argument, not a machine-checked formalization. Small exhaustive checks and agreement with existing data can test an implementation; they do not replace the proof, and the proof does not certify an unchecked program.

### Mathematical context

The algebraic treatment of binary adjacent-difference dynamics has precedent. Breuer, Lötter, and van der Merwe relate Ducci periods to polynomial and finite-field orders in [*Ducci-sequences and cyclotomic polynomials*](https://doi.org/10.1016/j.ffa.2005.11.003), *Finite Fields and Their Applications* 13 (2007), 293–304. Bors discusses nilpotent/periodic decomposition for finite-group endomorphism graphs in [*On the dynamics of endomorphisms of finite groups*](https://arxiv.org/abs/1409.3756).

These are background references, not a claim that either paper states this exact rotation-quotient catalogue theorem. The component-coset correspondence, removal of the rotation twist, branching calculation, and coverage argument needed here are supplied explicitly above. No novelty claim is made.


<a id="compressed-census"></a>

## Exact compression of the graph census

The census uses weighted relation lattices instead of enumerating annihilator divisors. The following argument proves that this compression preserves the complete graph census and its exact accounting. It builds on the [partition proof](#partition-proof).

The argument holds for every positive \(n\); it does not imply a uniform runtime bound.

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

A component, meaning one connected component of the binary necklace functional graph, corresponds to exactly one coset in exactly one family \(U_H/G_H\). If \(c\) is that coset, its words are the inverse CRT image of

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

Orders can therefore be established by a verified bound and successive prime-factor reductions, with exact modular-power tests. The quotient order \(t_i\) and its shift are determined by testing membership in \(\langle x\rangle\), which contains only \(d_i\le n\) rotation operators. These operator residues are not component representatives or a listing of original words.

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

The conventions include \(g=1\), \(\Delta=0\), and \(\gcd(g,0)=g\). No exceptional CRT search over a large interval is needed: \(d\mid n\), even when \(t\) is a large integer.

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

This recurrence does not visit all \((q+1)^r\) tuples. It visits the distinct intermediate states and the local choices. A checkable record can store the local choices and final weighted states; an independent verifier can reconstruct every intermediate map from those inputs.

The exponent tuples remain an implicit, precisely defined family. Compression changes their representation and summation, not the partition theorem. There is no claim that the number of distinct relation states stays small for arbitrarily large \(n\).

### 6. Recover graphs and all counts from a merged state

Let a final state be \((d,t,s)\) with weight \(W\). Every underlying stratum has the same group order \(dt\). Its accumulated component count is therefore

\[
\boxed{A=\frac{W}{dt}.}
\tag{10}
\]

This division is exact: each individual \(\Phi(H)\) in (9) is divisible by \(dt\), since the group acts freely on \(U_H\). Every component represented by this state has the same word count

\[
\boxed{B=2^qdt.}
\tag{11}
\]

To derive its graph shape, let \(h=\gcd(d,q)\), which is the power-of-two part of \(d\). The tree attached to each cycle vertex has maximum depth \(q\). Its branching sequence is

\[
\sigma=2b_1b_2\cdots b_{q-1}0,
\qquad
b_j=\begin{cases}
1,&j\text{ is a power of two and }j\ge h,\\
2,&\text{otherwise}.
\end{cases}
\tag{12}
\]

The graph name is `G` followed by \(t\), a hyphen, and \(\sigma\). The leading 2 counts the cycle predecessor and the unique transient predecessor. The proof in [partition proof](#partition-proof), Section 5, shows that the shift \(s\) can be removed by a graph isomorphism organized by nilpotent height. Thus it is needed for exact composition but is not an additional graph invariant.

For \(e\in\{1,2,4,\ldots,q\}\), define

\[
c(1)=2,\qquad c(e)=2^e-2^{e/2}\quad(e>1).
\]

These are the numbers of transient coordinates of exact rotation period \(e\). Consequently the per-component binary necklace and primitive-necklace counts are

\[
N=\sum_{e\mid q}\frac{dt\,c(e)}{\operatorname{lcm}(d,e)},
\qquad
F=\sum_{\substack{e\mid q\\\operatorname{lcm}(d,e)=n}}
\frac{dt\,c(e)}{n}.
\tag{13}
\]

Here \(F\) counts primitive necklaces, not irreducible polynomial factors.

The merged state contributes \(AB\) words, \(AN\) binary necklaces, and \(AF\) primitive necklaces. Only after computing these quantities should states be grouped by graph name. The full odd part of \(d\) affects word mass, even though the tree depends only on \(h\). Distinct states with the same graph name can therefore have different word masses per component.

#### Repeated factors and powers of two

The exponents \(e_i\) must not be reduced to a present/absent flag when \(q>1\). Repeated factors change the local relations and weights. Likewise, the two-part of the rotation order is retained through \(d\) and determines \(h\) in (12).

If \(n\) itself is a power of two, then \(P=1\), there are no irreducible factors, and the initial state is already the final state. It has \((d,t,s,W)=(1,1,0,1)\): one component with \(2^n\) words. Formula (12) still gives its full tree. In particular, \(n=1024\) does not require a special enumeration or prediction.

### 7. Certificate checks and integer representation

For each \(n\), independent verification can establish:

1. The stated irreducible factors are distinct, irreducible, and multiply to \(Q\); their stated powers multiply to \(P\).
2. Every local unit count, ordinary order, quotient order, and rotation shift is exact.
3. The weighted recurrence produces exactly the stated final states, with no missing or additional states.
4. Each final state has the claimed integral component count, graph branching sequence, and per-component masses.
5. The final graph totals are the exact weighted sums over these states.

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

The arithmetic must not silently overflow. Polynomial coefficient vectors, potentially large link orders and cycle lengths, weights, component counts, and word and necklace totals use exact arbitrary-precision integers. Rotation orders, shifts, depths, and factor exponents are bounded by \(n\), but products with other quantities may be much larger. For example, the word count at \(n=1024\) is exactly \(2^{1024}\), not a signed 64-bit integer or a floating-point approximation.

A record of these quantities supplies a checkable compressed calculation of a partition already justified at set level. It does not supply a list of components, and it does not need one.

<a id="python-implementation"></a>

## Relation to the Python implementation

`shared/algebra.py` computes word-specific invariants and bounded previews. `shared/census.py` uses the partition and weighted relation-lattice arguments above to calculate graph types and multiplicities. `shared/finitefield.py` supplies polynomial arithmetic and factorization over \(\mathbb F_2\). `shared/numbertheory.py` generates and certifies integer factors on demand; no saved factorization or catalogue is required at runtime.

The mathematical classification is finite for every positive \(n\). The interactive implementation has finite input, work, and time limits. An unfinished factorization or census is reported as deferred rather than asserted to be exact. Its returned coverage checks are additional arithmetic checks, not substitutes for the disjoint-partition proof.
