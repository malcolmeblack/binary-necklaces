const CHAT_URL = '/api/chatbot'
const POLL_INTERVAL_MS = 1200
const REQUEST_TIMEOUT_MS = 25000
const JOB_TIMEOUT_MS = 285000

class ApiError extends Error {
	constructor(message: string, readonly status: number) {
		super(message)
	}
}

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
	return new Promise((resolve, reject) => {
		if (signal.aborted) return reject(signal.reason)
		const abort = () => {
			clearTimeout(timer)
			signal.removeEventListener('abort', abort)
			reject(signal.reason)
		}
		const timer = setTimeout(() => {
			signal.removeEventListener('abort', abort)
			resolve()
		}, milliseconds)
		signal.addEventListener('abort', abort, { once: true })
	})
}

async function requestJson(url: string, options: RequestInit, signal: AbortSignal) {
	const request = new AbortController()
	const abort = () => request.abort(signal.reason)
	if (signal.aborted) abort()
	else signal.addEventListener('abort', abort, { once: true })
	const timer = setTimeout(() => request.abort(new Error('The request timed out.')), REQUEST_TIMEOUT_MS)
	try {
		const response = await fetch(url, {
			...options,
			cache: 'no-store',
			signal: request.signal,
		})
		const data = await response.json().catch(() => ({}))
		if (!response.ok) {
			throw new ApiError(
				(typeof data.error === 'string' && data.error) ||
				(typeof data.detail === 'string' && data.detail) ||
				`HTTP ${response.status}: ${response.statusText}`,
				response.status,
			)
		}
		return data
	} finally {
		clearTimeout(timer)
		signal.removeEventListener('abort', abort)
	}
}

/** Submit once; polling retries never create another paid question. */
export async function askQuestion(
	query: string,
	onStatus: (status: string) => void,
	signal: AbortSignal,
): Promise<string> {
	const job = new AbortController()
	const abort = () => job.abort(signal.reason)
	if (signal.aborted) abort()
	else signal.addEventListener('abort', abort, { once: true })
	const timer = setTimeout(() => job.abort(new Error('The response timed out. Please try again.')), JOB_TIMEOUT_MS)
	try {
		const submitted = await requestJson(CHAT_URL, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ query }),
		}, job.signal)
		if (!submitted || typeof submitted.jobId !== 'string' || !submitted.jobId ||
			typeof submitted.token !== 'string' || !submitted.token) {
			throw new Error('Invalid response from the chat service.')
		}

		const statusUrl = `${CHAT_URL}/${encodeURIComponent(submitted.jobId)}`
		const seenEvents = new Set<number>()
		let failures = 0
		while (!job.signal.aborted) {
			let update
			try {
				update = await requestJson(statusUrl, {
					headers: { Authorization: `Bearer ${submitted.token}` },
				}, job.signal)
				failures = 0
			} catch (error) {
				if (job.signal.aborted) throw job.signal.reason
				if (++failures > 3 || (error instanceof ApiError &&
					![429, 500, 502, 503, 504].includes(error.status))) throw error
				await wait(POLL_INTERVAL_MS * failures, job.signal)
				continue
			}
			if (!update || typeof update !== 'object') throw new Error('Invalid response from the chat service.')
			if (Array.isArray(update.events)) {
				for (const event of update.events) {
					if (event && Number.isInteger(event.seq) && typeof event.status === 'string' &&
						!seenEvents.has(event.seq)) {
						seenEvents.add(event.seq)
						onStatus(event.status)
					}
				}
			}
			if (update.status === 'done') {
				if (typeof update.response !== 'string') throw new Error('Invalid response from the chat service.')
				return update.response
			}
			if (update.status === 'error') {
				throw new Error(typeof update.error === 'string' ? update.error : 'The question could not be answered.')
			}
			if (!['queued', 'running'].includes(update.status)) {
				throw new Error('Invalid response from the chat service.')
			}
			await wait(POLL_INTERVAL_MS, job.signal)
		}
		throw job.signal.reason
	} finally {
		clearTimeout(timer)
		signal.removeEventListener('abort', abort)
	}
}
