"""Binary words, necklaces, and their adjacent-XOR functional digraph.

The canonical image/preimage functions distinguish literal words from necklace
representatives. Legacy aliases retain the old Python import interface.
"""
def divisors(n):
    """Positive divisors, in increasing order (word lengths are at most 64)."""
    return [d for d in range(1, n + 1) if n % d == 0]



def words_equal(bs1, bs2):
	"""are binary words equal"""
	return bs1 == bs2


def necklaces_equal(bs1, bs2):
	"""are binary necklaces equal"""
	return len(bs1) == len(bs2) and bs2 in bs1 + bs1


def decimal_to_word(n, dec):
	"""convert decimal to binary, preserve string length"""
	b = (bin(dec))[2:]
	return (n - len(b)) * '0' + b


def word_to_decimal(bs):
	"""convert binary to decimal"""
	bs = bs[bs.find('1'):]
	return int(str(bs), 2)


def parity(bs):
	"""sum of 1s in the binary word is even (true/false)"""
	return bs.count('1') % 2 == 0


def complement(bs):
	"""switch 1s for 0s and vice versa"""
	i = ''
	for b in bs:
		i += str(int(b) ^ 1)
	return i


def is_self_complementary(bs):
	"""does the rotation class of the binary necklace
	contain complementary pairs of binary words"""
	return necklaces_equal(bs, complement(bs))


def reversal(bs):
	"""reverse order of bits"""
	return bs[::-1]


def is_palindrome(bs):
	"""is reverse the same as non-reverse"""
	return bs == reversal(bs)


def is_achiral(bs):
	"""does the rotation class of the binary necklace
	contain reverse pairs of binary words"""
	for i in rotations(bs):
		if bs == reversal(i):
			return True
	return False


def rotate_left(bs, t):
	"""rotate order of bits by t bits"""
	t %= len(bs)
	r = bs[t:] + bs[:t]
	return r


def necklace_image(bs):
	"""Least representative of the adjacent-XOR image necklace (not the literal word D(w))."""
	l = ''
	for i in range(len(bs)):
		l += str(int(bs[i]) ^ int(bs[(i +1) % len(bs)]))
	return least_rotation(l)


def one_necklace_preimage(bs):
	"""return the preimage of a given binary necklace
	or an empty string if the binary necklace has no preimage"""
	sl = ''
	if parity(bs):
		sl += '0'
		for i in range(len(bs) - 1):
			sl += str(int(sl[i]) ^ int(bs[i]))
	return sl if sl == '' else least_rotation(sl)


