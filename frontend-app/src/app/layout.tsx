import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KBO Predictor | AI 경기 예측",
  description: "ML 모델 + 멀티 에이전트 토론 기반 KBO 경기 예측",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* 네비게이션 */}
        <nav className="border-b border-[#1e293b] bg-[#0a0e1a]/90 backdrop-blur-xl sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <a href="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white font-bold text-sm">
                K
              </div>
              <span className="text-lg font-bold tracking-tight text-white">
                KBO <span className="gradient-text">Predictor</span>
              </span>
            </a>
            <div className="flex gap-1">
              {[
                { href: "/", label: "Dashboard" },
                { href: "/standings", label: "Standings" },
                { href: "/history", label: "History" },
              ].map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="px-4 py-2 rounded-lg text-sm text-[#94a3b8] hover:text-white hover:bg-[#1a2236] transition-all"
                >
                  {link.label}
                </a>
              ))}
            </div>
          </div>
        </nav>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-[#1e293b] py-6 text-center text-xs text-[#64748b]">
          <span className="gradient-text font-semibold">KBO Predictor</span>
          {" "}&mdash; ML + Multi-Agent Debate Engine
        </footer>
      </body>
    </html>
  );
}
