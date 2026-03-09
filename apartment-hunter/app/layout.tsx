import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
});

export const metadata: Metadata = {
  title: "Honolulu Apartment Hunter",
  description: "AI-assisted apartment search for Honolulu 1BR rentals",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geist.variable} font-sans antialiased bg-slate-950 text-slate-100 min-h-screen`}>
        <div className="flex flex-col min-h-screen">
          <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
            <div className="container mx-auto px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🏝️</span>
                <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                  Honolulu Apartment Hunter
                </h1>
              </div>
              <nav className="flex items-center gap-6">
                <Link href="/" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                  Dashboard
                </Link>
                <Link href="/compare" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                  Compare
                </Link>
                <Link href="/pipeline" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                  Pipeline
                </Link>
                <Link href="/settings" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                  Settings
                </Link>
              </nav>
            </div>
          </header>
          <main className="flex-1">
            {children}
          </main>
          <footer className="border-t border-slate-800 py-4 text-center text-slate-500 text-sm">
            Apartment Hunter v1.0 • Budget: $2,700-$3,400 • 1BR/1BA
          </footer>
        </div>
      </body>
    </html>
  );
}
