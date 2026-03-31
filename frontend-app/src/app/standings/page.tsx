"use client";

import { useEffect, useState } from "react";

interface TeamInfo { team: string; elo: number; recent_win_pct: number; streak: number; }

const TEAM_META: Record<string, { name: string; color: string }> = {
  KIA: { name: "KIA 타이거즈", color: "#e11d48" }, KT: { name: "kt wiz", color: "#1d1d1b" },
  LG: { name: "LG 트윈스", color: "#c2002f" }, NC: { name: "NC 다이노스", color: "#1b3668" },
  SSG: { name: "SSG 랜더스", color: "#ce0e2d" }, 두산: { name: "두산 베어스", color: "#131230" },
  롯데: { name: "롯데 자이언츠", color: "#041e42" }, 삼성: { name: "삼성 라이온즈", color: "#0066b3" },
  Heroes: { name: "키움 히어로즈", color: "#570514" }, 한화: { name: "한화 이글스", color: "#ff6600" },
};

export default function StandingsPage() {
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/standings")
      .then(r => r.json())
      .then(d => { setTeams(d.teams); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="max-w-5xl mx-auto px-6 py-10 text-[#64748b]">Loading...</div>
  );

  const maxElo = Math.max(...teams.map(t => t.elo));
  const minElo = Math.min(...teams.map(t => t.elo));

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-4xl font-black tracking-tight mb-2">
        ELO <span className="gradient-text">Rankings</span>
      </h1>
      <p className="text-[#64748b] text-lg mb-8">2025 시즌 ELO 레이팅 기반 팀 파워 랭킹</p>

      <div className="space-y-3">
        {teams.map((t, i) => {
          const meta = TEAM_META[t.team] || { name: t.team, color: "#2563eb" };
          const pct = ((t.elo - minElo) / (maxElo - minElo)) * 100;
          const streakColor = t.streak > 0 ? "text-emerald-400" : t.streak < 0 ? "text-red-400" : "text-[#64748b]";
          const isTop3 = i < 3;

          return (
            <div key={t.team}
              className={`bg-[#111827] rounded-xl border border-[#1e293b] p-5 card-hover flex items-center gap-5 ${isTop3 ? "glow-blue" : ""}`}>
              {/* 순위 */}
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg ${
                i === 0 ? "bg-gradient-to-br from-amber-500 to-amber-600 text-white" :
                i === 1 ? "bg-gradient-to-br from-gray-300 to-gray-400 text-gray-800" :
                i === 2 ? "bg-gradient-to-br from-amber-700 to-amber-800 text-amber-200" :
                "bg-[#1e293b] text-[#64748b]"
              }`}>
                {i + 1}
              </div>

              {/* 팀 아이콘 */}
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg font-black"
                   style={{ backgroundColor: meta.color + "20", color: meta.color }}>
                {meta.name.charAt(0)}
              </div>

              {/* 팀명 */}
              <div className="w-36">
                <div className="font-bold text-sm">{meta.name}</div>
                <div className="text-xs text-[#64748b] font-mono">{t.team}</div>
              </div>

              {/* ELO 바 */}
              <div className="flex-1">
                <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                  <div className="h-full rounded-full animate-fill bg-gradient-to-r from-blue-600 to-cyan-500"
                       style={{ width: `${Math.max(pct, 5)}%` }} />
                </div>
              </div>

              {/* ELO 값 */}
              <div className="w-16 text-right">
                <div className="font-mono font-bold text-lg">{Math.round(t.elo)}</div>
              </div>

              {/* 최근 승률 */}
              <div className="w-20 text-center">
                <div className="text-xs text-[#64748b] mb-0.5">최근 10G</div>
                <div className="font-mono font-bold text-sm">{Math.round(t.recent_win_pct * 100)}%</div>
              </div>

              {/* 연승/연패 */}
              <div className="w-16 text-right">
                <span className={`font-mono font-bold text-sm ${streakColor}`}>
                  {t.streak > 0 ? `${t.streak}W` : t.streak < 0 ? `${Math.abs(t.streak)}L` : "-"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
