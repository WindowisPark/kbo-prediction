"use client";

import { API_URL } from "./config";

// --- 토큰 저장 ---

const ACCESS_KEY = "kbo_access_token";
const REFRESH_KEY = "kbo_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// --- JWT 디코딩 (검증 없이 payload만) ---

export interface JWTPayload {
  sub: string;
  user_id: number;
  email: string;
  tier: "free" | "basic" | "pro";
  type: string;
  exp: number;
}

export function decodeToken(token: string): JWTPayload | null {
  try {
    const payload = token.split(".")[1];
    const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token);
  if (!payload) return true;
  return Date.now() / 1000 > payload.exp;
}

// --- API 호출 ---

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface AuthError {
  detail: string;
}

async function authFetch<T>(
  path: string,
  body: Record<string, unknown>
): Promise<{ data?: T; error?: string }> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (!res.ok) {
      return { error: (json as AuthError).detail || `Error ${res.status}` };
    }
    return { data: json as T };
  } catch {
    return { error: "서버에 연결할 수 없습니다" };
  }
}

export async function register(
  email: string,
  password: string,
  nickname: string
): Promise<{ success: boolean; error?: string }> {
  const { data, error } = await authFetch<TokenResponse>("/auth/register", {
    email,
    password,
    nickname,
  });
  if (error) return { success: false, error };
  setTokens(data!.access_token, data!.refresh_token);
  return { success: true };
}

export async function login(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string }> {
  const { data, error } = await authFetch<TokenResponse>("/auth/login", {
    email,
    password,
  });
  if (error) return { success: false, error };
  setTokens(data!.access_token, data!.refresh_token);
  return { success: true };
}

export async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const { data } = await authFetch<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  if (!data) {
    clearTokens();
    return false;
  }
  setTokens(data.access_token, data.refresh_token);
  return true;
}

export function logout() {
  clearTokens();
  window.location.href = "/";
}

// --- 현재 유저 정보 ---

export interface UserInfo {
  email: string;
  tier: "free" | "basic" | "pro";
  userId: number;
}

export function getCurrentUser(): UserInfo | null {
  const token = getAccessToken();
  if (!token) return null;

  if (isTokenExpired(token)) {
    // 만료된 토큰 — 리프레시는 비동기라 여기선 null 반환
    return null;
  }

  const payload = decodeToken(token);
  if (!payload) return null;

  return {
    email: payload.email,
    tier: payload.tier,
    userId: payload.user_id,
  };
}
