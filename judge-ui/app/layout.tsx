import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BIM Production Copilot — Governance Before Geometry",
  description: "Evidence-gated BIM readiness, isolated production, independent review and controlled authority promotion.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
