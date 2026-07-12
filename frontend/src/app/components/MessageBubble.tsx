import { Box, Text, Heading, Code, UnorderedList, OrderedList, ListItem } from "@chakra-ui/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import type { Message } from "./ChatInterface";

const mdComponents: Components = {
  h1: (props) => <Heading as="h3" size="md" mt={2} mb={1} {...props} />,
  h2: (props) => <Heading as="h4" size="sm" mt={2} mb={1} {...props} />,
  h3: (props) => <Heading as="h5" size="xs" mt={2} mb={1} {...props} />,
  p: (props) => <Text mb={2} {...props} />,
  strong: (props) => <Text as="strong" fontWeight="bold" {...props} />,
  em: (props) => <Text as="em" fontStyle="italic" {...props} />,
  ul: (props) => <UnorderedList mb={2} {...props} />,
  ol: (props) => <OrderedList mb={2} {...props} />,
  li: (props) => <ListItem {...props} />,
  code: (props) => <Code {...props} />,
};

export function MessageBubble({ role, intent, content }: Message) {
  const isUser = role === "user";

  return (
    <Box alignSelf={isUser ? "flex-end" : "flex-start"} maxW="80%">
      {!isUser && intent && (
        <Text fontSize="xs" color="unicorn.lavender.600" mb={1} ml={1}>
          {intent}
        </Text>
      )}
      <Box
        bg={isUser ? "unicorn.pink.100" : "white"}
        borderWidth={isUser ? 0 : "1px"}
        borderColor="unicorn.lavender.100"
        borderRadius="chatRadius"
        px={4}
        py={2}
      >
        {isUser ? (
          <Text whiteSpace="pre-wrap">{content}</Text>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
            {content}
          </ReactMarkdown>
        )}
      </Box>
    </Box>
  );
}
