"use client";

import { useEffect, useState } from "react";

interface PredictionHistory {
  date: string; home_team: string; away_team: string;
  predicted_winner: string; home_win_probability: number;
  confidence: string; actual_winner: string | null; created_at: string;
}

const SHORT: Record<string, string> = {
  Heroes: "키움", KIA: "KIA", KT: "KT", LG: "LG", NC: "NC", SSG: "SSG",
  두산: "두산", 롯데: "롯데", 삼성: "삼성", 한화: "한화",
};

export default function HistoryPage() {
  const [predictions, setPredictions] = useState<PredictionHistory[]>([]);
  const [stats, setStats] = useState<{ total_predictions: number; correct: number; accuracy: number } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("http://localhost:8000/predictions?limit=100").then(r => r.json()),
      fetch("http://localhost:8000/accuracy").then(r => r.json()),
    ]).then(([p, a]) => {
      setPredictions(p.predictions.reverse());
      setStats(a);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="max-w-5xl mx-auto px-6 py-10 text-[#64748b]">Loading...</div>;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-4xl font-black tracking-tight mb-2">
        Prediction <span className="gradient-text">History</span>
      </h1>
      <p className="text-[#64748b] text-lg mb-8">과거 분석 결과 및 정확도 트래킹</p>

      {/* 통계 카드 */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: "Total Analyses", value: stats.total_predictions, color: "from-blue-600 to-cyan-600" },
            { label: "Correct", value: stats.correct, color: "from-emerald-600 to-emerald-500" },
            { label: "Accuracy", value: stats.accuracy > 0 ? `${Math.round(stats.accuracy * 100)}%` : "-", color: "from-orange-600 to-amber-500" },
          ].map((card, i) => (
            <div key={i} className="bg-[#111827] rounded-xl border border-[#1e293b] p-6 text-center card-hover">
              <div className={`text-4xl font-black font-mono bg-gradient-to-r ${card.color} bg-clip-text text-transparent`}>
                {card.value}
              </div>
              <div className="text-xs text-[#64748b] uppercase tracking-wider mt-2 font-semibold">{card.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* 예측 리스트 */}
      {predictions.length === 0 ? (
        <div className="text-center text-[#334155] py-20 bg-[#111827] rounded-xl border border-[#1e293b]">
          <div className="text-5xl mb-4">&#9918;</div>
          <div className="text-lg font-semibold text-[#64748b]">아직 분석 기록이 없습니다</div>
          <div className="text-sm text-[#334155] mt-1">Dashboard에서 첫 분석을 실행하세요</div>
        </div>
      ) : (
        <div className="space-y-2">
          {predictions.map((p, i) => {
            const isCorrect = p.actual_winner ? p.predicted_winner === p.actual_winner : null;
            return (
              <div key={i} className="bg-[#111827] border border-[#1e293b] rounded-xl px-5 py-4 flex items-center gap-4 card-hover">
                <div className="text-sm text-[#64748b] font-mono w-28">{p.date}</div>
                <div className="flex-1 flex items-center gap-2 text-sm">
                  <span className="font-bold">{SHORT[p.away_team] || p.away_team}</span>
                  <span className="text-[#334155] text-xs">@</span>
                  <span className="font-bold">{SHORT[p.home_team] || p.home_team}</span>
                </div>
                <div className="text-sm flex items-center gap-2">
                  <span className="text-blue-400 font-semibold">{SHORT[p.predicted_winner] || p.predicted_winner}</span>
                  <span className="text-[#334155] font-mono text-xs">{Math.round(p.home_win_probability * 100)}%</span>
                </div>
                <div className="w-12 text-right">
                  {isCorrect === true && <span className="text-emerald-400 font-bold">O</span>}
                  {isCorrect === false && <span className="text-red-400 font-bold">X</span>}
                  {isCorrect === null && <span className="text-[#334155]">-</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
