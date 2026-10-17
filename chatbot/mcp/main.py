import asyncio
import boto3
import json
import sys
from pathlib import Path
from binary_necklaces import RESOURCE_URI
from typing import Optional
from contextlib import AsyncExitStack

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from roles import first_responder, skeptic, arbiter, judge

# Pydantic model for request body
class QueryRequest(BaseModel):
	query: str

# FastAPI app instance
app = FastAPI(title='Binary Necklace Chatbot')

# Global MCP client instance
mcp_client: Optional['MCPClient'] = None


def send_tokens_to_cloudwatch(tokens):
	cloudwatch = boto3.client('cloudwatch', region_name='us-west-2')
	cloudwatch.put_metric_data(
		Namespace='BitloopsChatbot',
		MetricData=[
			{
				'MetricName': 'inputTokens',
				'Value': tokens[0],
				'Unit': 'Count'
			},
			{
				'MetricName': 'outputTokens',
				'Value': tokens[1],
				'Unit': 'Count'
			},
			{
				'MetricName': 'cacheReadInputTokens',
				'Value': tokens[2],
				'Unit': 'Count'
			},
			{
				'MetricName': 'cacheWriteInputTokens',
				'Value': tokens[3],
				'Unit': 'Count'
			}
		]
	)


class MCPClient:
	def __init__(self):
		# initialize session and client objects
		self.session: Optional[ClientSession] = None
		self.exit_stack = AsyncExitStack()
		self.bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')
		self.research_paper: Optional[str] = None
		self.available_tools: Optional[list] = None


	def _call_bedrock(self, prompt: str, messages: list, available_tools: list, research_paper: str):
		'''helper function to call Bedrock API'''
		if not research_paper:
			raise RuntimeError(
				'Research paper resource is empty or unreachable. '
				'The external resource at https://malcolmblack.org/binary-necklaces/binary-necklaces.yml '
				'could not be fetched. Check network connectivity from the container.'
			)
		return self.bedrock.converse(
			modelId='us.anthropic.claude-sonnet-4-5-20250929-v1:0',
			inferenceConfig={'maxTokens': 1000, 'temperature': 0.5},
			system=[
				{'text': research_paper},
				{'cachePoint': {'type': 'default'}},
				{'text': prompt}
			],
			messages=messages,
			toolConfig={'tools': available_tools}
		)


	async def connect_to_server(self, server_script_path: str):
		'''connect to MCP server'''
		server_params = StdioServerParameters(
			command=sys.executable,
			args=[server_script_path]
		)
		# launches MCP server as subprocess, creates stdio pipe
		stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
		# stdio_transport: tuple of the two ends of the stdio pipe (read and write)
		self.stdio, self.write = stdio_transport
		# wrap raw streams into ClientSession; handles serialization, message framing, request/response
		self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
		# perform MCP handshake, server knows it has a live client
		await self.session.initialize()
		print(f'connected to MCP server', file=sys.stderr)

		# fetch and cache paper and tools
		await self._initialize_resources()


	async def _initialize_resources(self):
		'''fetch and cache the research paper and available tools'''
		# get research paper
		response = await self.session.read_resource(RESOURCE_URI)
		self.research_paper = response.contents[0].text
		if not self.research_paper:
			raise RuntimeError(
				'Failed to load research paper: resource at '
				'https://malcolmblack.org/binary-necklaces/binary-necklaces.yml returned empty content. '
				'Check that the URL is reachable from the container.'
			)

		# get tools
		response = await self.session.list_tools()
		self.available_tools = [{
			'toolSpec': {
				'name': tool.name,
				'description': tool.description,
				'inputSchema': {
					'json': tool.inputSchema
				}
			}
		} for tool in response.tools]
		print(f'initialized resources', file=sys.stderr)


	async def process_query(self, query:str, role, status_callback=None):
		'''process a query using Claude and available tools with a specific role'''
		messages = [
			{
				'role': 'user',
				'content': [{'text': query}]
			}
		]

		# use cached resources
		prompt = role.prompt_template

		# initial Bedrock API call
		response = await asyncio.get_event_loop().run_in_executor(
			None,
			self._call_bedrock,
			prompt, messages, self.available_tools, self.research_paper
		)

		# process response and handle tool calls
		final_text = []
		max_iterations = 5
		iteration = 0

		while iteration < max_iterations:
			iteration += 1

			# tokens
			if 'usage' in response:
				usage = response['usage']
				tokens_i = usage.get('inputTokens', 0)
				tokens_o = usage.get('outputTokens', 0)
				tokens_cri = usage.get('cacheReadInputTokens', 0)
				tokens_cwi = usage.get('cacheWriteInputTokens', 0)

			assistant_message_content = []
			has_tool_use = False

			for content in response['output']['message']['content']:
				if next(iter(content)) == 'text':
					final_text.append('\n' + content['text'])
					assistant_message_content.append(content)
				elif next(iter(content)) == 'toolUse':
					has_tool_use = True
					tool_name = content['toolUse']['name']
					tool_args = content['toolUse']['input']
					if status_callback:
						await status_callback('calculating')
					assistant_message_content.append(content)

			# if no tool use, we're done
			if not has_tool_use:
				break

			# add assistant message with tool uses
			messages.append({
				'role': 'assistant',
				'content': assistant_message_content
			})

			# add tool results
			tool_results = []
			for content in assistant_message_content:
				if next(iter(content)) == 'toolUse':
					tool_name = content['toolUse']['name']
					tool_args = content['toolUse']['input']
					result = await self.session.call_tool(tool_name, tool_args)
					tool_results.append({
						'toolResult': {
							'toolUseId': content['toolUse']['toolUseId'],
							'content': [{'text': result.content[0].text}]
						}
					})

			messages.append({
				'role': 'user',
				'content': tool_results
			})

			# get next response from Bedrock
			response = await asyncio.get_event_loop().run_in_executor(
				None,
				self._call_bedrock,
				prompt, messages, self.available_tools, self.research_paper
			)

		return '\n'.join(final_text), (tokens_i, tokens_o, tokens_cri, tokens_cwi)


	async def orchestrate(self, query: str, status_callback=None):
		'''orchestrate three roles: first_responder, skeptic, arbiter'''

		# first_responder
		if status_callback:
			await status_callback('first_responder')
		first_query = first_responder.query_template.format(
			query=query)
		first_response, tokens_F = await self.process_query(first_query, first_responder, status_callback)

		# skeptic
		if status_callback:
			await status_callback('skeptic')
		skeptic_query = skeptic.query_template.format(
			query=query,
			first_response=first_response)
		skeptic_response, tokens_S = await self.process_query(skeptic_query, skeptic, status_callback)

		# arbiter
		if status_callback:
			await status_callback('arbiter')
		arbiter_query = arbiter.query_template.format(
			query=query,
			first_response=first_response,
			skeptic_response=skeptic_response)
		arbiter_response, tokens_A = await self.process_query(arbiter_query, arbiter, status_callback)

		analysis = (first_response, skeptic_response, arbiter_response)
		tokens_i = tokens_F[0] + tokens_S[0] + tokens_A[0]
		tokens_o = tokens_F[1] + tokens_S[1] + tokens_A[1]
		tokens_cri = tokens_F[2] + tokens_S[2] + tokens_A[2]
		tokens_cwi = tokens_F[3] + tokens_S[3] + tokens_A[3]
		tokens = (tokens_i, tokens_o, tokens_cri, tokens_cwi)
		return analysis, tokens


	async def orchestrate_parallel(self, query: str, status_callback=None):
		'''run parallel analyses and judge between them.'''

		# run parallel analyses
		if status_callback:
			await status_callback('running_parallel_analyses')

		results = await asyncio.gather(
			self.orchestrate(query, status_callback),
			self.orchestrate(query, status_callback)
		)
		analysis_1, tokens_1 = results[0]
		analysis_2, tokens_2 = results[1]
		analyses = (analysis_1, analysis_2)

		# judge the responses
		if status_callback:
			await status_callback('judging')

		judge_query = judge.query_template.format(
			query=query,
			arbiter_response_1=analysis_1[2],
			arbiter_response_2=analysis_2[2]
		)

		final_answer, tokens_J = await self.process_query(judge_query, judge, status_callback)

		tokens_i = tokens_1[0] + tokens_2[0] + tokens_J[0]
		tokens_o = tokens_1[1] + tokens_2[1] + tokens_J[1]
		tokens_cri = tokens_1[2] + tokens_2[2] + tokens_J[2]
		tokens_cwi = tokens_1[3] + tokens_2[3] + tokens_J[3]
		tokens = (tokens_i, tokens_o, tokens_cri, tokens_cwi)
		send_tokens_to_cloudwatch(tokens)
		return final_answer, analyses, tokens


	async def cleanup(self):
		'''clean up resources'''
		await self.exit_stack.aclose()


