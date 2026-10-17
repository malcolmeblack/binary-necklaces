import asyncio
import sys
import json
import re
from datetime import datetime
from main import MCPClient

QUESTION = "Is the necklace represented by 1100101 fixed by the adjacent-XOR map?"
NUM_ITERATIONS = 100
RESULTS_FILE = f'test/desc_i{NUM_ITERATIONS}.json'


def yes_or_no(response_text):
	'''extract first occurrence of "yes" or "no"'''
	if not response_text:
		return None
	match = re.search(r'\b(yes|no)\b', response_text, re.IGNORECASE)
	if match and match.group(1).lower() == 'yes':
		return 1
	return 0


async def run_test():
	'''run orchestrate_layer_2 NUM_ITERATIONS times and save results as JSON.'''

	# init MCP client
	client = MCPClient()
	await client.connect_to_server('binary_necklaces.py')

	test_start_time = datetime.now()

	results = {
		'question': QUESTION,
		'num_iterations': NUM_ITERATIONS,
		'iterations': []
	}

	y_count_FR = 0
	y_count_A = 0
	y_count_J = 0

	# run iterations
	for i in range(1, NUM_ITERATIONS + 1):
		print(f'\nITERATION NUMBER: {i}/{NUM_ITERATIONS}\n', file=sys.stderr)

		start_time = datetime.now()
		iteration_result = {
			'iteration': i
		}

		final_answer, analyses, tokens = await client.orchestrate_parallel(QUESTION)
		# extract and log answer
		y_FR = (yes_or_no(analyses[0][0]) + yes_or_no(analyses[1][0])) / 2
		y_A = (yes_or_no(analyses[0][2]) + yes_or_no(analyses[1][2])) / 2
		y_J = yes_or_no(final_answer)
		iteration_result['first_responder_y'] = y_FR
		iteration_result['analysis_y'] = y_A
		iteration_result['judge_y'] = y_J
		y_count_FR += y_FR
		y_count_A += y_A
		y_count_J += y_J

		iteration_result['inputTokens'] = tokens[0]
		iteration_result['outputTokens'] = tokens[1]
		iteration_result['cacheReadInputTokens'] = tokens[2]
		iteration_result['cacheWriteInputTokens'] = tokens[3]

		end_time = datetime.now()
		iteration_result['duration_seconds'] = round((end_time - start_time).total_seconds(), 2)
		results['iterations'].append(iteration_result)

	test_end_time = datetime.now()
	results['avg_duration_seconds'] = round((test_end_time - test_start_time).total_seconds() / NUM_ITERATIONS, 2)

	# calculate percentage of yes answers
	results['accuracy_FR'] = round((y_count_FR / NUM_ITERATIONS * 100), 2)
	results['accuracy_A'] = round((y_count_A / NUM_ITERATIONS * 100), 2)
	results['accuracy_J'] = round((y_count_J / NUM_ITERATIONS * 100), 2)


	# save results
	with open(RESULTS_FILE, 'w') as f:
		json.dump(results, f, indent=2)

	# cleanup
	await client.cleanup()


async def simple():
	client = MCPClient()
	await client.connect_to_server('bitcalc.py')
	response = await client.orchestrate_layer_2(QUESTION)
	await client.cleanup()


if __name__ == '__main__':
	#asyncio.run(simple())
	asyncio.run(run_test())












