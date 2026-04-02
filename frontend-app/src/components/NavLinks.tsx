"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/standings", label: "Standings" },
  { href: "/history", label: "History" },
];

const TIER_COLORS: Record<string, string> = {
  free: "text-[#94a3b8]",
  basic: "text-cyan-400",
  pro: "text-amber-400",
};

const TIER_LABELS: Record<string, string> = {
  free: "Free",
  basic: "Basic",
  pro: "Pro",
};

export function NavLinks() {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  return (
    <div className="flex items-center gap-1">
      {LINKS.map((link) => {
        const isActive = pathname === link.href;
        return (
          <a
            key={link.href}
            href={link.href}
            className={`px-4 py-2 rounded-lg text-sm transition-all ${
              isActive
                ? "text-white bg-[#1a2236] font-semibold border border-blue-500/30"
                : "text-[#94a3b8] hover:text-white hover:bg-[#1a2236]"
            }`}
          >
            {link.label}
          </a>
        );
      })}

      {/* 구분선 */}
      <div className="w-px h-6 bg-[#1e293b] mx-2" />

      {loading ? (
        <div className="w-20 h-8 rounded-lg bg-[#111827] animate-pulse" />
      ) : user ? (
        <a
          href="/mypage"
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${
            pathname === "/mypage"
              ? "bg-[#1a2236] border border-blue-500/30"
              : "hover:bg-[#1a2236]"
          }`}
        >
          <span className={`text-xs font-bold uppercase ${TIER_COLORS[user.tier]}`}>
            {TIER_LABELS[user.tier]}
          </span>
          <span className="text-white text-sm">{user.email.split("@")[0]}</span>
        </a>
      ) : (
        <a
          href="/login"
          className="px-4 py-2 rounded-lg text-sm bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-medium hover:from-blue-500 hover:to-cyan-400 transition-all"
        >
          로그인
        </a>
      )}
    </div>
  );
}
