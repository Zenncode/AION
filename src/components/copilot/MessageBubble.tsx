import { HiUser, HiComputerDesktop } from 'react-icons/hi2';
import ReactMarkdown from 'react-markdown';
import { ChatMessage } from '@/types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isUser ? 'bg-blue-600' : 'bg-purple-600'
        }`}
      >
        {isUser ? (
          <HiUser className="w-4 h-4 text-white" />
        ) : (
          <HiComputerDesktop className="w-4 h-4 text-white" />
        )}
      </div>

      {/* Content */}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white rounded-tr-sm'
            : 'bg-[#1e293b] text-gray-100 rounded-tl-sm border border-[#334155]'
        }`}
      >
        {isUser ? (
          <p className="text-sm">{message.content}</p>
        ) : (
          <div className="text-sm prose prose-invert prose-sm max-w-none prose-p:my-1 prose-pre:bg-[#0f172a] prose-pre:border prose-pre:border-[#334155]">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Metadata */}
        {!isUser && message.latencyMs && (
          <div className="mt-2 pt-2 border-t border-[#334155] flex items-center gap-3 text-xs text-gray-500">
            {message.modelUsed && <span>{message.modelUsed}</span>}
            <span>{message.latencyMs.toFixed(0)}ms</span>
            {message.sqlQuery && <span className="text-green-500">SQL executed</span>}
          </div>
        )}
      </div>
    </div>
  );
}
