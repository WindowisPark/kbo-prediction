"use client";

import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/standings", label: "Standings" },
  { href: "/history", label: "History" },
];

export function NavLinks() {
  const pathname = usePathname();

  return (
    <div className="flex gap-1">
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
    </div>
  );
}
