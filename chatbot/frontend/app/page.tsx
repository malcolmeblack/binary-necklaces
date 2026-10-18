'use client'

import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { askQuestion } from './chat-api'

type Message = {
	role: string
	text: string
}

const DEFAULT_QUESTION = "Is the necklace represented by 1100101 fixed by the adjacent-XOR map?"

function statusLabel(status: string): string | undefined {
	if (status.startsWith('reading_doc')) return 'reading document...'
	return {
		running_parallel_analyses: 'running parallel analyses...',
		judging: 'judging responses...',
		first_responder: 'formulating response...',
		skeptic: 'verifying accuracy...',
		arbiter: 'synthesizing...',
		calculating: 'calculating...',
	}[status]
}

export default function Chat() {

	const [messages, setMessages] = useState<Message[]>([])
	const [input, setInput] = useState('')
	const [statusMessages, setStatusMessages] = useState<string[]>([])
	const [isLoading, setIsLoading] = useState(false)
	const request = useRef<AbortController | null>(null)

	useEffect(() => () => {
		const active = request.current
		request.current = null
		active?.abort()
	}, [])

	async function sendMessage() {

		if (request.current) return
		const active = new AbortController()
		request.current = active

		const questionText = input.trim() || DEFAULT_QUESTION

		const userMessage = { role: 'user', text: questionText }

		setMessages(prev => [...prev, userMessage])
		setInput('')
		setIsLoading(true)

		try {
			const response = await askQuestion(userMessage.text, status => {
				const label = statusLabel(status)
				if (label && request.current === active) setStatusMessages(prev => [...prev, label])
			}, active.signal)
			if (request.current === active) setMessages(prev => [...prev, { role: 'assistant', text: response }])
		} catch (error) {
			if (request.current !== active) return
			const errorMessage = {
				role: 'assistant',
				text: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`
			}
			setMessages(prev => [...prev, errorMessage])
		} finally {
			if (request.current === active) {
				request.current = null
				setStatusMessages([])
				setIsLoading(false)
			}
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
