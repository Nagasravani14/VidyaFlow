import Image from "next/image";
import Link from "next/link";
import { Brand, ButtonLink, ThemeToggle } from "@/components/ui";
import CurriculumSelector from "@/components/CurriculumSelector";
import CinematicIntro, { ReplayIntroButton } from "@/components/CinematicIntro";
const features = [
  ["Concept-first learning", "Every chapter is broken into concepts with clear prerequisites, so gaps are visible early."],
  ["Adaptive learning map", "See what is mastered, what needs work and which concept to tackle next."],
  ["AI Learning Coach", "Ask for hints or simpler explanations in English, Telugu or Hindi. (Interface only in this prototype.)"],
  ["Practice with feedback", "Try questions, use hints and review every answer with a worked explanation."],
  ["Teacher tools", "Class mastery heatmaps, learning-gap lists and remedial group suggestions."],
  ["Parent view", "Strengths, improvement areas and upcoming assessments in one calm page."],
];
const flow = [["Choose", "Pick your board, class, language and subjects."], ["Learn", "Study a concept with examples and key ideas."], ["Practice", "Answer questions and get step-by-step feedback."], ["Adapt", "The map highlights what to revisit and what to learn next."]];
export default function Landing() {
  return (<div className="bg-navy-950 text-slate-100">
    <CinematicIntro />
    <header className="absolute inset-x-0 top-0 z-30"><div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-8">
      <Brand className="text-2xl" />
      <nav className="hidden gap-6 text-sm font-medium md:flex" aria-label="Sections">{[["Features", "#features"], ["How it works", "#how"], ["Curriculum", "#curriculum"], ["Roles", "#roles"]].map(([l, h]) => <a key={h} href={h} className="hover:text-sky-300">{l}</a>)}</nav>
      <div className="flex items-center gap-2"><ReplayIntroButton /><ThemeToggle /><ButtonLink href="/get-started">Get started</ButtonLink></div></div></header>

    <section className="relative flex min-h-[92vh] flex-col justify-end overflow-hidden lg:justify-center">
      <div className="relative aspect-video w-full lg:absolute lg:inset-y-0 lg:right-0 lg:aspect-auto lg:w-[78%]" style={{ WebkitMaskImage: "linear-gradient(to right, transparent, #000 28%)", maskImage: "linear-gradient(to right, transparent, #000 28%)" }}>
        <Image src="/hero-heroes.png" alt="A team of superheroes standing on a neon city rooftop at night" fill priority sizes="100vw" className="object-cover object-right" /></div>
      <div className="relative z-10 mx-auto w-full max-w-7xl px-4 pb-14 pt-8 sm:px-8 lg:pt-24">
        <div className="max-w-xl lg:max-w-[30%] lg:min-w-[22rem]">
          <p className="font-display text-5xl font-extrabold sm:text-6xl"><span className="brand-gradient">VidyaFlow</span></p>
          <h1 className="mt-3 font-display text-3xl font-bold leading-tight sm:text-4xl">Every Student Has a Superpower.</h1>
          <p className="mt-3 text-lg font-medium text-sky-200">Learn smarter. Grow stronger. Go beyond.</p>
          <p className="mt-3 text-slate-300">Adaptive learning for Classes 6–10 in the Telangana State Board and ICSE, in English, Telugu and Hindi.</p>
          <div className="mt-6 flex flex-wrap gap-3"><ButtonLink href="/get-started">Start learning</ButtonLink><ButtonLink href="/dashboard" variant="ghost">Explore the dashboard</ButtonLink></div>
          <p className="mt-4 text-xs text-slate-400">Frontend prototype. Sample data is labelled; no AI or analytics are connected.</p></div></div></section>

    <div className="bg-slate-50 text-slate-800 dark:bg-navy-900 dark:text-slate-200">
      <section id="features" className="mx-auto max-w-7xl scroll-mt-8 px-4 py-20 sm:px-8">
        <h2 className="font-display text-3xl font-bold">Built around how students actually learn</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{features.map(([t, d]) => <div key={t} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card dark:border-white/10 dark:bg-navy-800/80"><h3 className="font-display text-lg font-semibold">{t}</h3><p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{d}</p></div>)}</div></section>

      <section id="how" className="scroll-mt-8 bg-gradient-to-b from-indigo-50 to-transparent px-4 py-20 dark:from-indigo-950/40 sm:px-8"><div className="mx-auto max-w-7xl">
        <h2 className="font-display text-3xl font-bold">The VidyaFlow learning loop</h2>
        <ol className="mt-8 grid gap-4 md:grid-cols-4">{flow.map(([t, d], i) => <li key={t} className="rounded-2xl border border-indigo-200 bg-white p-5 dark:border-indigo-400/20 dark:bg-navy-800"><span className="font-display text-sm font-bold text-indigo-600 dark:text-sky-300">Step {i + 1}</span><h3 className="mt-1 text-lg font-semibold">{t}</h3><p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{d}</p></li>)}</ol></div></section>

      <section id="curriculum" className="mx-auto max-w-7xl scroll-mt-8 px-4 py-20 sm:px-8"><h2 className="mb-8 text-center font-display text-3xl font-bold">Choose your curriculum</h2><CurriculumSelector /></section>

      <section id="roles" className="mx-auto max-w-7xl scroll-mt-8 px-4 pb-20 sm:px-8"><h2 className="font-display text-3xl font-bold">One platform, four views</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[["Student", "Learning map, goals and next steps.", "/dashboard"], ["Self-Learner", "Free exploration of any chapter.", "/subjects"], ["Teacher", "Class heatmap and remedial groups.", "/teacher"], ["Parent", "Weekly insights and upcoming tests.", "/parent"]].map(([t, d, h]) => <Link key={t} href={h} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card transition hover:-translate-y-0.5 hover:border-indigo-400 dark:border-white/10 dark:bg-navy-800/80"><h3 className="font-display text-lg font-semibold">{t}</h3><p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{d}</p><span className="mt-3 inline-block text-sm font-semibold text-indigo-600 dark:text-sky-300">Preview →</span></Link>)}</div></section>

      <section className="px-4 pb-20 sm:px-8"><div className="mx-auto max-w-4xl rounded-3xl bg-gradient-to-r from-sky-500 via-indigo-600 to-violet-700 p-10 text-center text-white">
        <h2 className="font-display text-3xl font-bold">Ready to find your superpower?</h2><p className="mt-2 text-indigo-100">Set up VidyaFlow in under a minute.</p>
        <div className="mt-6"><Link href="/get-started" className="inline-flex rounded-full bg-white px-6 py-3 font-semibold text-indigo-700 hover:bg-indigo-50">Get started</Link></div></div></section>
      <footer className="border-t border-slate-200 px-4 py-8 text-sm text-slate-500 dark:border-white/10 sm:px-8"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3"><Brand className="text-lg" /><p>© VidyaFlow prototype. Learn smarter. Grow stronger. Go beyond.</p></div></footer>
    </div></div>);
}
