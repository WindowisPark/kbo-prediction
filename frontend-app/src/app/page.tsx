"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { TEAMS as TEAM_MAP, getTeam, type TeamMeta } from "@/lib/teams";
import { API_URL } from "@/lib/config";
import { useAuth } from "@/components/AuthProvider";
import { TierGate, BlurredValue } from "@/components/TierGate";

const TEAM_IDS = ["KIA","KT","LG","NC","SSG","두산","롯데","삼성","Heroes","한화"];

// 하위 호환 — 기존 TEAM_META 참조를 getTeam()으로 대체
const TEAM_META = TEAM_MAP;

interface DebateEntry {
  agent: string; model: string; round: number | string;
  probability?: number; confidence?: string; content: string;
}
interface Prediction {
  home_team: string; away_team: string;
  predicted_winner: string; home_win_probability: number | null;
  confidence: string; key_factors: string[]; reasoning: string | null;
  model_probabilities: { xgboost: number; elo: number; ensemble: number; ai_combined: number } | null;
  debate_log: DebateEntry[] | null;
  tier?: "free" | "basic" | "pro";
}

function PredictingIndicator() {
  const [step, setStep] = useState(0);
  const steps = [
    "맥락 수집 중...",
    "ML 모델 실행 중...",
    "에이전트 분석 중...",
    "다각도 검토 R1...",
    "다각도 검토 R2...",
    "결과 종합 중...",
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setStep(s => (s + 1) % steps.length);
    }, 8000);
    return () => clearInterval(interval);
  }, [steps.length]);

  return (
    <span className="flex items-center justify-center gap-2">
      <span className="w-3 h-3 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
      <span className="text-cyan-400">{steps[step]}</span>
    </span>
  );
}

function AgentBadge({ model }: { model: string }) {
  const isGPT = model.includes("openai");
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
      isGPT ? "bg-emerald-900/40 text-emerald-400 border border-emerald-800/50"
            : "bg-violet-900/40 text-violet-400 border border-violet-800/50"
    }`}>
      {model.split("/").pop()}
    </span>
  );
}

function ConfBadge({ confidence }: { confidence: string }) {
  const map: Record<string, string> = {
    high: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    medium: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    low: "bg-red-500/10 text-red-400 border-red-500/30",
  };
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium uppercase tracking-wider ${map[confidence] || map.medium}`}>
      {confidence}
    </span>
  );
}

