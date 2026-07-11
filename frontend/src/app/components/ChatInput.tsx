import { HStack, Input, IconButton } from "@chakra-ui/react";
import { FaStar } from "react-icons/fa";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
}

export function ChatInput({ value, onChange, onSubmit, disabled }: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !disabled) {
      onSubmit();
    }
  };

  return (
    <HStack p={4} borderTopWidth="1px" borderColor="unicorn.lavender.100">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about flights, hotels, or the weather..."
        borderRadius="chatRadius"
        disabled={disabled}
      />
      <IconButton
        aria-label="Send message"
        icon={<FaStar />}
        onClick={onSubmit}
        isDisabled={disabled}
        borderRadius="chatRadius"
        bgGradient="linear(to-r, unicorn.pink.300, unicorn.lavender.300)"
        color="white"
        _hover={{ bgGradient: "linear(to-r, unicorn.pink.400, unicorn.lavender.400)" }}
      />
    </HStack>
  );
}
