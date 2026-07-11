import { extendTheme } from "@chakra-ui/react";

const theme = extendTheme({
  colors: {
    unicorn: {
      pink: {
        50: "#fff5f8",
        100: "#ffe3ec",
        200: "#ffc2d6",
        300: "#ff9ebf",
        400: "#ff7aa8",
        500: "#f4568f",
        600: "#d63f73",
        700: "#b02f5a",
        800: "#8a2245",
        900: "#5f1730",
      },
      lavender: {
        50: "#f7f4ff",
        100: "#ece3ff",
        200: "#d9c7ff",
        300: "#c2a5ff",
        400: "#ab84f7",
        500: "#8f66de",
        600: "#7550b8",
        700: "#5c3c92",
        800: "#452c6e",
        900: "#2e1d49",
      },
      mint: {
        50: "#f2fffb",
        100: "#d9fff1",
        200: "#b0f6e0",
        300: "#84e9cd",
        400: "#5cd8b8",
        500: "#3cbd9d",
        600: "#2c9a7f",
        700: "#217862",
        800: "#185947",
        900: "#0f3a2e",
      },
    },
  },
  radii: {
    chatRadius: "2xl",
  },
  fonts: {
    heading: "'Baloo 2', sans-serif",
  },
  styles: {
    global: {
      body: {
        bg: "white",
      },
    },
  },
});

export default theme;
