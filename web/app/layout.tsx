import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Freepik AI Studio",
  description:
    "Professional AI studio — text-to-image, motion control, text-to-video, and image-to-video powered by Freepik API.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-bg text-white antialiased">
        <div className="min-h-screen bg-grid-fade">{children}</div>
      </body>
    </html>
  );
}