def primitive_root(bs):
	"""return the primitive root of a given binary necklace"""
	n = len(bs)
	divs = divisors(n)
	for div in divs:
		p = bs[:div]
		if p * (n // div) == bs:
			return p


def rotations(bs):
	"""return all unique rotations of a binary word
	that is, the rotation class of the respective binary necklace"""
	rots = []
	for i in range(len(primitive_root(bs))):
		rots.append(rotate_left(bs, i))
	return rots


def least_rotation(bs):
	"""minimum value rotation (canonical form)"""
	rots = [word_to_decimal(r) for r in rotations(bs)]
	mn = decimal_to_word(len(bs), min(rots))
	return (len(bs) - len(mn)) * '0' + mn


def cycle_root(bs):
	"""the root of the tree that a binary necklace is in"""
	cycle = [bs]
	lbs = necklace_image(bs)
	while not lbs in cycle:
		cycle.append(lbs)
		lbs = necklace_image(lbs)
	return least_rotation(lbs)


def is_root(bs):
	"""is the binary necklace a tree root"""
	return bs == cycle_root(bs)


def cycle_length(rt):
	"""number of roots in a cycle"""
	l = necklace_image(rt)
	i = 1
	while not necklaces_equal(rt, l):
		i += 1
		l = necklace_image(l)
	return i


def cycle_representatives(rt, cycle_length):
	"""list of roots in a component
	input a root and num_roots(root)"""
	rts = []
	for i in range(cycle_length):
		rts.append(rt)
		rt = necklace_image(rt)
	return rts


def least_cycle_representative(cycle_representatives):
	"""minimum value root given the roots in a component"""
	for r in cycle_representatives:
		r = word_to_decimal(r)
	return min(cycle_representatives)


def cycle_predecessor(cycle_root):
	"""the preimage of a root that is also a root"""
	s = one_necklace_preimage(cycle_root)
	return s if is_root(s) else complement(s)


def tree_depth(bs):
	"""tree depth (root at depth zero)"""
	l = 1
	bs = complement(cycle_root(bs))
	while one_necklace_preimage(bs) != '':
		l += 1
		bs = one_necklace_preimage(bs)
	return l


def branching_sequence(bs):
	"""the branching sequence of a tree"""
	s = '2'
	bs = complement(cycle_root(bs))
	while one_necklace_preimage(bs) != '':
		bs = one_necklace_preimage(bs)
		s += '1' if is_self_complementary(bs) else '2'
	s += '0'
	return s


def tree_necklace_count(bs):
	"""number of binary necklaces in a tree"""
	s = branching_sequence(bs)
	num_bl_lv = 1
	num_bl_tr = 2
	for lv in range(2, len(s)):
		num_bl_lv *= int(s[lv - 1])
		num_bl_tr += num_bl_lv
	return num_bl_tr


def tree_word_count(bs):
	"""number of binary words in a tree"""
	s = branching_sequence(bs)
	# level 0 (a root in the cycle)
	bs = cycle_root(bs)
	num_bs_tr = len(primitive_root(bs))
	# level 1
	bs = complement(bs) # preimage of a root that is not also a root
	num_bs_tr += len(primitive_root(bs))
	# levels 2+
	num_bl_lv = 1
	for lv in range(2, len(s)):
		num_bl_lv *= int(s[lv - 1])
		bs = one_necklace_preimage(bs)
		num_bs_tr += len(primitive_root(bs)) * num_bl_lv
	return num_bs_tr


def component_necklace_count(bs):
	"""number of binary necklaces in a component"""
	return cycle_length(cycle_root(bs)) * tree_necklace_count(bs)


def component_mass(bs):
	"""number of binary words in a component"""
	bs = cycle_root(bs)
	num_bs_cyc = len(primitive_root(bs)) * cycle_length(bs)
	return cycle_length(bs) * tree_word_count(bs)


def tree_necklaces(cycle_root):
	"""returns the set of all binary necklaces in a tree"""
	t_ns = [cycle_root]
	sl_off_cycle = complement(cycle_predecessor(cycle_root))
	_visit_tree(sl_off_cycle, t_ns)
	return t_ns


def _visit_tree(t_root, t_ns):
	"""helper function for tree_nodes"""
	t_ns.append(t_root)
	sl = one_necklace_preimage(t_root)
	if sl == '':
		return
	inv = complement(sl)
	_visit_tree(sl, t_ns)
	if not necklaces_equal(sl, inv):
		_visit_tree(inv, t_ns)



def adjacent_xor(word):
    """D(w)=w+R(w), with R the right rotation used in the exposition."""
    return ''.join(str(int(word[i]) ^ int(word[i-1])) for i in range(len(word)))


def word_preimages(word):
    """All word preimages under D; even targets have two, odd targets none."""
    if not parity(word):
        return []
    first = ['0']
    for bit in word[1:]:
        first.append(str(int(first[-1]) ^ int(bit)))
    first = ''.join(first)
    return [first, complement(first)]


def necklace_preimages(word):
    """Distinct preimage necklaces, written as least representatives."""
    return sorted({least_rotation(x) for x in word_preimages(word)})


def tree_levels(word):
    """Number of levels including the cycle root."""
    return tree_depth(word) + 1


# Legacy Python names are retained for existing Lambda packages and scripts.
bs_equals = words_equal
bl_equals = necklaces_equal
dec_to_bs = decimal_to_word
bs_to_dec = word_to_decimal
inverse = complement
is_inverse = is_self_complementary
reverse = reversal
is_reverse = is_palindrome
is_symmetric = is_achiral
rotate = rotate_left
link = necklace_image
sublink = one_necklace_preimage
pattern = primitive_root
min_val_rot = least_rotation
root = cycle_root
num_roots = cycle_length
roots = cycle_representatives
min_val_root = least_cycle_representative
sublink_and_root = cycle_predecessor
num_lvl_tree = tree_depth
structure = branching_sequence
num_bl_tree = tree_necklace_count
num_bs_tree = tree_word_count
num_bl_chain = component_necklace_count
num_bs_chain = component_mass
tree_nodes = tree_necklaces
make_tree = _visit_tree
