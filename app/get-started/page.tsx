"use client";
import { useState, useEffect } from "react";
import { boards, classes, languages, roles, subjects as defaultSubjects } from "@/lib/data";
import { Brand, ButtonLink, Card, Progress, ThemeToggle, cx, styles } from "@/components/ui";
import { fetchSubjects } from "@/lib/api";

const steps = ["Role", "Board & class", "Language", "Subjects", "Review"];

export default function GetStarted() {
  const [step, setStep] = useState(0);
  const [role, setRole] = useState("");
  const [board, setBoard] = useState<string>(boards[0]);
  const [cls, setCls] = useState(8);
  const [lang, setLang] = useState("English");
  const [subs, setSubs] = useState<string[]>([]);
  const [availableSubjects, setAvailableSubjects] = useState<string[]>(defaultSubjects);

  // Dynamically load subjects when board or class changes
  useEffect(() => {
    let mounted = true;
    async function loadSubjects() {
      const boardCode = board.toLowerCase().includes("icse") ? "ICSE" : "TELANGANA_STATE_BOARD";
      const live = await fetchSubjects({ boardCode, classGrade: cls });
      if (!mounted) return;
      if (live && live.length > 0) {
        setAvailableSubjects(live.map((s) => s.name));
      } else {
        setAvailableSubjects(defaultSubjects);
      }
    }
    loadSubjects();
    return () => {
      mounted = false;
    };
  }, [board, cls]);

  const target = roles.find((r) => r.id === role)?.href ?? "/dashboard";
  const ok = [!!role, true, true, subs.length > 0, true][step];
  const choice = (on: boolean) =>
    cx(
      "rounded-xl border p-4 text-left transition",
      on
        ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500 dark:bg-indigo-400/10"
        : "border-slate-200 hover:border-indigo-300 dark:border-white/10"
    );

  return (
    <div className="mx-auto min-h-screen max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <Brand />
        <ThemeToggle />
      </div>
      <Card>
        <p className="text-sm text-slate-500">
          Step {step + 1} of {steps.length}: {steps[step]}
        </p>
        <div className="mb-6 mt-2">
          <Progress value={((step + 1) / steps.length) * 100} label="Setup progress" />
        </div>
        {step === 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {roles.map((r) => (
              <button
                key={r.id}
                aria-pressed={role === r.id}
                onClick={() => setRole(r.id)}
                className={choice(role === r.id)}
              >
                <b>{r.label}</b>
                <p className="text-sm text-slate-600 dark:text-slate-400">{r.desc}</p>
              </button>
            ))}
          </div>
        )}
        {step === 1 && (
          <div className="space-y-4">
            <label className="block text-sm font-semibold">
              Board
              <select
                value={board}
                onChange={(e) => setBoard(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 dark:border-white/20 dark:bg-navy-900"
              >
                {boards.map((b) => (
                  <option key={b}>{b}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-semibold">
              Class
              <select
                value={cls}
                onChange={(e) => setCls(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 dark:border-white/20 dark:bg-navy-900"
              >
                {classes.map((c) => (
                  <option key={c} value={c}>
                    Class {c}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        {step === 2 && (
          <div className="grid gap-3 sm:grid-cols-3">
            {languages.map((l) => (
              <button
                key={l}
                aria-pressed={lang === l}
                onClick={() => setLang(l)}
                className={choice(lang === l)}
              >
                <b>{l}</b>
              </button>
            ))}
          </div>
        )}
        {step === 3 && (
          <div>
            <p className="mb-3 text-sm">Pick at least one subject.</p>
            <div className="grid gap-3 sm:grid-cols-3">
              {availableSubjects.map((s) => {
                const on = subs.includes(s);
                return (
                  <button
                    key={s}
                    aria-pressed={on}
                    onClick={() => setSubs(on ? subs.filter((x) => x !== s) : [...subs, s])}
                    className={choice(on)}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {step === 4 && (
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            {[
              ["Role", roles.find((r) => r.id === role)?.label],
              ["Board", board],
              ["Class", `Class ${cls}`],
              ["Language", lang],
              ["Subjects", subs.join(", ")],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-slate-50 p-3 dark:bg-white/5">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
        )}
        <div className="mt-6 flex justify-between">
          <button
            disabled={step === 0}
            onClick={() => setStep(step - 1)}
            className={cx(styles.ghost, "disabled:opacity-40")}
          >
            Back
          </button>
          {step < 4 ? (
            <button
              disabled={!ok}
              onClick={() => setStep(step + 1)}
              className={cx(styles.primary, "disabled:opacity-40")}
            >
              Next
            </button>
          ) : (
            <ButtonLink href={target}>Open my workspace</ButtonLink>
          )}
        </div>
        {step === 4 && (
          <p className="mt-3 text-xs text-slate-500">
            Choices are kept on this page only; no account is created in this prototype.
          </p>
        )}
      </Card>
    </div>
  );
}
