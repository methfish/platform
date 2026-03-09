import client from './client';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  role: 'assistant';
  content: string;
}

export async function sendChatMessage(messages: ChatMessage[]): Promise<ChatResponse> {
  const { data } = await client.post<ChatResponse>('/api/v1/chat', { messages });
  return data;
}

export async function streamChatMessage(
  messages: ChatMessage[],
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  const token = localStorage.getItem('pensy_token');
  const baseUrl = import.meta.env.VITE_API_URL || '';

  const response = await fetch(`${baseUrl}/api/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages }),
  });

  if (!response.ok) {
    onError(`Chat error: ${response.status}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError('No response stream');
    return;
  }

  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') {
          onDone();
          return;
        }
        if (data.startsWith('[ERROR]')) {
          onError(data);
          return;
        }
        onChunk(data);
      }
    }
  }

  onDone();
}
