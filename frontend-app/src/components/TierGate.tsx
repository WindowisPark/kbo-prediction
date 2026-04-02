"use client";

import { type ReactNode } from "react";

interface TierGateProps {
  tier: "free" | "basic" | "pro" | undefined;
  requiredTier: "basic" | "pro";
  children: ReactNode;
  placeholder?: ReactNode;
}

const TIER_RANK = { free: 0, basic: 1, pro: 2 };

const UPGRADE_TEXT: Record<string, string> = {
  basic: "Basic 플랜으로 업그레이드",
  pro: "Pro 플랜으로 업그레이드",
};

export function TierGate({ tier, requiredTier, children, placeholder }: TierGateProps) {
  const userRank = TIER_RANK[tier || "free"];
  const requiredRank = TIER_RANK[requiredTier];

  if (userRank >= requiredRank) {
    return <>{children}</>;
  }

  return (
    <div className="relative">
      {/* 블러 오버레이 */}
      <div className="pointer-events-none select-none blur-sm opacity-40">
        {placeholder || children}
      </div>
      {/* 잠금 배지 */}
      <div className="absolute inset-0 flex items-center justify-center">
        <a
          href="/mypage"
          className={`flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-sm text-sm font-medium transition-all hover:scale-105 ${
            requiredTier === "pro"
              ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
              : "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
          }`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          {UPGRADE_TEXT[requiredTier]}
        </a>
      </div>
    </div>
  );
}

/**
 * 블러 처리된 텍스트 (Free 확률 숨김 등)
 */
export function BlurredValue({
  value,
  blurred,
  placeholder = "??%",
}: {
  value: ReactNode;
  blurred: boolean;
  placeholder?: string;
}) {
  if (!blurred) return <>{value}</>;
  return (
    <span className="relative inline-block">
      <span className="blur-md select-none pointer-events-none">{placeholder}</span>
      <a
        href="/mypage"
        className="absolute inset-0 flex items-center justify-center"
        title="Basic 플랜에서 확인"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-cyan-400 opacity-70">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      </a>
    </span>
  );
}
