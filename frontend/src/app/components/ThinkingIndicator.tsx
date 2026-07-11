import { Box, HStack, Text } from "@chakra-ui/react";
import { keyframes } from "@emotion/react";

const bounce = keyframes`
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-4px); opacity: 1; }
`;

const DOT_DELAYS = ["0s", "0.15s", "0.3s"];

export function ThinkingIndicator() {
  return (
    <Box alignSelf="flex-start" maxW="80%">
      <Box
        bg="white"
        borderWidth="1px"
        borderColor="unicorn.lavender.100"
        borderRadius="chatRadius"
        px={4}
        py={2}
      >
        <HStack spacing={2}>
          <HStack spacing={1}>
            {DOT_DELAYS.map((delay, i) => (
              <Box
                key={i}
                w={2}
                h={2}
                borderRadius="full"
                bg="unicorn.lavender.300"
                animation={`${bounce} 1.2s ease-in-out infinite`}
                sx={{ animationDelay: delay }}
              />
            ))}
          </HStack>
          <Text fontSize="sm" color="unicorn.lavender.600">
            ...thinking
          </Text>
        </HStack>
      </Box>
    </Box>
  );
}
