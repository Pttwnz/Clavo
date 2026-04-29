import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Cormorant_Garamond, DM_Sans } from "next/font/google";
import { VisitRecorder } from "@/components/analytics/VisitRecorder";
import "./globals.css";

const display = Cormorant_Garamond({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const bodyFont = DM_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Taberna El Clavo · València",
  description: "Taberna en el Grau: tapas, mercado y reserva de mesa.",
  appleWebApp: { capable: true, title: "Taberna El Clavo" },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#8f1d1d",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${display.variable} ${bodyFont.variable} h-full scroll-smooth antialiased`}>
      <body className="font-body flex min-h-full flex-col bg-[#f5f0e8] text-[#2d2420]">
        <Suspense fallback={null}>
          <VisitRecorder />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
