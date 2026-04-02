"use client";

import { useAuth } from "@/components/AuthProvider";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth";
import { API_URL } from "@/lib/config";

const TIERS = [
  {
    id: "free",
    name: "Free",
    price: "무료",
    color: "from-slate-500 to-slate-400",
    border: "border-slate-500/30",
    features: [
      "매일 1회 AI 분석",
      "승리팀 예측",
      "핵심 요인 1줄",
    ],
    limited: [
      "승률 숨김",
      "AI 분석 근거 숨김",
      "ML 모델 상세 숨김",
      "에이전트 토론 숨김",
    ],
  },
  {
    id: "basic",
    name: "Basic",
    price: "₩4,900/월",
    color: "from-cyan-500 to-blue-500",
    border: "border-cyan-500/30",
    features: [
      "매일 5회 AI 분석",
      "실제 라인업 반영 분석",
      "승리팀 + 승률",
      "핵심 요인 3줄",
      "AI 분석 근거 미리보기",
    ],
    limited: [
      "ML 모델 상세 숨김",
      "에이전트 토론 숨김",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "₩9,900/월",
    color: "from-amber-500 to-orange-500",
    border: "border-amber-500/30",
    features: [
      "무제한 AI 분석",
      "실제 라인업 반영 분석",
      "수동 재분석 (맞춤 컨텍스트)",
      "승리팀 + 승률",
      "핵심 요인 전체",
      "AI 분석 근거 전문",
      "ML 모델 상세 (XGB, ELO, Ensemble)",
      "에이전트 토론 전문",
      "전체 기간 적중률 상세",
    ],
    limited: [],
  },
];

export default function MyPage() {
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login";
    }
  }, [loading, user]);

  if (loading || !user) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* 프로필 헤더 */}
      <div className="bg-[#111827] border border-[#1e293b] rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${
              TIERS.find((t) => t.id === user.tier)?.color || "from-slate-500 to-slate-400"
            } flex items-center justify-center text-white font-bold text-xl`}>
              {user.email[0].toUpperCase()}
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{user.email}</h1>
              <div className="flex items-center gap-2 mt-1">
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${
                  user.tier === "pro"
                    ? "bg-amber-500/15 text-amber-400"
                    : user.tier === "basic"
                    ? "bg-cyan-500/15 text-cyan-400"
                    : "bg-slate-500/15 text-slate-400"
                }`}>
                  {user.tier}
                </span>
                <span className="text-sm text-[#64748b]">플랜</span>
              </div>
            </div>
          </div>
          <button
            onClick={logout}
            className="px-4 py-2 rounded-lg text-sm text-[#94a3b8] border border-[#1e293b] hover:bg-[#1a2236] hover:text-white transition"
          >
            로그아웃
          </button>
        </div>
      </div>

      {/* 구독 플랜 비교 */}
      <h2 className="text-lg font-bold text-white mb-4">구독 플랜</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {TIERS.map((tier) => {
          const isCurrent = tier.id === user.tier;
          return (
            <div
              key={tier.id}
              className={`rounded-xl p-5 border transition-all ${
                isCurrent
                  ? `bg-[#111827] ${tier.border} glow-blue`
                  : "bg-[#0d1117] border-[#1e293b] opacity-75 hover:opacity-100"
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`text-lg font-bold bg-gradient-to-r ${tier.color} bg-clip-text text-transparent`}>
                  {tier.name}
                </span>
                <span className="text-sm text-[#94a3b8]">{tier.price}</span>
              </div>

              {isCurrent && (
                <div className="text-xs text-cyan-400 font-medium mb-3 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  현재 플랜
                </div>
              )}

              <ul className="space-y-2">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <span className="text-emerald-400 mt-0.5">&#10003;</span>
                    <span className="text-[#94a3b8]">{f}</span>
                  </li>
                ))}
                {tier.limited.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <span className="text-[#475569] mt-0.5">&#10005;</span>
                    <span className="text-[#475569]">{f}</span>
                  </li>
                ))}
              </ul>

              {!isCurrent && tier.id !== "free" && (
                <button
                  className={`w-full mt-4 py-2.5 rounded-lg text-sm font-medium bg-gradient-to-r ${tier.color} text-white hover:opacity-90 transition disabled:opacity-50`}
                  onClick={async () => {
                    const token = getAccessToken();
                    if (!token) { window.location.href = "/login"; return; }
                    try {
                      const res = await fetch(`${API_URL}/payments/create-checkout`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                        body: JSON.stringify({ tier: tier.id }),
                      });
                      const data = await res.json();
                      if (data.checkout_url) {
                        window.location.href = data.checkout_url;
                      } else {
                        alert(data.detail || "결제 시스템 준비 중입니다");
                      }
                    } catch {
                      alert("결제 시스템 준비 중입니다");
                    }
                  }}
                >
                  업그레이드
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
