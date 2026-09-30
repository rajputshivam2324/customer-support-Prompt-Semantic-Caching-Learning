import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Relay — AI Support Gateway",
  description: "Explainable AI support answers with real cache and retrieval traces",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

