"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { verifyEmail, resendCode } from "@/lib/auth";

export default function VerifyPage() {
  const { user, refresh } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result = await verifyEmail(code);
    setLoading(false);

    if (!result.success) {
      setError(result.error || "인증 실패");
      return;
    }

    refresh();
    window.location.href = "/";
  };

  const handleResend = async () => {
    setResending(true);
    setResent(false);
    const result = await resendCode();
    setResending(false);

    if (result.success) {
      setResent(true);
      setTimeout(() => setResent(false), 5000);
    } else {
      setError(result.error || "재발송 실패");
    }
  };

  if (!user) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <p className="text-[#94a3b8] mb-4">로그인이 필요합니다</p>
          <a href="/login" className="text-blue-400 hover:text-blue-300">로그인</a>
        </div>
      </div>
    );
  }

  if (user.isVerified) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">&#10003;</div>
          <p className="text-white font-semibold mb-2">이미 인증된 계정입니다</p>
          <a href="/" className="text-blue-400 hover:text-blue-300">대시보드로 이동</a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white text-2xl mx-auto mb-4">
            &#9993;
          </div>
          <h1 className="text-2xl font-bold text-white">이메일 인증</h1>
          <p className="text-[#64748b] text-sm mt-2">
            <span className="text-white font-medium">{user.email}</span>
            로 인증 코드를 보냈습니다
          </p>
        </div>

        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="6자리 인증 코드"
              maxLength={6}
              className="w-full px-4 py-4 rounded-lg bg-[#111827] border border-[#1e293b] text-white text-center text-2xl font-mono tracking-[0.5em] placeholder-[#475569] placeholder:text-base placeholder:tracking-normal focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition"
            />
          </div>

          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || code.length !== 6}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold hover:from-blue-500 hover:to-cyan-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                확인 중...
              </span>
            ) : (
              "인증하기"
            )}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-sm text-[#64748b]">
            코드를 받지 못하셨나요?{" "}
            <button
              onClick={handleResend}
              disabled={resending}
              className="text-blue-400 hover:text-blue-300 transition disabled:opacity-50"
            >
              {resending ? "발송 중..." : "재발송"}
            </button>
          </p>
          {resent && (
            <p className="text-sm text-emerald-400 mt-2">인증 코드를 다시 보냈습니다</p>
          )}
        </div>

        <div className="mt-8 p-4 rounded-lg bg-[#111827] border border-[#1e293b]">
          <p className="text-xs text-[#64748b] text-center">
            인증 코드는 10분간 유효합니다. 스팸 폴더도 확인해 주세요.
          </p>
        </div>
      </div>
    </div>
  );
}
