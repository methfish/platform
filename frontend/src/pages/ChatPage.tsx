import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Sparkles, Trash2 } from 'lucide-react';
import { sendChatMessage, type ChatMessage } from '../api/chat';

const SUGGESTIONS = [
  'What strategies work best for EUR/USD?',
  'Analyze my current positions and risk exposure',
  'Compare SMA crossover vs RSI on AAPL',
  'How should I optimize my bollinger band parameters?',
  'What data should I collect before backtesting forex?',
  'Explain the Sharpe ratio and how to improve it',
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (text?: string) => {
    const content = text || input.trim();
    if (!content || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', content };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage(newMessages);
      setMessages([...newMessages, { role: 'assistant', content: response.content }]);
    } catch (err: any) {
      const errorMsg = err?.response?.status === 503
        ? 'AI chat is not configured. Please set `LLM_API_KEY` in the backend environment.'
        : 'Failed to get a response. Please try again.';
      setMessages([
        ...newMessages,
        { role: 'assistant', content: errorMsg },
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent/15">
            <Sparkles className="h-5 w-5 text-accent" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-100">Pensy AI</h1>
            <p className="text-xs text-gray-500">Quantitative research assistant</p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 hover:bg-surface-overlay rounded-lg transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full space-y-8">
            <div className="text-center space-y-3">
              <div className="mx-auto w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center">
                <Sparkles className="h-8 w-8 text-accent" />
              </div>
              <h2 className="text-xl font-bold text-gray-100">How can I help?</h2>
              <p className="text-sm text-gray-500 max-w-md">
                Ask me about strategies, backtesting, data analysis, risk management,
                or anything related to quantitative trading research.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-2xl w-full">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSend(suggestion)}
                  className="text-left px-4 py-3 rounded-xl border border-surface-border hover:border-accent/40 hover:bg-surface-overlay/50 transition-all text-sm text-gray-400 hover:text-gray-200"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="shrink-0 w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center mt-0.5">
                  <Bot className="h-4 w-4 text-accent" />
                </div>
              )}
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-accent/20 text-gray-100'
                    : 'bg-surface-raised text-gray-200 border border-surface-border'
                }`}
              >
                {msg.role === 'assistant' ? (
                  <div className="prose prose-invert prose-sm max-w-none [&>p]:mb-2 [&>ul]:mb-2 [&>ol]:mb-2 [&>pre]:bg-surface [&>pre]:rounded-lg [&>pre]:p-3 [&>code]:text-accent [&>h1]:text-base [&>h2]:text-sm [&>h3]:text-sm">
                    <MarkdownRenderer content={msg.content} />
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="shrink-0 w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center mt-0.5">
                  <User className="h-4 w-4 text-blue-400" />
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex gap-3">
            <div className="shrink-0 w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center">
              <Bot className="h-4 w-4 text-accent" />
            </div>
            <div className="bg-surface-raised border border-surface-border rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking...
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-surface-border">
        <div className="flex items-end gap-3 max-w-4xl mx-auto">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about strategies, backtesting, risk..."
              rows={1}
              className="w-full resize-none rounded-xl border border-surface-border bg-surface-raised px-4 py-3 pr-12 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-colors"
              style={{ minHeight: '44px', maxHeight: '120px' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = Math.min(target.scrollHeight, 120) + 'px';
              }}
            />
          </div>
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            className="shrink-0 p-3 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <Send className="h-4 w-4 text-white" />
          </button>
        </div>
        <p className="text-[10px] text-gray-600 text-center mt-2">
          Pensy AI powered by Claude. Responses are for research purposes only.
        </p>
      </div>
    </div>
  );
}

/** Simple markdown renderer for assistant messages */
function MarkdownRenderer({ content }: { content: string }) {
  // Convert markdown to basic HTML
  const html = content
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p>')
    // Single newlines to <br>
    .replace(/\n/g, '<br/>');

  // Wrap consecutive <li> tags in <ul>
  const wrapped = html
    .replace(/(<li>.*?<\/li>)(\s*<br\/>)*\s*(<li>)/g, '$1$3')
    .replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');

  return <div dangerouslySetInnerHTML={{ __html: `<p>${wrapped}</p>` }} />;
}
