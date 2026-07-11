import { Box, Heading } from "@chakra-ui/react";
import { keyframes } from "@emotion/react";

const twinkle = keyframes`
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
`;

const SPARKLE_POSITIONS = [
  { top: "10%", left: "8%", delay: "0s" },
  { top: "60%", left: "18%", delay: "0.6s" },
  { top: "20%", left: "88%", delay: "0.3s" },
  { top: "70%", left: "92%", delay: "0.9s" },
];

export function SparkleHeader() {
  return (
    <Box
      position="relative"
      bgGradient="linear(to-r, unicorn.pink.50, unicorn.lavender.50, unicorn.mint.50)"
      py={4}
      textAlign="center"
      overflow="hidden"
    >
      {SPARKLE_POSITIONS.map((pos, i) => (
        <Box
          key={i}
          position="absolute"
          top={pos.top}
          left={pos.left}
          fontSize="lg"
          color="unicorn.lavender.300"
          animation={`${twinkle} 2s ease-in-out infinite`}
          sx={{ animationDelay: pos.delay }}
        >
          ✦
        </Box>
      ))}
      <Heading size="md" color="unicorn.lavender.700">
        Travel Agent
      </Heading>
    </Box>
  );
}
