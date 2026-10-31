"use client";
import { useState } from "react";
import { ButtonLink, Card, Demo, Empty, PageHead, Progress } from "@/components/ui";
const subjectProgress: [string, number][] = [["Mathematics", 64], ["Science", 52], ["Social Studies", 38], ["English", 72], ["Telugu", 68]];
export default function Dashboard() {
  const [goals, setGoals] = useState([{ t: "Finish 1 lesson", d: false }, { t: "Answer 10 practice questions", d: false }, { t: "Review one weak concept", d: false }]);
  const done = goals.filter((g) => g.d).length;
  return (<>
    <PageHead title="Welcome back" sub="Pick up where you left off, or choose a new subject." />
    <div className="grid gap-5 lg:grid-cols-3">
      <Card className="bg-gradient-to-br from-indigo-600 to-violet-700 text-white lg:col-span-2 dark:from-indigo-600 dark:to-violet-700">
        <p className="text-sm text-indigo-100">Continue learning</p><h2 className="mt-1 font-display text-2xl font-bold">Linear Equations in One Variable</h2>
        <p className="mt-1 text-sm text-indigo-100">Sample lesson · about 15 min</p><div className="mt-4 max-w-sm"><Progress value={60} label="Lesson progress" /></div>
        <div className="mt-5"><ButtonLink href="/learn">Resume lesson</ButtonLink></div></Card>
      <Card><div className="flex items-center justify-between"><h2 className="font-display font-semibold">Study goals</h2><span className="text-sm">{done}/{goals.length}</span></div>
        <ul className="mt-3 space-y-2">{goals.map((g, i) => <li key={g.t}><label className="flex cursor-pointer items-center gap-2 text-sm"><input type="checkbox" checked={g.d} onChange={() => setGoals(goals.map((x, j) => j === i ? { ...x, d: !x.d } : x))} className="h-4 w-4 accent-indigo-600" /><span className={g.d ? "line-through opacity-60" : ""}>{g.t}</span></label></li>)}</ul></Card>
      <Card className="lg:col-span-2"><div className="mb-3 flex items-center gap-3"><h2 className="font-display font-semibold">Subjects</h2><Demo /></div>
        <ul className="space-y-3">{subjectProgress.map(([s, v]) => <li key={s}><div className="mb-1 flex justify-between text-sm"><span>{s}</span><span>{v}%</span></div><Progress value={v} label={s} /></li>)}</ul></Card>
      <Card><h2 className="mb-3 font-display font-semibold">Learning map</h2><p className="text-sm text-slate-600 dark:text-slate-400">See mastered concepts, weak areas and what to learn next.</p><div className="mt-4"><ButtonLink href="/map" variant="ghost">Open map</ButtonLink></div></Card>
      <Card className="lg:col-span-3"><h2 className="mb-3 font-display font-semibold">Recent activity</h2><Empty title="No activity yet" hint="Finish a lesson or a practice set and it will show up here." /></Card></div></>);
}
