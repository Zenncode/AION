import { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation } from '@apollo/client';
import { SEND_COPilot_MESSAGE } from '@/graphql/queries';
import { ChatMessage, ChatResponse, ChartData } from '@/types';
import { HiPaperAirplane, HiShieldCheck, HiExclamationTriangle } from 'react-icons/hi2';
import MessageBubble from './MessageBubble';
import ChartRenderer from './ChartRenderer';

export default function Copilot() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [sendMessage] = useMutation<{ copilotChat: ChatResponse }>(SEND_COPilot_MESSAGE);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || isStreaming) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    // Add placeholder for assistant
    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const { data } = await sendMessage({
        variables: {
          input: {
            question,
            maxResults: 100,
          },
        },
      });

      if (data?.copilotChat) {
        const response = data.copilotChat;

        // Parse chart data from SQL results if applicable
        const chartData = response.sqlResults
          ? inferChartType(response.sqlResults, question)
          : undefined;

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? {
                  ...msg,
                  content: response.answer,
                  sqlQuery: response.sqlQuery ?? undefined,
                  sqlResults: response.sqlResults ?? undefined,
                  chartData,
                  modelUsed: response.modelUsed ?? undefined,
                  latencyMs: response.latencyMs,
                  guardrailFlags: response.guardrailFlags,
                }
              : msg
          )
        );
      }
    } catch (error) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                content: 'An error occurred while processing your request. Please try again.',
              }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-[#334155] px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center">
          <span className="text-white font-bold text-sm">AI</span>
        </div>
        <div>
          <h1 className="text-lg font-semibold">AION Copilot</h1>
          <p className="text-xs text-gray-500">
            Ask questions about your business data · Powered by Claude / GPT-4
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-purple-600/20 flex items-center justify-center mb-4">
              <span className="text-purple-400 font-bold text-2xl">AI</span>
            </div>
            <h2 className="text-xl font-semibold mb-2">How can I help you today?</h2>
            <p className="text-gray-400 max-w-md mb-8">
              Ask questions about revenue, customers, inventory, or any business metric.
              I can query your data warehouse and generate charts.
            </p>
            <div className="grid grid-cols-2 gap-3 max-w-lg">
              {[
                'Why did sales drop in the West region yesterday?',
                'Show me the top 10 customers by revenue this quarter',
                'What is our current inventory turnover rate?',
                'Which products are at risk of stockout?',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="text-left text-sm p-3 rounded-lg bg-[#1e293b] border border-[#334155] hover:border-blue-500/50 transition-colors text-gray-300"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className="animate-fade-in">
            <MessageBubble message={msg} />
            {msg.chartData && (
              <div className="mt-4 ml-12">
                <ChartRenderer data={msg.chartData} />
              </div>
            )}
            {msg.sqlQuery && (
              <details className="mt-2 ml-12">
                <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">
                  View generated SQL
                </summary>
                <pre className="mt-2 p-3 bg-[#0f172a] rounded-lg text-xs text-gray-300 overflow-x-auto border border-[#334155]">
                  {msg.sqlQuery}
                </pre>
              </details>
            )}
            {msg.guardrailFlags && msg.guardrailFlags.length > 0 && (
              <div className="mt-2 ml-12 flex items-center gap-2 text-xs text-yellow-400">
                <HiExclamationTriangle className="w-4 h-4" />
                <span>Guardrail: {msg.guardrailFlags.map((f) => f.message).join(', ')}</span>
              </div>
            )}
          </div>
        ))}

        {isStreaming && messages[messages.length - 1]?.role === 'user' && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <div className="bg-[#1e293b] rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[#334155] px-6 py-4">
        <form onSubmit={handleSubmit} className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your data..."
              rows={1}
              className="w-full bg-[#1e293b] border border-[#334155] rounded-xl px-4 py-3 pr-12 text-sm text-white placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500 transition-colors"
              style={{ minHeight: '48px', maxHeight: '120px' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = Math.min(target.scrollHeight, 120) + 'px';
              }}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-3 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <HiPaperAirplane className="w-5 h-5" />
          </button>
        </form>
        <div className="flex items-center gap-2 mt-2 text-xs text-gray-600">
          <HiShieldCheck className="w-3 h-3" />
          <span>Guardrails active · SQL injection & PII protection enabled</span>
        </div>
      </div>
    </div>
  );
}

// --- Helpers ---

function inferChartType(rows: Record<string, unknown>[], question: string): ChartData | null {
  if (!rows || rows.length === 0) return null;

  const columns = Object.keys(rows[0]);
  const q = question.toLowerCase();

  // Try to identify x-axis (string/categorical) and y-axis (numeric)
  const stringCols = columns.filter((c) => typeof rows[0][c] === 'string');
  const numericCols = columns.filter((c) => typeof rows[0][c] === 'number');

  if (stringCols.length === 0 || numericCols.length === 0) return null;

  const xCol = stringCols[0];
  const yCol = numericCols[0];

  const labels = rows.map((r) => String(r[xCol]));
  const values = rows.map((r) => Number(r[yCol]));

  // Determine chart type based on question keywords
  let chartType: ChartData['type'] = 'bar';
  if (q.includes('trend') || q.includes('over time') || q.includes('daily') || q.includes('daily')) {
    chartType = 'line';
  } else if (q.includes('share') || q.includes('proportion') || q.includes('breakdown')) {
    chartType = 'doughnut';
  } else if (q.includes('scatter') || q.includes('correlation')) {
    chartType = 'scatter';
  }

  return {
    type: chartType,
    labels,
    datasets: [
      {
        label: yCol,
        data: values,
        backgroundColor: 'rgba(37, 99, 235, 0.8)',
        borderColor: 'rgb(37, 99, 235)',
        borderWidth: 1,
        fill: chartType === 'line',
        tension: 0.4,
      },
    ],
    title: `${yCol} by ${xCol}`,
  };
}
