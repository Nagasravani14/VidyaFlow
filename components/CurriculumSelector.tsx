"use client";
import { useState, useEffect } from "react";
import { boards as defaultBoards, classes as defaultClasses, subjects as defaultSubjects } from "@/lib/data";
import { Card, Tabs, ButtonLink } from "./ui";
import { fetchBoards, fetchSubjects, BoardItem, SubjectItem } from "@/lib/api";

export default function CurriculumSelector() {
  const [boardList, setBoardList] = useState<string[]>([...defaultBoards]);
  const [board, setBoard] = useState<string>(defaultBoards[0]);
  const [cls, setCls] = useState<number>(8);
  const [availableSubjects, setAvailableSubjects] = useState<SubjectItem[]>([]);
  const [isLive, setIsLive] = useState<boolean>(false);

  useEffect(() => {
    let mounted = true;
    async function loadCurriculumData() {
      const liveBoards = await fetchBoards();
      if (!mounted) return;

      if (liveBoards && liveBoards.length > 0) {
        setBoardList(liveBoards.map((b) => b.name));
      }

      const boardCode = board.toLowerCase().includes("icse") ? "ICSE" : "TELANGANA_STATE_BOARD";
      const subjects = await fetchSubjects({ boardCode, classGrade: cls });
      if (!mounted) return;

      if (subjects && subjects.length > 0) {
        setAvailableSubjects(subjects);
        setIsLive(true);
      } else {
        setIsLive(false);
      }
    }
    loadCurriculumData();
    return () => {
      mounted = false;
    };
  }, [board, cls]);

  const displaySubjects =
    availableSubjects.length > 0
      ? availableSubjects.map((s) => s.name)
      : defaultSubjects;

  const boardCode = board.toLowerCase().includes("icse") ? "ICSE" : "TELANGANA_STATE_BOARD";

  return (
    <Card className="mx-auto max-w-3xl">
      <div className="space-y-4">
        <div>
          <p className="mb-2 text-sm font-semibold">Board</p>
          <Tabs items={boardList} value={board} onChange={setBoard} />
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold">Class</p>
          <Tabs
            items={defaultClasses.map(String)}
            value={String(cls)}
            onChange={(v) => setCls(Number(v))}
          />
        </div>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold">Subjects available to explore</p>
            {isLive ? (
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300">
                Live Syllabus
              </span>
            ) : null}
          </div>
          <ul className="flex flex-wrap gap-2">
            {availableSubjects.length > 0
              ? availableSubjects.map((s) => (
                  <li key={s.id}>
                    <a
                      href={`/subjects?board=${boardCode}&class=${cls}&subjectId=${s.id}`}
                      className="inline-block rounded-lg bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-800 transition hover:bg-indigo-100 dark:bg-indigo-400/10 dark:text-indigo-200 dark:hover:bg-indigo-400/20"
                    >
                      {s.name} ({s.chapter_count || 0} chapters) →
                    </a>
                  </li>
                ))
              : displaySubjects.map((s) => (
                  <li
                    key={s}
                    className="rounded-lg bg-indigo-50 px-3 py-1 text-sm text-indigo-800 dark:bg-indigo-400/10 dark:text-indigo-200"
                  >
                    {s}
                  </li>
                ))}
          </ul>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400" aria-live="polite">
          Selected: {board}, Class {cls}.{" "}
          {isLive
            ? "Connected to verified curriculum database."
            : "Chapter lists are sample outlines, not the official syllabus."}
        </p>
        <div className="flex flex-wrap gap-3">
          <ButtonLink href={`/subjects?board=${boardCode}&class=${cls}`}>
            Explore Subjects &amp; Chapters
          </ButtonLink>
          <ButtonLink href="/get-started" variant="ghost">
            Guided Onboarding
          </ButtonLink>
        </div>
      </div>
    </Card>
  );
}
