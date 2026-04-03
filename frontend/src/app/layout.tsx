import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tokyo Apartment Search",
  description: "Search rental apartments across Suumo, Homes, Chintai and more — all in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <header className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center gap-3">
            <div className="text-2xl font-bold text-blue-600">東京</div>
            <div>
              <div className="font-semibold text-gray-900 leading-tight">Tokyo Apartment Search</div>
              <div className="text-xs text-gray-500">Suumo · Homes · Chintai — aggregated</div>
            </div>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
