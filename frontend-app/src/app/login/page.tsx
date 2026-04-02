"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { login, register } from "@/lib/auth";

export default function LoginPage() {
  const { refresh } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result =
      mode === "login"
        ? await login(email, password)
        : await register(email, password, nickname || email.split("@")[0]);

    setLoading(false);

    if (!result.success) {
      setError(result.error || "오류가 발생했습니다");
      return;
    }

    refresh();
    window.location.href = "/";
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white font-bold text-xl mx-auto mb-4">
            K
          </div>
          <h1 className="text-2xl font-bold text-white">
            {mode === "login" ? "로그인" : "회원가입"}
          </h1>
          <p className="text-[#64748b] text-sm mt-2">
            KBO AI Analyzer에 오신 것을 환영합니다
          </p>
        </div>

        {/* 탭 */}
        <div className="flex rounded-lg bg-[#111827] p-1 mb-6">
          <button
            onClick={() => { setMode("login"); setError(""); }}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all ${
              mode === "login"
                ? "bg-[#1a2236] text-white shadow-sm"
                : "text-[#64748b] hover:text-[#94a3b8]"
            }`}
          >
            로그인
          </button>
          <button
            onClick={() => { setMode("register"); setError(""); }}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all ${
              mode === "register"
                ? "bg-[#1a2236] text-white shadow-sm"
                : "text-[#64748b] hover:text-[#94a3b8]"
            }`}
          >
            회원가입
          </button>
        </div>

        {/* 폼 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <div>
              <label className="block text-sm text-[#94a3b8] mb-1.5">닉네임</label>
              <input
                type="text"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="닉네임 (선택)"
                className="w-full px-4 py-3 rounded-lg bg-[#111827] border border-[#1e293b] text-white placeholder-[#475569] focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition"
              />
            </div>
          )}

          <div>
            <label className="block text-sm text-[#94a3b8] mb-1.5">이메일</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="w-full px-4 py-3 rounded-lg bg-[#111827] border border-[#1e293b] text-white placeholder-[#475569] focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition"
            />
          </div>

          <div>
            <label className="block text-sm text-[#94a3b8] mb-1.5">비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="8자 이상, 영문 + 숫자"
              className="w-full px-4 py-3 rounded-lg bg-[#111827] border border-[#1e293b] text-white placeholder-[#475569] focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition"
            />
          </div>

          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold hover:from-blue-500 hover:to-cyan-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                처리 중...
              </span>
            ) : mode === "login" ? (
              "로그인"
            ) : (
              "가입하기"
            )}
          </button>
        </form>

        {/* 하단 안내 */}
        <div className="mt-6 text-center">
          {mode === "login" ? (
            <p className="text-sm text-[#64748b]">
              계정이 없으신가요?{" "}
              <button
                onClick={() => { setMode("register"); setError(""); }}
                className="text-blue-400 hover:text-blue-300 transition"
              >
                회원가입
              </button>
            </p>
          ) : (
            <p className="text-sm text-[#64748b]">
              이미 계정이 있으신가요?{" "}
              <button
                onClick={() => { setMode("login"); setError(""); }}
                className="text-blue-400 hover:text-blue-300 transition"
              >
                로그인
              </button>
            </p>
          )}
        </div>

        {/* Free 티어 안내 */}
        <div className="mt-8 p-4 rounded-lg bg-[#111827] border border-[#1e293b]">
          <p className="text-xs text-[#64748b] text-center">
            가입 시 <span className="text-cyan-400 font-medium">Free</span> 플랜이 적용됩니다.
            매일 1회 AI 분석을 무료로 이용할 수 있습니다.
          </p>
        </div>
      </div>
    </div>
  );
}
