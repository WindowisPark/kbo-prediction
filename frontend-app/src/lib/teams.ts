export interface TeamMeta {
  id: string;
  name: string;
  short: string;
  color: string;
  bgColor: string;
  emblem: string; // /emblems/{id}.svg
}

export const TEAMS: Record<string, TeamMeta> = {
  KIA:    { id: "KIA",    name: "KIA 타이거즈",    short: "KIA",  color: "#e11d48", bgColor: "#e11d4820", emblem: "/emblems/KIA.svg" },
  KT:     { id: "KT",     name: "kt wiz",          short: "KT",   color: "#000000", bgColor: "#00000020", emblem: "/emblems/KT.svg" },
  LG:     { id: "LG",     name: "LG 트윈스",       short: "LG",   color: "#c2002f", bgColor: "#c2002f20", emblem: "/emblems/LG.svg" },
  NC:     { id: "NC",     name: "NC 다이노스",      short: "NC",   color: "#1b3668", bgColor: "#1b366820", emblem: "/emblems/NC.svg" },
  SSG:    { id: "SSG",    name: "SSG 랜더스",       short: "SSG",  color: "#ce0e2d", bgColor: "#ce0e2d20", emblem: "/emblems/SSG.svg" },
  두산:   { id: "두산",    name: "두산 베어스",      short: "두산",  color: "#131230", bgColor: "#13123020", emblem: "/emblems/doosan.svg" },
  롯데:   { id: "롯데",    name: "롯데 자이언츠",   short: "롯데",  color: "#041e42", bgColor: "#041e4220", emblem: "/emblems/lotte.svg" },
  삼성:   { id: "삼성",    name: "삼성 라이온즈",   short: "삼성",  color: "#0066b3", bgColor: "#0066b320", emblem: "/emblems/samsung.svg" },
  Heroes: { id: "Heroes", name: "키움 히어로즈",    short: "키움",  color: "#570514", bgColor: "#57051420", emblem: "/emblems/kiwoom.svg" },
  한화:   { id: "한화",    name: "한화 이글스",     short: "한화",  color: "#ff6600", bgColor: "#ff660020", emblem: "/emblems/hanwha.svg" },
  키움:   { id: "Heroes", name: "키움 히어로즈",    short: "키움",  color: "#570514", bgColor: "#57051420", emblem: "/emblems/kiwoom.svg" },
};

export function getTeam(name: string): TeamMeta {
  return TEAMS[name] || { id: name, name, short: name, color: "#666", bgColor: "#66666620", emblem: "" };
}
