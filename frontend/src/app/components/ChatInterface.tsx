"use client";

import { useState } from "react";
import { Box, VStack } from "@chakra-ui/react";
import { SparkleHeader } from "./SparkleHeader";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ThinkingIndicator } from "./ThinkingIndicator";

export interface Message {
  role: "user" | "assistant";
  intent?: string;
  content: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    const message = input.trim();
    if (!message || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", intent: data.intent, content: data.response },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: could not reach the backend." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      maxW="2xl"
      mx="auto"
      h={{ base: "100vh", md: "calc(100vh - 3rem)" }}
      my={{ base: 0, md: 6 }}
      display="flex"
      flexDirection="column"
      bg="white"
      borderWidth="1px"
      borderColor="unicorn.lavender.100"
      borderRadius="chatRadius"
      boxShadow="md"
      overflow="hidden"
    >
      <SparkleHeader />
      <VStack flex="1" overflowY="auto" spacing={4} p={4} align="stretch">
        <MessageList messages={messages} />
        {loading && <ThinkingIndicator />}
      </VStack>
      <ChatInput
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        disabled={loading}
      />
    </Box>
  );
}
