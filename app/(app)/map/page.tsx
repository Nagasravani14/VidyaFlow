"use client";
import { useState } from "react";
import { mapNodes, NodeState } from "@/lib/data";
import { Card, PageHead, cx } from "@/components/ui";
const style: Record<NodeState, string> = { mastered: "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-400/10 dark:text-emerald-200", weak: "border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-400/10 dark:text-amber-200", next: "border-indigo-500 bg-indigo-50 text-indigo-900 ring-2 ring-indigo-400 dark:bg-indigo-400/10 dark:text-indigo-100", locked: "border-slate-300 bg-slate-100 text-slate-600 dark:border-white/15 dark:bg-white/5 dark:text-slate-400" };
const label: Record<NodeState, string> = { mastered: "Mastered", weak: "Needs work", next: "Recommended next", locked: "Locked" };
export default function MapPage() {
  const [sel, setSel] = useState(mapNodes[3].id); const n = mapNodes.find((x) => x.id === sel)!;
  return (<><PageHead demo title="Adaptive Learning Map" sub="Concept dependencies. States shown are sample values, not calculated mastery." />
    <div className="mb-3 flex flex-wrap gap-2 text-xs">{(Object.keys(label) as NodeState[]).map((k) => <span key={k} className={cx("rounded-full border px-2.5 py-1", style[k])}>{label[k]}</span>)}</div>
    <Card><div className="flex flex-col gap-4 overflow-x-auto md:flex-row md:items-center md:gap-6">{[0, 1, 2, 3].map((lv) => <div key={lv} className="flex flex-1 flex-col gap-3">{mapNodes.filter((x) => x.level === lv).map((x) =>
      <button key={x.id} onClick={() => setSel(x.id)} aria-pressed={sel === x.id} className={cx("rounded-xl border p-3 text-left text-sm font-semibold transition", style[x.state], sel === x.id && "shadow-glow")}>{x.id}<span className="block text-xs font-normal">{label[x.state]}</span></button>)}</div>)}</div></Card>
    <Card className="mt-4"><h2 className="font-display text-lg font-semibold">{n.id}</h2><p className="text-sm">Status: {label[n.state]}</p><p className="text-sm">Requires: {n.pre.length ? n.pre.join(", ") : "Nothing (starting concept)"}</p>
      <p className="text-sm">Unlocks: {mapNodes.filter((x) => x.pre.includes(n.id)).map((x) => x.id).join(", ") || "Nothing further"}</p></Card></>);
}
