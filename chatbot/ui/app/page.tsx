'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

type Message = {
	role: string
	text: string
}

const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL || ''
const DEFAULT_QUESTION = "Is the necklace represented by 1100101 fixed by the adjacent-XOR map?"

export default function Chat() {

	const [messages, setMessages] = useState<Message[]>([])
	const [input, setInput] = useState('')
	const [statusMessages, setStatusMessages] = useState<string[]>([])
	const [isLoading, setIsLoading] = useState(false)

	async function sendMessage() {

		if (isLoading) return

		const questionText = input.trim() || DEFAULT_QUESTION

		const userMessage = { role: 'user', text: questionText }

		setMessages(prev => [...prev, userMessage])
		setInput('')
		setIsLoading(true)

		try {
			const res = await fetch(`${MCP_URL}/mcp`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ query: userMessage.text })
			})

			if (!res.ok) {
				const errorData = await res.json().catch(() => ({}))
				throw new Error(errorData.detail || `HTTP ${res.status}: ${res.statusText}`)
			}

			const reader = res.body?.getReader()
			const decoder = new TextDecoder()

			if (!reader) {
				throw new Error('No response body')
			}

			let buffer = ''

			while (true) {
				const { done, value } = await reader.read()
				if (done) break

				buffer += decoder.decode(value, { stream: true })
				const lines = buffer.split('\n')
				buffer = lines.pop() || ''

				for (const line of lines) {
					if (line.startsWith('data: ')) {
						const data = JSON.parse(line.slice(6))

						if (data.status === 'running_parallel_analyses') {
							setStatusMessages(prev => [...prev, 'running parallel analyses...'])
						} else if (data.status === 'judging') {
							setStatusMessages(prev => [...prev, 'judging responses...'])
						} else if (data.status === 'first_responder') {
							setStatusMessages(prev => [...prev, 'formulating response...'])
						} else if (data.status === 'skeptic') {
							setStatusMessages(prev => [...prev, 'verifying accuracy...'])
						} else if (data.status === 'arbiter') {
							setStatusMessages(prev => [...prev, 'synthesizing...'])
						} else if (data.status.startsWith('reading_doc')) {
							setStatusMessages(prev => [...prev, 'reading document...'])
						} else if (data.status === 'calculating') {
							setStatusMessages(prev => [...prev, 'calculating...'])
						} else if (data.status === 'done') {
							const botMessage = {
								role: 'assistant',
								text: data.response
							}
							setMessages(prev => [...prev, botMessage])
							setStatusMessages([])
							setIsLoading(false)
						} else if (data.status === 'error') {
							throw new Error(data.error)
						}
					}
				}
			}
		} catch (error) {
			const errorMessage = {
				role: 'assistant',
				text: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`
			}
			setMessages(prev => [...prev, errorMessage])
			setStatusMessages([])
			setIsLoading(false)
		}
	}

	return (
		<div style={{display:'flex', flexDirection:'column', height:'100vh', fontFamily:'CMSroman'}}>

			<div style={{flex:1, padding:20, overflowY:'auto', backgroundColor:'#333333'}}>

				{messages.map((m, i) => (
					<div key={i} style={{display:'flex', gap:10, marginBottom:15}}>
						<div style={{flex:1, color: m.role === 'user' ? '#00ffbb' : '#ffffff'}}>
							<ReactMarkdown>{m.text}</ReactMarkdown>
						</div>
					</div>
				))}

				{statusMessages.length > 0 && (
					<div style={{display:'flex', flexDirection:'column', gap:5, marginBottom:15}}>
						{statusMessages.map((msg, idx) => (
							<p key={idx} style={{fontStyle:'italic', color:'#999', margin:0}}>{msg}</p>
						))}
					</div>
				)}

			</div>

			<div style={{padding:10, backgroundColor:'#222222'}}>

				<textarea
					rows={3}
					style={{
						width:'100%',
						resize:'none',
						boxSizing:'border-box',
						backgroundColor:'transparent',
						outline:'none',
						fontFamily:'CMSroman',
						color:'#22cc99',
						opacity: isLoading ? 0.5 : 1,
					}}
					value={input}
					onChange={(e)=>setInput(e.target.value)}
					onKeyDown={(e)=>{if(e.key==='Enter' && !e.shiftKey){e.preventDefault();sendMessage()}}}
					placeholder={DEFAULT_QUESTION}
					disabled={isLoading}
				/>

			</div>

		</div>
	)
}
