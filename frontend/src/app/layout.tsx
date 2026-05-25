import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Tokyo Rooms — Apartment Search",
  description: "Search rental apartments across Suumo, Homes, Chintai and more — all in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 antialiased font-sans transition-colors">
        <ThemeProvider>
          <header className="bg-rose-700 dark:bg-rose-900 px-6 py-3.5 shadow-sm">
            <div className="max-w-5xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl leading-none">🏯</span>
                <div>
                  <div className="font-bold text-white text-base leading-tight tracking-tight">Tokyo Rooms</div>
                  <div className="text-rose-200 text-xs">Suumo · Homes · Chintai</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-rose-200 text-xs hidden sm:block">東京の賃貸物件を探す</span>
                <ThemeToggle />
              </div>
            </div>
          </header>
          <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
