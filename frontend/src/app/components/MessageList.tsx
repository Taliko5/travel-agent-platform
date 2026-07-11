import { MessageBubble } from "./MessageBubble";
import type { Message } from "./ChatInterface";

export function MessageList({ messages }: { messages: Message[] }) {
  return (
    <>
      {messages.map((message, i) => (
        <MessageBubble key={i} {...message} />
      ))}
    </>
  );
}
