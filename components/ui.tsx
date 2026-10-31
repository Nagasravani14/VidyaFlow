"use client";
import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
export const cx = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(" ");
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-white/10 dark:bg-navy-800/80", className)}>{children}</div>;
}
export function Progress({ value, label }: { value: number; label?: string }) {
  return <div role="progressbar" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
    <div className="h-full rounded-full bg-gradient-to-r from-sky-400 to-violet-500 transition-all" style={{ width: `${value}%` }} /></div>;
}
export const Demo = ({ text = "Demo data" }: { text?: string }) => <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-400/15 dark:text-amber-300">{text}</span>;
export function Empty({ title, hint }: { title: string; hint: string }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center dark:border-white/15"><p className="font-semibold">{title}</p><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{hint}</p></div>;
}
export function Brand({ className = "text-xl" }: { className?: string }) {
  return <Link href="/" className={cx("inline-flex items-center gap-2 font-display font-bold", className)} aria-label="VidyaFlow home">
    <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden><defs><linearGradient id="vfg" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#38bdf8" /><stop offset="1" stopColor="#8b5cf6" /></linearGradient></defs>
      <path d="M4 9l12-5 12 5-12 5z" fill="url(#vfg)" /><path d="M9 14v6c0 2 3.2 4 7 4s7-2 7-4v-6l-7 3z" fill="url(#vfg)" opacity=".75" /><circle cx="28" cy="10" r="1.8" fill="#67e8f9" /></svg>
    <span className="brand-gradient">VidyaFlow</span></Link>;
}
const btn = "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition";
export const styles = {
  primary: cx(btn, "bg-gradient-to-r from-sky-500 to-violet-600 text-white shadow-glow hover:brightness-110"),
  ghost: cx(btn, "border border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-white/20 dark:text-slate-100 dark:hover:bg-white/10"),
};
export function ButtonLink({ href, children, variant = "primary" }: { href: string; children: ReactNode; variant?: "primary" | "ghost" }) {
  return <Link href={href} className={styles[variant]}>{children}</Link>;
}
export function Tabs({ items, value, onChange }: { items: string[]; value: string; onChange: (v: string) => void }) {
  return <div role="tablist" className="flex flex-wrap gap-2">{items.map((i) => (
    <button key={i} role="tab" aria-selected={value === i} onClick={() => onChange(i)}
      className={cx("rounded-full px-4 py-1.5 text-sm font-medium transition", value === i ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20")}>{i}</button>))}</div>;
}
export function PageHead({ title, sub, demo }: { title: string; sub: string; demo?: boolean }) {
  return <div className="mb-6"><div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-2xl font-bold sm:text-3xl">{title}</h1>{demo && <Demo />}</div><p className="mt-1 text-slate-500 dark:text-slate-400">{sub}</p></div>;
}
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  const flip = () => { const n = !dark; setDark(n); document.documentElement.classList.toggle("dark", n); try { localStorage.setItem("vf-theme", n ? "dark" : "light"); } catch {} };
  return <button onClick={flip} aria-pressed={dark} aria-label="Toggle dark theme" className="rounded-full border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-white/25 dark:text-slate-100 dark:hover:bg-white/10">{dark ? "☀ Light" : "☾ Dark"}</button>;
}
