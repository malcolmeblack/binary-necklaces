try:
    from src import calc  # Existing Lambda layout.
except ModuleNotFoundError as exc:
    if exc.name != 'src':
        raise
    import calc  # Running directly from this source directory.
from pathlib import Path
import re
import json


def get_item(json_file, n):
	with open(json_file, 'r') as file:
		data = json.load(file)
	for item in data:
		if int(item['n']['N']) == n:
			return {
				'bitloops': int(item['bitloops']['N']),
				'bitstrings': int(item['bitstrings']['N']),
				'sym_chains': int(item['sym_chains']['N']),
				'ls_sym_chains': item['ls_sym_chains']['S'],
				'asym_chains': int(item['asym_chains']['N']),
				'ls_asym_chains': item['ls_asym_chains']['S'],
				'graphs': int(item['graphs']['N']),
				'ls_graphs': item['ls_graphs']['S'],
			}
	return {
		'bitloops': 'no data',
		'bitstrings': 'no data',
		'sym_chains': 'no data',
		'ls_sym_chains': 'no data',
		'asym_chains': 'no data',
		'ls_asym_chains': 'no data',
		'graphs': 'no data',
		'ls_graphs': 'no data',
	}


def handler(event, context):
	query_params = event.get('queryStringParameters') or {}
	bs = query_params.get('bitstring', '')
	if not isinstance(bs, str) or re.fullmatch(r'[01]{1,64}', bs) is None:
		return {'statusCode': 400, 'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
		        'body': json.dumps({'error': 'Enter a binary word of length 1 to 64.'})}
	
	bs_num_bits = len(bs)
	bs_parity = 'Even' if calc.parity(bs) else 'Odd'
	bs_inverse = calc.complement(bs)
	bs_reverse = calc.reversal(bs)
	bs_pattern = calc.primitive_root(bs)
	
	bl_symmetry = 'Symmetric' if calc.is_achiral(bs) else 'Asymmetric'
	bl_link = calc.necklace_image(bs)
	bl_sublink = calc.one_necklace_preimage(bs)
	if bl_sublink == '':
		bl_sublink = 'None'
	bl_mvrot = calc.least_rotation(bs)
	
	tr_root = calc.cycle_root(bs)
	tr_structure = calc.branching_sequence(bs)
	tr_num_levels = calc.tree_depth(bs)
	tr_num_bl = calc.tree_necklace_count(bs)
	tr_num_bs = calc.tree_word_count(bs)
	tr_ls_bl = calc.tree_necklaces(tr_root)
	
	ch_num_trees = calc.cycle_length(tr_root)
	ch_ls_roots = calc.cycle_representatives(tr_root, ch_num_trees)
	ch_mvroo = calc.least_cycle_representative(ch_ls_roots)
	
	catalogue_paths = [Path('data/powerset.json'), Path(__file__).resolve().parent / 'data' / 'powerset.json', Path(__file__).with_name('powerset.json')]
	json_file = next((p for p in catalogue_paths if p.is_file()), catalogue_paths[-1])
	item = get_item(json_file, bs_num_bits)
	
	gr_num_bs = item['bitstrings']
	gr_num_bl = item['bitloops']
	gr_num_sym_chains = item['sym_chains']
	gr_ls_sym_chains = item['ls_sym_chains']
	gr_num_asym_chains = item['asym_chains']
	gr_ls_asym_chains = item['ls_asym_chains']
	if gr_ls_asym_chains == '':
		gr_ls_asym_chains = 'None'
	gr_num_graphs = item['graphs']
	gr_ls_graphs = item['ls_graphs']
	
	return {
		'statusCode': 200,
		'headers': {
			'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'
		},
		'body': json.dumps({
			'word_image': calc.adjacent_xor(bs),
			'necklace_chirality': 'achiral' if calc.is_achiral(bs) else 'chiral',
			'necklace_preimages': calc.necklace_preimages(bs),
			'tree_depth': tr_num_levels,
			'tree_levels': tr_num_levels + 1,
			'bs_num_bits': bs_num_bits,
			'bs_parity': bs_parity,
			'bs_inverse': bs_inverse,
			'bs_reverse': bs_reverse,
			'bs_pattern': bs_pattern,
			
			'bl_symmetry': bl_symmetry,
			'bl_link': bl_link,
			'bl_sublink': bl_sublink,
			'bl_mvrot': bl_mvrot,
			
			'tr_root': tr_root,
			'tr_structure': tr_structure,
			'tr_num_levels': tr_num_levels,
			'tr_num_bl': tr_num_bl,
			'tr_num_bs': tr_num_bs,
			'tr_ls_bl': tr_ls_bl,
			
			'ch_num_trees': ch_num_trees,
			'ch_ls_roots': ch_ls_roots,
			'ch_mvroo': ch_mvroo,
			
			'gr_num_bs': gr_num_bs,
			'gr_num_bl': gr_num_bl,
			'gr_num_sym_chains': gr_num_sym_chains,
			'gr_ls_sym_chains': gr_ls_sym_chains,
			'gr_num_asym_chains': gr_num_asym_chains,
			'gr_ls_asym_chains': gr_ls_asym_chains,
			'gr_num_graphs': gr_num_graphs,
			'gr_ls_graphs': gr_ls_graphs
		})
	}