# FastAPI lifecycle events

@app.on_event('startup')
async def startup_event():
	'''initialize MCP client on server startup'''
	global mcp_client
	path_to_server = str(Path(__file__).with_name('binary_necklaces.py'))
	mcp_client = MCPClient()
	await mcp_client.connect_to_server(path_to_server)
	print('MCP HTTP server started and connected to MCP server', file=sys.stderr)


@app.on_event('shutdown')
async def shutdown_event():
	'''cleanup resources on server shutdown'''
	global mcp_client
	if mcp_client:
		await mcp_client.cleanup()
		print('MCP client cleaned up', file=sys.stderr)


# HTTP endpoints

@app.post('/mcp')
async def query_endpoint(request: QueryRequest):
	'''handle query requests with streaming status updates'''
	global mcp_client

	if not mcp_client:
		raise HTTPException(status_code=503, detail='MCP client not initialized')

	status_queue = asyncio.Queue()

	async def process_with_status():
		async def send_status(status: str):
			await status_queue.put({'status': status})

		try:
			response_text, _, _ = await mcp_client.orchestrate_parallel(request.query, send_status)
			await status_queue.put({'status': 'done', 'response': response_text})
		except Exception as e:
			await status_queue.put({'status': 'error', 'error': str(e)})

	async def event_stream():
		task = asyncio.create_task(process_with_status())

		while True:
			data = await status_queue.get()
			yield f'data: {json.dumps(data)}\n\n'

			if data.get('status') in ['done', 'error']:
				break

		await task

	return StreamingResponse(event_stream(), media_type='text/event-stream')


@app.get('/health')
async def health_check():
	'''health check endpoint'''
	return {'status': 'healthy', 'mcp_connected': mcp_client is not None}

