import { getAccessToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface TeamInfo {
  team: string;
  elo: number;
  recent_win_pct: number;
  streak: number;
}

export interface ModelProbabilities {
  xgboost: number;
  elo: number;
  bayesian: number;
}

export interface DebateEntry {
  agent: string;
  model: string;
  round: number | string;
  probability?: number;
  confidence?: string;
  content: string;
}

export interface Prediction {
  home_team: string;
  away_team: string;
  date: string;
  predicted_winner: string;
  home_win_probability: number | null;
  confidence: string;
  key_factors: string[];
  reasoning: string | null;
  model_probabilities: ModelProbabilities | null;
  debate_log: DebateEntry[] | null;
  tier?: "free" | "basic" | "pro";
}

export interface StandingsData {
  season: number;
  teams: TeamInfo[];
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...Object.fromEntries(
      Object.entries(options?.headers || {})
    ),
  };

  // JWT 토큰이 있으면 Authorization 헤더 추가
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getStandings(): Promise<StandingsData> {
  return fetchAPI("/standings");
}

export async function predictGame(
  homeTeam: string,
  awayTeam: string,
  date: string,
  extraContext?: string
): Promise<Prediction> {
  return fetchAPI("/predict", {
    method: "POST",
    body: JSON.stringify({
      home_team: homeTeam,
      away_team: awayTeam,
      date,
      extra_context: extraContext || "",
    }),
  });
}

export async function getPredictions(limit = 50) {
  return fetchAPI<{ predictions: Prediction[] }>(`/predictions?limit=${limit}`);
}

export async function getTeams(): Promise<{ teams: string[] }> {
  return fetchAPI("/teams");
}

export async function getAccuracy() {
  return fetchAPI<{
    total_predictions: number;
    correct: number;
    accuracy: number;
    by_confidence: Record<string, { total: number; correct: number; accuracy: number }>;
  }>("/accuracy");
}