function ModelBar({ prob, label, color }: { prob: number; label: string; color: string }) {
  const pct = Math.round(prob * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="w-16 text-xs text-[#64748b] font-mono">{label}</span>
      <div className="flex-1 h-1.5 bg-[#1e293b] rounded-full overflow-hidden">
        <div className={`h-full rounded-full animate-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-xs font-mono text-[#94a3b8]">{pct}%</span>
    </div>
  );
}

function DebateTimeline({ log }: { log: DebateEntry[] }) {
  const [open, setOpen] = useState(false);
  const phases = [
    { label: "Phase 1: 독립 분석", entries: log.filter(e => e.round === 0) },
    { label: "Phase 2: 토론", entries: log.filter(e => typeof e.round === "number" && e.round > 0) },
    { label: "Phase 3: 종합", entries: log.filter(e => e.round === "final") },
  ];

  return (
    <div className="mt-6">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm text-[#94a3b8] hover:text-white transition group">
        <span className={`transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
        <span>에이전트 토론 과정</span>
        <span className="text-xs text-[#64748b]">({log.length} entries)</span>
      </button>
      {open && (
        <div className="mt-4 space-y-6">
          {phases.map((phase, pi) => (
            phase.entries.length > 0 && (
              <div key={pi}>
                <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wider mb-3 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  {phase.label}
                </div>
                <div className="space-y-3 pl-4 border-l border-[#1e293b]">
                  {phase.entries.map((e, i) => (
                    <div key={i} className="bg-[#111827] rounded-xl p-4 border border-[#1e293b] card-hover">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className="font-semibold text-sm text-white">{e.agent}</span>
                        <AgentBadge model={e.model} />
                        {e.probability != null && (
                          <span className="text-xs font-mono text-blue-400">{Math.round(e.probability * 100)}%</span>
                        )}
                        {e.confidence && <ConfBadge confidence={e.confidence} />}
                      </div>
                      <p className="text-sm text-[#94a3b8] whitespace-pre-wrap leading-relaxed">{e.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}

function PredictionResult({ p }: { p: Prediction }) {
  const { user } = useAuth();
  const tier = p.tier || user?.tier || "free";
  const homeProb = p.home_win_probability;
  const awayProb = homeProb != null ? 1 - homeProb : null;
  const isHomeWin = p.predicted_winner === p.home_team;
  const winnerMeta = TEAM_META[p.predicted_winner] || { name: p.predicted_winner, color: "#2563eb", short: p.predicted_winner };
  const probHidden = homeProb == null;

  return (
    <div className="space-y-6">
      {/* 스코어보드 */}
      <div className="bg-[#111827] rounded-2xl border border-[#1e293b] overflow-hidden glow-blue">
        {/* 상단 그라디언트 바 */}
        <div className="h-1 bg-gradient-to-r from-blue-600 via-cyan-500 to-orange-500" />

        <div className="p-8">
          {/* 팀 대결 */}
          <div className="flex items-center justify-between mb-8">
            <div className={`text-center flex-1 transition-opacity ${isHomeWin ? "opacity-40" : ""}`}>
              <Image src={getTeam(p.away_team).emblem} alt={p.away_team} width={64} height={64}
                     className="mx-auto mb-3 drop-shadow-lg" />
              <div className="text-xl font-bold">{TEAM_META[p.away_team]?.name || p.away_team}</div>
              <div className="text-xs text-[#64748b] mt-1">AWAY</div>
              <div className="text-3xl font-black font-mono mt-2 gradient-text-orange">
                <BlurredValue value={awayProb != null ? `${Math.round(awayProb * 100)}%` : "??"} blurred={probHidden} placeholder="52%" />
              </div>
            </div>

            <div className="px-6 flex flex-col items-center gap-2">
              <div className="text-[#334155] text-4xl font-black">VS</div>
              <div className="w-px h-8 bg-[#1e293b]" />
            </div>

            <div className={`text-center flex-1 transition-opacity ${!isHomeWin ? "opacity-40" : ""}`}>
              <Image src={getTeam(p.home_team).emblem} alt={p.home_team} width={64} height={64}
                     className="mx-auto mb-3 drop-shadow-lg" />
              <div className="text-xl font-bold">{TEAM_META[p.home_team]?.name || p.home_team}</div>
              <div className="text-xs text-[#64748b] mt-1">HOME</div>
              <div className="text-3xl font-black font-mono mt-2 gradient-text">
                <BlurredValue value={homeProb != null ? `${Math.round(homeProb * 100)}%` : "??"} blurred={probHidden} placeholder="48%" />
              </div>
            </div>
          </div>

          {/* 승리 예측 배너 */}
          <div className="text-center py-4 rounded-xl border border-[#1e293b] bg-[#0a0e1a]">
            <div className="text-sm text-[#64748b] mb-1">AI 분석 결과</div>
            <div className="text-2xl font-black" style={{ color: winnerMeta.color }}>
              {winnerMeta.name}
            </div>
            <div className="mt-2">
              <ConfBadge confidence={p.confidence} />
            </div>
          </div>
        </div>
      </div>

      {/* ML 모델 + 요인 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* ML 모델 출력 */}
        <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-5">
          <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wider mb-4">ML Models (Home Win %)</div>
          <TierGate tier={tier as "free"|"basic"|"pro"} requiredTier="pro" placeholder={
            <div className="space-y-3">
              <ModelBar prob={0.55} label="XGBoost" color="bg-gradient-to-r from-blue-600 to-blue-400" />
              <ModelBar prob={0.48} label="ELO" color="bg-gradient-to-r from-cyan-600 to-cyan-400" />
              <ModelBar prob={0.52} label="Ensemble" color="bg-gradient-to-r from-violet-600 to-violet-400" />
            </div>
          }>
            {p.model_probabilities ? (
              <div className="space-y-3">
                <ModelBar prob={p.model_probabilities.xgboost} label="XGBoost" color="bg-gradient-to-r from-blue-600 to-blue-400" />
                <ModelBar prob={p.model_probabilities.elo} label="ELO" color="bg-gradient-to-r from-cyan-600 to-cyan-400" />
                <ModelBar prob={p.model_probabilities.ensemble} label="Ensemble" color="bg-gradient-to-r from-violet-600 to-violet-400" />
                <div className="pt-2 mt-2 border-t border-[#1e293b]">
                  <ModelBar prob={p.model_probabilities.ai_combined} label="AI 종합" color="bg-gradient-to-r from-orange-500 to-amber-400" />
                </div>
              </div>
            ) : (
              <div className="text-sm text-[#475569]">Pro 플랜에서 확인 가능</div>
            )}
          </TierGate>
        </div>

        {/* 핵심 요인 */}
        <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-5">
          <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wider mb-4">Key Factors</div>
          <div className="space-y-2">
            {(p.key_factors || []).map((f, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="w-1 h-1 rounded-full bg-orange-500" />
                <span className="text-sm text-[#94a3b8]">{f}</span>
              </div>
            ))}
          </div>
          {p.reasoning != null && (
            <div className="mt-4 pt-4 border-t border-[#1e293b]">
              <p className="text-sm text-[#64748b] leading-relaxed">
                {p.reasoning}
                {p.reasoning && p.reasoning.endsWith("...") && (
                  <a href="/mypage" className="ml-1 text-cyan-400 hover:text-cyan-300 text-xs">
                    전문 보기 →
                  </a>
                )}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 토론 과정 */}
      {p.debate_log && p.debate_log.length > 0 ? (
        <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-5">
          <DebateTimeline log={p.debate_log} />
        </div>
      ) : (
        <TierGate tier={tier as "free"|"basic"|"pro"} requiredTier="pro" placeholder={
          <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-5">
            <div className="text-sm text-[#64748b]">에이전트 토론 과정 (3 agents, 2 rounds)</div>
          </div>
        }>
          <div />
        </TierGate>
      )}
    </div>
  );
}

interface LineupBatter { order: string; position: string; name: string; }
interface LineupPitcher { name: string; role: string; }
interface LineupData {
  available: boolean;
  away_lineup?: LineupBatter[]; home_lineup?: LineupBatter[];
  away_pitchers?: LineupPitcher[]; home_pitchers?: LineupPitcher[];
  away_starter?: string; home_starter?: string;
  message?: string;
}

function LineupPanel({ data, gameId, onClose }: { data: LineupData; gameId: string; onClose: () => void }) {
  if (!data.available) {
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center" onClick={onClose}>
        <div className="bg-[#111827] rounded-2xl border border-[#1e293b] p-8 max-w-md text-center" onClick={e => e.stopPropagation()}>
          <div className="text-xl mb-2">&#9918;</div>
          <div className="text-[#94a3b8]">{data.message || "라인업 미공개"}</div>
          <button onClick={onClose} className="mt-4 text-sm text-blue-400 hover:text-blue-300">닫기</button>
        </div>
      </div>
    );
  }

  // 선발 라인업만 (교체 제외 — order 1~9 첫 등장)
  const getStarters = (lineup: LineupBatter[]) => {
    const seen = new Set<string>();
    return lineup.filter(b => {
      if (seen.has(b.order)) return false;
      seen.add(b.order);
      return true;
    }).slice(0, 9);
  };

  const awayStarters = getStarters(data.away_lineup || []);
  const homeStarters = getStarters(data.home_lineup || []);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#0a0e1a] rounded-2xl border border-[#1e293b] max-w-3xl w-full max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
        <div className="h-1 bg-gradient-to-r from-blue-600 via-cyan-500 to-orange-500" />
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold">Lineup</h3>
            <button onClick={onClose} className="text-[#64748b] hover:text-white text-xl">&times;</button>
          </div>

          {/* 선발투수 */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 text-center">
              <div className="text-xs text-[#64748b] uppercase tracking-wider mb-1">Away SP</div>
              <div className="text-lg font-bold text-orange-400">{data.away_starter || "-"}</div>
            </div>
            <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 text-center">
              <div className="text-xs text-[#64748b] uppercase tracking-wider mb-1">Home SP</div>
              <div className="text-lg font-bold text-blue-400">{data.home_starter || "-"}</div>
            </div>
          </div>

          {/* 타자 라인업 */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Away", starters: awayStarters, color: "text-orange-400" },
              { label: "Home", starters: homeStarters, color: "text-blue-400" },
            ].map(side => (
              <div key={side.label} className="bg-[#111827] rounded-xl border border-[#1e293b] p-4">
                <div className="text-xs text-[#64748b] uppercase tracking-wider mb-3">{side.label} Lineup</div>
                <div className="space-y-1.5">
                  {side.starters.map((b, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span className="w-5 text-center font-mono text-[#64748b]">{b.order}</span>
                      <span className={`w-8 text-center text-xs font-mono ${side.color}`}>{b.position}</span>
                      <span className="text-[#f1f5f9]">{b.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

interface TodayGame {
  away_team: string; home_team: string; time: string;
  away_score: number | null; home_score: number | null;
  status: string; date: string; game_id: string;
  stadium?: string;
  away_starter?: string; home_starter?: string;
  away_rank?: number; home_rank?: number;
  prediction?: Prediction | null; error?: string; note?: string;
}

function TodayGameCard({ game, onSelect, onLineup, onPredict }: {
  game: TodayGame; onSelect: (p: Prediction) => void;
  onLineup: (gameId: string) => void;
  onPredict: (game: TodayGame) => void;
}) {
  const away = TEAM_META[game.away_team] || { name: game.away_team, color: "#666", short: game.away_team };
  const home = TEAM_META[game.home_team] || { name: game.home_team, color: "#666", short: game.home_team };
  const pred = game.prediction as Prediction | undefined;
  const isFinished = game.status === "final";

  return (
    <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 card-hover cursor-pointer"
         onClick={() => pred && onSelect(pred)}>
      {/* 헤더: 시간 + 구장 + 상태 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#94a3b8] font-mono">{game.time}</span>
          {game.stadium && (
            <span className="text-[11px] text-[#64748b] bg-[#1e293b] px-2 py-0.5 rounded">{game.stadium}</span>
          )}
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider ${
          isFinished ? "bg-[#1e293b] text-[#64748b]"
          : game.status === "in_progress" ? "bg-green-500/10 text-green-400 border border-green-500/30 flex items-center gap-1.5"
          : "bg-blue-500/10 text-blue-400 border border-blue-500/30"
        }`}>
          {isFinished ? "Final" : game.status === "in_progress" ? (<><span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" /><span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" /></span>Live</>) : "Upcoming"}
        </span>
      </div>

      {/* 팀 VS 팀 */}
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-2">
          <Image src={getTeam(game.away_team).emblem} alt={game.away_team} width={36} height={36} />
          <div>
            <div className="text-sm font-bold">{away.short}</div>
            {isFinished && <div className="text-lg font-mono font-black">{game.away_score}</div>}
          </div>
        </div>

        <div className="text-[#475569] text-sm font-black">VS</div>

        <div className="flex-1 flex items-center gap-2 justify-end text-right">
          <div>
            <div className="text-sm font-bold">{home.short}</div>
            {isFinished && <div className="text-lg font-mono font-black">{game.home_score}</div>}
          </div>
          <Image src={getTeam(game.home_team).emblem} alt={game.home_team} width={36} height={36} />
        </div>
      </div>

      {/* 선발투수 */}
      {(game.away_starter || game.home_starter) && (
        <div className="mt-3 pt-3 border-t border-[#1e293b]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-[#475569] bg-orange-500/10 px-1.5 py-0.5 rounded">SP</span>
              <span className="text-xs text-orange-300 font-semibold">{game.away_starter || "TBD"}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-blue-300 font-semibold">{game.home_starter || "TBD"}</span>
              <span className="text-[10px] text-[#475569] bg-blue-500/10 px-1.5 py-0.5 rounded">SP</span>
            </div>
          </div>
        </div>
      )}

      {/* 예측 결과 미니 */}
      {pred && (
        <div className="mt-3 pt-3 border-t border-[#1e293b] flex items-center justify-between">
          <div className="text-xs">
            <span className="text-[#64748b]">AI 분석: </span>
            <span className="font-bold text-blue-400">
              {TEAM_META[pred.predicted_winner]?.short || pred.predicted_winner}
            </span>
          </div>
          {pred.home_win_probability != null && (
            <div className="flex items-center gap-2">
              <div className="w-16 h-1.5 bg-[#1e293b] rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-blue-600 to-cyan-500 rounded-full"
                     style={{ width: `${Math.round(pred.home_win_probability * 100)}%` }} />
              </div>
              <span className="text-xs font-mono text-[#94a3b8]">{Math.round(pred.home_win_probability * 100)}%</span>
            </div>
          )}
        </div>
      )}
      {game.error && (
        <div className="mt-3 pt-3 border-t border-[#1e293b] text-xs text-red-400">{game.error}</div>
      )}

      {/* 버튼 영역 — 종료 경기는 Lineup만 */}
      <div className="mt-3 flex flex-col sm:flex-row gap-2">
        {!isFinished && !pred && (
          <button
            onClick={(e) => { e.stopPropagation(); onPredict(game); }}
            disabled={game.status === "predicting"}
            className="flex-1 text-xs font-semibold text-white bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:from-[#1e293b] disabled:to-[#1e293b] disabled:text-[#64748b] py-2 rounded-lg transition-all uppercase tracking-wider"
          >
            {game.status === "predicting" ? (
              <PredictingIndicator />
            ) : "Analyze"}
          </button>
        )}
        {pred && (
          <button
            onClick={(e) => { e.stopPropagation(); onSelect(pred); }}
            className="flex-1 text-xs font-semibold text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 py-2 rounded-lg border border-blue-500/30 transition-all"
          >
            상세 보기
          </button>
        )}
        {game.game_id && (
          <button
            onClick={(e) => { e.stopPropagation(); onLineup(game.game_id); }}
            className={`text-xs text-[#94a3b8] hover:text-cyan-400 bg-[#0a0e1a] hover:bg-[#1a2236] px-4 py-2 rounded-lg border border-[#1e293b] transition-all ${isFinished && !pred ? "flex-1" : ""}`}
          >
            Lineup
          </button>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState("");

  // 경기 일정
  const [todayGames, setTodayGames] = useState<TodayGame[]>([]);
  const [todayDate, setTodayDate] = useState("");
  const [currentDateId, setCurrentDateId] = useState("");
  const [prevDate, setPrevDate] = useState("");
  const [nextDate, setNextDate] = useState("");
  const [todayLoading, setTodayLoading] = useState(true);
  const [predictingAll, setPredictingAll] = useState(false);
  const [predictingIds, setPredictingIds] = useState<Set<string>>(new Set());

  // 라인업
  const [lineupData, setLineupData] = useState<LineupData | null>(null);
  const [lineupGameId, setLineupGameId] = useState("");

  // 토스트
  const [toasts, setToasts] = useState<{id: number; message: string; type: "success"|"error"}[]>([]);
  const addToast = (message: string, type: "success" | "error" = "success") => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  };

  // 결과 스크롤 ref
  const resultRef = useRef<HTMLDivElement>(null);

  // 예측 진행 중 페이지 이탈 방지
  useEffect(() => {
    const hasActive = predictingIds.size > 0 || predictingAll;
    const handler = (e: BeforeUnloadEvent) => {
      if (hasActive) { e.preventDefault(); }
    };
    if (hasActive) {
      window.addEventListener("beforeunload", handler);
      return () => window.removeEventListener("beforeunload", handler);
    }
  }, [predictingIds, predictingAll]);

  // 분석 결과 표시 시 스크롤
  useEffect(() => {
    if (prediction && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [prediction]);

  // 결과 로컬 캐시 저장/복원
  useEffect(() => {
    const cached = localStorage.getItem(`kbo_games_${currentDateId}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        // 캐시된 예측 결과가 있으면 복원
        setTodayGames(prev => prev.map(g => {
          const cachedGame = parsed.find((c: TodayGame) => c.game_id === g.game_id);
          return cachedGame?.prediction ? { ...g, prediction: cachedGame.prediction } : g;
        }));
      } catch { /* ignore */ }
    }
  }, [currentDateId, todayLoading]);

  // 예측 결과가 바뀔 때 캐시 저장
  useEffect(() => {
    if (currentDateId && todayGames.some(g => g.prediction)) {
      localStorage.setItem(`kbo_games_${currentDateId}`, JSON.stringify(todayGames));
    }
  }, [todayGames, currentDateId]);

  const loadGames = (dateParam?: string) => {
    setTodayLoading(true);
    setPrediction(null);
    const url = dateParam
      ? `${API_URL}/today?date=${dateParam}`
      : `${API_URL}/today`;
    fetch(url)
      .then(r => r.json())
      .then(d => {
        setTodayGames(d.games || []);
        setTodayDate(d.game_date_text || "");
        setCurrentDateId(d.game_date || "");
        setPrevDate(d.prev_date || "");
        setNextDate(d.next_date || "");
        setTodayLoading(false);
      })
      .catch(() => setTodayLoading(false));
  };

  useEffect(() => { loadGames(); }, []);

  const fetchLineup = async (gameId: string) => {
    try {
      const res = await fetch(`${API_URL}/game/${gameId}/lineup`);
      const data = await res.json();
      setLineupData(data);
      setLineupGameId(gameId);
    } catch {
      setLineupData({ available: false, message: "라인업 로딩 실패" });
      setLineupGameId(gameId);
    }
  };

  const handlePredictSingle = async (game: TodayGame) => {
    setPredictingIds(prev => new Set(prev).add(game.game_id));
    setError("");
    try {
      const spContext = [
        game.away_starter || game.home_starter ? "\n### 오늘 선발투수" : "",
        game.away_starter ? `- 원정 선발: **${game.away_starter}**` : "",
        game.home_starter ? `- 홈 선발: **${game.home_starter}**` : "",
        game.stadium ? `- 구장: ${game.stadium}` : "",
      ].filter(Boolean).join("\n");

      const res = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          home_team: game.home_team,
          away_team: game.away_team,
          date: game.date,
          extra_context: spContext,
          home_starter: game.home_starter || "",
          away_starter: game.away_starter || "",
        }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const pred = await res.json();
      setTodayGames(prev => prev.map(g =>
        g.game_id === game.game_id ? { ...g, prediction: pred } : g
      ));
      setPrediction(pred);
      addToast(`${getTeam(game.away_team).short} vs ${getTeam(game.home_team).short} 분석 완료`);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "분석 실패";
      setTodayGames(prev => prev.map(g =>
        g.game_id === game.game_id ? { ...g, error: errMsg } : g
      ));
      addToast(`${getTeam(game.away_team).short} vs ${getTeam(game.home_team).short}: ${errMsg}`, "error");
    } finally {
      setPredictingIds(prev => {
        const next = new Set(prev);
        next.delete(game.game_id);
        return next;
      });
    }
  };

  const handlePredictAll = async () => {
    setPredictingAll(true);
    setError("");
    // 아직 예측 안 된 경기만 병렬로
    const unpredicted = todayGames.filter(g => !g.prediction && g.status !== "final");
    const allIds = new Set(unpredicted.map(g => g.game_id));
    setPredictingIds(allIds);

    await Promise.allSettled(unpredicted.map(g => handlePredictSingle(g)));
    setPredictingAll(false);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* 히어로 */}
      {!user ? (
        <div className="mb-10 relative overflow-hidden rounded-2xl border border-[#1e293b] bg-gradient-to-br from-[#0d1117] via-[#111827] to-[#0d1117]">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(37,99,235,0.12),transparent_60%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(6,182,212,0.08),transparent_60%)]" />
          <div className="relative px-8 py-10 sm:py-14">
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-black tracking-tight mb-3">
              KBO <span className="gradient-text">AI Analyzer</span>
            </h1>
            <p className="text-[#94a3b8] text-base sm:text-lg max-w-xl mb-6">
              독자적 AI 분석 엔진이 매일 경기를 다각도로 분석합니다
            </p>
            <div className="flex flex-wrap gap-3">
              <a
                href="/login"
                className="px-6 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold hover:from-blue-500 hover:to-cyan-400 transition-all text-sm"
              >
                무료로 시작하기
              </a>
              <a
                href="/login"
                className="px-6 py-3 rounded-lg border border-[#334155] text-[#94a3b8] hover:text-white hover:border-[#475569] transition-all text-sm"
              >
                로그인
              </a>
            </div>
            <div className="flex gap-6 mt-6 text-xs text-[#475569]">
              <span>&#10003; 매일 무료 1회 분석</span>
              <span>&#10003; 가입 10초</span>
              <span>&#10003; 카드 등록 불필요</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-black tracking-tight mb-2">
            KBO <span className="gradient-text">AI Analyzer</span>
          </h1>
          <p className="text-[#64748b] text-sm sm:text-lg">
            독자적 AI 분석 엔진 기반 경기 분석
          </p>
        </div>
      )}

      {/* 경기 일정 */}
      <div className="mb-10">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-lg sm:text-xl font-bold">
              KBO <span className="gradient-text-orange">Games</span>
            </h2>
            {/* 날짜 네비게이션 */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => prevDate && loadGames(prevDate)}
                disabled={!prevDate || todayLoading}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#1e293b] hover:bg-[#334155] disabled:opacity-30 text-[#94a3b8] hover:text-white transition text-sm"
              >
                &lt;
              </button>
              <button
                onClick={() => loadGames()}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#1e293b] hover:bg-[#334155] text-[#94a3b8] hover:text-white transition"
              >
                Today
              </button>
              <button
                onClick={() => nextDate && loadGames(nextDate)}
                disabled={!nextDate || todayLoading}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#1e293b] hover:bg-[#334155] disabled:opacity-30 text-[#94a3b8] hover:text-white transition text-sm"
              >
                &gt;
              </button>
              {/* 캘린더 날짜 점프 */}
              <input
                type="date"
                value={currentDateId ? `${currentDateId.slice(0,4)}-${currentDateId.slice(4,6)}-${currentDateId.slice(6,8)}` : ""}
                onChange={(e) => e.target.value && loadGames(e.target.value.replace(/-/g, ""))}
                className="bg-[#1e293b] text-[#94a3b8] text-xs font-mono px-2 py-1.5 rounded-lg border border-[#334155] hover:border-blue-500/50 focus:border-blue-500 focus:outline-none cursor-pointer [color-scheme:dark] w-[130px]"
              />
            </div>
            {/* 날짜 + 요일 표시 */}
            {currentDateId && (() => {
              const d = new Date(`${currentDateId.slice(0,4)}-${currentDateId.slice(4,6)}-${currentDateId.slice(6,8)}`);
              const dayName = d.toLocaleDateString("ko-KR", { weekday: "short" });
              const dayNum = d.getDay();
              const dayColor = dayNum === 0 ? "text-red-400" : dayNum === 6 ? "text-blue-400" : "text-[#94a3b8]";
              return (
                <span className="text-sm font-mono text-[#64748b]">
                  {todayDate} <span className={`font-semibold ${dayColor}`}>({dayName})</span>
                </span>
              );
            })()}
          </div>
          <button onClick={handlePredictAll} disabled={predictingAll || todayGames.length === 0}
            className="w-full sm:w-auto bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 disabled:from-[#1e293b] disabled:to-[#1e293b] disabled:text-[#64748b] text-white text-sm font-bold px-5 py-2.5 rounded-xl transition-all uppercase tracking-wider">
            {predictingAll ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {predictingIds.size}경기 분석 중...
              </span>
            ) : "Analyze All"}
          </button>
        </div>

        {todayLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-[#111827] rounded-xl border border-[#1e293b] p-4 animate-pulse">
                <div className="flex justify-between mb-3">
                  <div className="h-4 w-20 bg-[#1e293b] rounded" />
                  <div className="h-4 w-16 bg-[#1e293b] rounded-full" />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 bg-[#1e293b] rounded-full" />
                    <div className="h-4 w-10 bg-[#1e293b] rounded" />
                  </div>
                  <div className="h-3 w-6 bg-[#1e293b] rounded" />
                  <div className="flex items-center gap-2">
                    <div className="h-4 w-10 bg-[#1e293b] rounded" />
                    <div className="w-9 h-9 bg-[#1e293b] rounded-full" />
                  </div>
                </div>
                <div className="mt-4 h-8 bg-[#1e293b] rounded-lg" />
              </div>
            ))}
          </div>
        ) : todayGames.length === 0 ? (
          <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-12 text-center">
            <div className="text-4xl mb-3 opacity-30">&#9918;</div>
            <div className="text-lg font-semibold text-[#94a3b8] mb-2">경기가 없는 날입니다</div>
            <p className="text-sm text-[#64748b] mb-5">다른 날짜의 경기를 확인해보세요.</p>
            <div className="flex justify-center gap-3">
              <button onClick={() => prevDate && loadGames(prevDate)} disabled={!prevDate}
                className="px-4 py-2 text-sm rounded-lg bg-[#1e293b] hover:bg-[#334155] text-[#94a3b8] hover:text-white transition disabled:opacity-30">
                &larr; 이전
              </button>
              <button onClick={() => nextDate && loadGames(nextDate)} disabled={!nextDate}
                className="px-4 py-2 text-sm rounded-lg bg-[#1e293b] hover:bg-[#334155] text-[#94a3b8] hover:text-white transition disabled:opacity-30">
                다음 &rarr;
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {todayGames.map((g, i) => (
              <TodayGameCard
                key={i}
                game={predictingIds.has(g.game_id) ? { ...g, status: "predicting" } : g}
                onSelect={setPrediction}
                onLineup={fetchLineup}
                onPredict={handlePredictSingle}
              />
            ))}
          </div>
        )}
        {error && <p className="mt-3 text-red-400 text-sm text-center">{error}</p>}
      </div>

      {/* 결과 */}
      {prediction && (
        <div ref={resultRef} className="animate-fadeInUp">
          <div className="flex items-center justify-between mb-4 sticky top-16 z-10 bg-[#0a0e1a]/95 backdrop-blur-md py-3 -mx-6 px-6 border-b border-[#1e293b]">
            <h2 className="text-base sm:text-lg font-bold">
              분석 결과: {getTeam(prediction.away_team).short} vs {getTeam(prediction.home_team).short}
            </h2>
            <button onClick={() => { setPrediction(null); window.scrollTo({ top: 0, behavior: "smooth" }); }}
              className="flex items-center gap-1.5 text-sm text-[#94a3b8] hover:text-white bg-[#1e293b] hover:bg-[#334155] px-3 py-1.5 rounded-lg transition active:scale-95">
              &times; 닫기
            </button>
          </div>
          <PredictionResult p={prediction} />
        </div>
      )}

      {/* 라인업 모달 */}
      {lineupData && (
        <LineupPanel data={lineupData} gameId={lineupGameId} onClose={() => setLineupData(null)} />
      )}

      {/* 토스트 알림 */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <div key={t.id}
            className={`px-4 py-3 rounded-xl border backdrop-blur-sm animate-fadeInUp text-sm font-medium shadow-xl ${
              t.type === "success"
                ? "bg-emerald-950/90 border-emerald-800/50 text-emerald-300"
                : "bg-red-950/90 border-red-800/50 text-red-300"
            }`}>
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
