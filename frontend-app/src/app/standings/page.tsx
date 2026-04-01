"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { getTeam } from "@/lib/teams";

interface TeamInfo { team: string; elo: number; recent_win_pct: number; streak: number; }

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
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="h-10 bg-[#1e293b] rounded w-64 mb-8 animate-pulse" />
      {[...Array(10)].map((_, i) => (
        <div key={i} className="bg-[#111827] rounded-xl border border-[#1e293b] p-5 mb-3 animate-pulse">
          <div className="flex items-center gap-5">
            <div className="w-10 h-10 bg-[#1e293b] rounded-xl" />
            <div className="w-10 h-10 bg-[#1e293b] rounded-full" />
            <div className="h-4 bg-[#1e293b] rounded w-32" />
            <div className="flex-1 h-2 bg-[#1e293b] rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );

  if (!teams.length) return (
    <div className="max-w-5xl mx-auto px-6 py-10 text-center">
      <div className="text-4xl mb-4 opacity-30">&#128200;</div>
      <div className="text-lg font-semibold text-[#94a3b8]">순위 데이터를 불러올 수 없습니다</div>
    </div>
  );

  const maxElo = Math.max(...teams.map(t => t.elo));
  const minElo = Math.min(...teams.map(t => t.elo));

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-2xl sm:text-4xl font-black tracking-tight mb-2">
        ELO <span className="gradient-text">Rankings</span>
      </h1>
      <p className="text-[#64748b] text-sm sm:text-lg mb-8">ELO 레이팅 기반 팀 파워 랭킹</p>

      <div className="space-y-3">
        {teams.map((t, i) => {
          const meta = getTeam(t.team);
          const pct = ((t.elo - minElo) / (maxElo - minElo)) * 100;
          const streakColor = t.streak > 0 ? "text-emerald-400" : t.streak < 0 ? "text-red-400" : "text-[#64748b]";
          const isTop3 = i < 3;

          return (
            <div key={t.team}>
              <div className={`bg-[#111827] rounded-xl border border-[#1e293b] p-4 sm:p-5 card-hover ${isTop3 ? "glow-blue" : ""}`}>
                {/* 모바일: 2행, 데스크톱: 1행 */}
                <div className="flex items-center gap-3 sm:gap-5">
                  {/* 순위 */}
                  <div className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center font-black text-base sm:text-lg shrink-0 ${
                    i === 0 ? "bg-gradient-to-br from-amber-500 to-amber-600 text-white" :
                    i === 1 ? "bg-gradient-to-br from-gray-300 to-gray-400 text-gray-800" :
                    i === 2 ? "bg-gradient-to-br from-amber-700 to-amber-800 text-amber-200" :
                    "bg-[#1e293b] text-[#64748b]"
                  }`}>
                    {i + 1}
                  </div>

                  {/* 팀 엠블럼 (SVG) */}
                  <Image src={meta.emblem} alt={t.team} width={40} height={40} className="shrink-0" />

                  {/* 팀명 */}
                  <div className="w-28 sm:w-36 shrink-0">
                    <div className="font-bold text-sm">{meta.name}</div>
                    <div className="text-xs text-[#64748b] font-mono">{meta.short}</div>
                  </div>

                  {/* ELO 바 — 모바일 숨김 */}
                  <div className="flex-1 hidden sm:block">
                    <div className="h-2.5 bg-[#1e293b] rounded-full overflow-hidden">
                      <div className="h-full rounded-full animate-fill"
                           style={{
                             width: `${Math.max(pct, 5)}%`,
                             background: `linear-gradient(to right, ${meta.color}, ${meta.color}aa)`,
                           }} />
                    </div>
                  </div>

                  {/* ELO 값 */}
                  <div className="w-14 sm:w-16 text-right shrink-0">
                    <div className="font-mono font-bold text-base sm:text-lg">{Math.round(t.elo)}</div>
                  </div>

                  {/* 최근 승률 */}
                  <div className="w-14 sm:w-20 text-center shrink-0">
                    <div className="text-[10px] sm:text-xs text-[#64748b] mb-0.5 hidden sm:block">최근 10G</div>
                    <div className="font-mono font-bold text-sm">{Math.round(t.recent_win_pct * 100)}%</div>
                  </div>

                  {/* 연승/연패 */}
                  <div className="w-12 sm:w-16 text-right shrink-0">
                    <span className={`font-mono font-bold text-sm ${streakColor}`}>
                      {t.streak > 0 ? `${t.streak}W` : t.streak < 0 ? `${Math.abs(t.streak)}L` : "-"}
                    </span>
                  </div>
                </div>

                {/* 모바일용 ELO 바 */}
                <div className="mt-3 sm:hidden">
                  <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                    <div className="h-full rounded-full animate-fill"
                         style={{
                           width: `${Math.max(pct, 5)}%`,
                           background: `linear-gradient(to right, ${meta.color}, ${meta.color}aa)`,
                         }} />
                  </div>
                </div>
              </div>

              {/* 포스트시즌 컷라인 (5위 아래) */}
              {i === 4 && (
                <div className="flex items-center gap-3 py-2 px-4">
                  <div className="flex-1 border-t border-dashed border-amber-500/30" />
                  <span className="text-[11px] text-amber-500/50 uppercase tracking-wider font-semibold">
                    postseason cutline
                  </span>
                  <div className="flex-1 border-t border-dashed border-amber-500/30" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
