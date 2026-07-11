import type { Metadata } from "next";
import { Baloo_2 } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const baloo2 = Baloo_2({
  subsets: ["latin"],
  variable: "--font-baloo-2",
});

export const metadata: Metadata = {
  title: "Travel Agent",
  description: "AI-powered travel planning agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={baloo2.variable}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
