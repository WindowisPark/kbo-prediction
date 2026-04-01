"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { getTeam } from "@/lib/teams";

interface PredictionHistory {
  date: string; home_team: string; away_team: string;
  predicted_winner: string; home_win_probability: number;
  confidence: string; actual_winner: string | null;
  is_draw?: boolean; home_score?: number; away_score?: number;
}

interface AccuracyData {
  total_predictions: number; correct: number; accuracy: number;
  by_confidence: Record<string, { total: number; correct: number; accuracy: number }>;
}

type TabType = "overview" | "by-team" | "games";

export default function HistoryPage() {
  const [predictions, setPredictions] = useState<PredictionHistory[]>([]);
  const [stats, setStats] = useState<AccuracyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabType>("overview");
  const [teamFilter, setTeamFilter] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("http://localhost:8000/predictions?limit=500").then(r => r.json()),
      fetch("http://localhost:8000/accuracy").then(r => r.json()),
    ]).then(([p, a]) => {
      setPredictions(p.predictions.reverse());
      setStats(a);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // 경기별 중복 제거 (같은 날 같은 매치업 → 최신만)
  const uniqueGames = (() => {
    const seen = new Set<string>();
    return predictions.filter(p => {
      const key = `${p.date}_${p.home_team}_${p.away_team}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  })();

  // 검증된 경기 (무승부 제외)
  const verified = uniqueGames.filter(p => p.actual_winner && !p.is_draw);

  // 팀별 통계
  const teamStats = (() => {
    const map: Record<string, { total: number; correct: number }> = {};
    for (const p of verified) {
      for (const team of [p.home_team, p.away_team]) {
        if (!map[team]) map[team] = { total: 0, correct: 0 };
        map[team].total++;
        if (p.predicted_winner === p.actual_winner) map[team].correct++;
      }
    }
    return Object.entries(map)
      .map(([team, s]) => ({ team, ...s, accuracy: s.total > 0 ? s.correct / s.total : 0 }))
      .sort((a, b) => b.accuracy - a.accuracy);
  })();

  if (loading) return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="h-10 bg-[#1e293b] rounded w-64 mb-8 animate-pulse" />
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-[#111827] rounded-xl border border-[#1e293b] p-6 animate-pulse">
            <div className="h-10 bg-[#1e293b] rounded w-20 mx-auto mb-2" />
            <div className="h-3 bg-[#1e293b] rounded w-24 mx-auto" />
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-2xl sm:text-4xl font-black tracking-tight mb-2">
        Analysis <span className="gradient-text">Record</span>
      </h1>
      <p className="text-[#64748b] text-sm sm:text-lg mb-6">분석 정확도 통계 및 경기별 결과</p>

      {/* 총합 통계 */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            { label: "총 분석", value: uniqueGames.length, color: "from-blue-600 to-cyan-600" },
            { label: "검증 완료", value: verified.length, color: "from-violet-600 to-violet-500" },
            { label: "적중", value: stats.correct, color: "from-emerald-600 to-emerald-500" },
            { label: "정확도", value: stats.accuracy > 0 ? `${Math.round(stats.accuracy * 100)}%` : "-", color: "from-orange-600 to-amber-500" },
          ].map((card, i) => (
            <div key={i} className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 sm:p-5 text-center">
              <div className={`text-2xl sm:text-3xl font-black font-mono bg-gradient-to-r ${card.color} bg-clip-text text-transparent`}>
                {card.value}
              </div>
              <div className="text-[10px] sm:text-xs text-[#64748b] uppercase tracking-wider mt-1 font-semibold">{card.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* 신뢰도별 정확도 */}
      {stats && stats.by_confidence && Object.keys(stats.by_confidence).length > 0 && (
        <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 sm:p-5 mb-8">
          <div className="text-xs text-[#64748b] uppercase tracking-wider font-semibold mb-3">신뢰도별 정확도</div>
          <div className="flex gap-4">
            {["low", "medium", "high"].map(conf => {
              const d = stats.by_confidence[conf];
              if (!d) return null;
              const colors: Record<string, string> = {
                low: "text-red-400", medium: "text-amber-400", high: "text-emerald-400"
              };
              return (
                <div key={conf} className="flex-1 text-center">
                  <div className={`text-xl sm:text-2xl font-black font-mono ${colors[conf]}`}>
                    {Math.round(d.accuracy * 100)}%
                  </div>
                  <div className="text-[10px] text-[#64748b] uppercase mt-0.5">{conf} ({d.correct}/{d.total})</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 탭 */}
      <div className="flex gap-1 mb-6 border-b border-[#1e293b] pb-2">
        {([
          { id: "overview" as TabType, label: "경기별 결과" },
          { id: "by-team" as TabType, label: "팀별 통계" },
        ]).map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm transition-all ${
              tab === t.id
                ? "text-white bg-[#1a2236] font-semibold border border-blue-500/30"
                : "text-[#94a3b8] hover:text-white hover:bg-[#1a2236]"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 탭: 경기별 결과 */}
      {tab === "overview" && (
        <>
          {uniqueGames.length === 0 ? (
            <div className="text-center py-16 bg-[#111827] rounded-xl border border-[#1e293b]">
              <div className="text-4xl mb-3 opacity-30">&#9918;</div>
              <div className="text-lg font-semibold text-[#94a3b8]">아직 분석 기록이 없습니다</div>
              <div className="text-sm text-[#64748b] mt-1">Dashboard에서 첫 분석을 실행하세요</div>
            </div>
          ) : (
            <div className="space-y-2">
              {uniqueGames.map((p, i) => {
                const isCorrect = p.actual_winner && !p.is_draw ? p.predicted_winner === p.actual_winner : null;
                const isDraw = p.is_draw;
                const away = getTeam(p.away_team);
                const home = getTeam(p.home_team);

                return (
                  <div key={i} className="bg-[#111827] border border-[#1e293b] rounded-xl px-4 sm:px-5 py-3 sm:py-4 card-hover">
                    <div className="flex items-center gap-3 sm:gap-4">
                      {/* 날짜 */}
                      <div className="text-xs sm:text-sm text-[#64748b] font-mono w-20 sm:w-24 shrink-0">{p.date}</div>

                      {/* 팀 매치업 */}
                      <div className="flex-1 flex items-center gap-2">
                        <Image src={away.emblem} alt={p.away_team} width={24} height={24} className="shrink-0" />
                        <span className="font-bold text-sm">{away.short}</span>
                        {p.away_score != null && (
                          <span className="font-mono text-sm text-[#94a3b8]">{p.away_score}</span>
                        )}
                        <span className="text-[#475569] text-xs">vs</span>
                        {p.home_score != null && (
                          <span className="font-mono text-sm text-[#94a3b8]">{p.home_score}</span>
                        )}
                        <span className="font-bold text-sm">{home.short}</span>
                        <Image src={home.emblem} alt={p.home_team} width={24} height={24} className="shrink-0" />
                      </div>

                      {/* AI 분석 결과 */}
                      <div className="text-sm flex items-center gap-2 shrink-0">
                        <span className="text-[#64748b] text-xs hidden sm:inline">AI:</span>
                        <span className="text-blue-400 font-semibold">
                          {getTeam(p.predicted_winner).short}
                        </span>
                      </div>

                      {/* 적중 여부 */}
                      <div className="w-10 text-center shrink-0">
                        {isDraw && <span className="text-[#475569] text-xs">무승부</span>}
                        {isCorrect === true && <span className="text-emerald-400 font-bold text-lg">O</span>}
                        {isCorrect === false && <span className="text-red-400 font-bold text-lg">X</span>}
                        {isCorrect === null && !isDraw && <span className="text-[#334155]">-</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* 탭: 팀별 통계 */}
      {tab === "by-team" && (
        <div className="space-y-3">
          {teamStats.length === 0 ? (
            <div className="text-center py-16 bg-[#111827] rounded-xl border border-[#1e293b]">
              <div className="text-lg font-semibold text-[#94a3b8]">검증된 분석 결과가 없습니다</div>
            </div>
          ) : teamStats.map((ts, i) => {
            const meta = getTeam(ts.team);
            const pct = Math.round(ts.accuracy * 100);
            return (
              <div key={ts.team} className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 sm:p-5 card-hover flex items-center gap-4">
                <Image src={meta.emblem} alt={ts.team} width={36} height={36} className="shrink-0" />
                <div className="w-28 sm:w-36 shrink-0">
                  <div className="font-bold text-sm">{meta.name}</div>
                  <div className="text-xs text-[#64748b]">{ts.correct}/{ts.total} 적중</div>
                </div>
                <div className="flex-1">
                  <div className="h-2.5 bg-[#1e293b] rounded-full overflow-hidden">
                    <div className="h-full rounded-full animate-fill"
                      style={{
                        width: `${Math.max(pct, 3)}%`,
                        background: pct >= 60 ? "linear-gradient(to right, #10b981, #34d399)"
                          : pct >= 45 ? "linear-gradient(to right, #f59e0b, #fbbf24)"
                          : "linear-gradient(to right, #ef4444, #f87171)",
                      }} />
                  </div>
                </div>
                <div className="w-16 text-right shrink-0">
                  <span className={`font-mono font-black text-lg ${
                    pct >= 60 ? "text-emerald-400" : pct >= 45 ? "text-amber-400" : "text-red-400"
                  }`}>
                    {pct}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
