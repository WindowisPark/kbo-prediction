import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { NavLinks } from "@/components/NavLinks";
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
  title: "KBO AI Analyzer | AI 경기 분석",
  description: "ML 모델 + 멀티 에이전트 토론 기반 KBO 경기 분석 플랫폼",
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
                KBO <span className="gradient-text">Analyzer</span>
              </span>
            </a>
            <NavLinks />
          </div>
        </nav>

        <main className="flex-1">{children}</main>

        {/* 면책 배너 — 상시 노출 */}
        <div className="border-t border-amber-900/30 bg-amber-950/10 px-6 py-3">
          <p className="max-w-5xl mx-auto text-xs text-amber-300/70 text-center leading-relaxed">
            본 서비스는 통계 기반 스포츠 분석 정보를 제공하며, 경기 결과를 보장하지 않습니다.
            분석 정보를 도박 목적으로 사용하는 것을 금지합니다.
            도박 중독 상담:{" "}
            <span className="text-amber-300 font-semibold">한국도박문제관리센터 1336</span>
          </p>
        </div>

        <footer className="border-t border-[#1e293b] py-6 px-6">
          <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
            <span className="text-xs text-[#64748b]">
              <span className="gradient-text font-semibold">KBO AI Analyzer</span>
              {" "}&mdash; ML + Multi-Agent Debate Engine
            </span>
            <div className="flex gap-4 text-xs text-[#475569]">
              <a href="/terms" className="hover:text-[#94a3b8] transition">이용약관</a>
              <a href="/privacy" className="hover:text-[#94a3b8] transition">개인정보처리방침</a>
              <a href="/disclaimer" className="hover:text-[#94a3b8] transition">면책조항</a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
