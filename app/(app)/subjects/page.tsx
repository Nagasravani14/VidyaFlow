"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ButtonLink, Card, Empty, PageHead, Progress, Tabs, cx } from "@/components/ui";
import { fetchSubjects, fetchChapters, ChapterItem, SubjectItem } from "@/lib/api";

const boardOptions = [
  { label: "Telangana State Board", code: "TELANGANA_STATE_BOARD" },
  { label: "ICSE", code: "ICSE" },
];
const classOptions = [6, 7, 8, 9, 10];

function SubjectsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Read initial board, class, and subjectId from query parameters
  const initialBoardParam = searchParams.get("board") || "TELANGANA_STATE_BOARD";
  const initialClassParam = Number(searchParams.get("class")) || 10;
  const initialSubjectIdParam = searchParams.get("subjectId")
    ? Number(searchParams.get("subjectId"))
    : null;

  const [boardCode, setBoardCode] = useState<string>(initialBoardParam);
  const [classGrade, setClassGrade] = useState<number>(initialClassParam);
  const [subjectsData, setSubjectsData] = useState<SubjectItem[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | null>(initialSubjectIdParam);
  const [q, setQ] = useState("");
  const [liveChapters, setLiveChapters] = useState<ChapterItem[]>([]);
  const [isLoadingChapters, setIsLoadingChapters] = useState(false);
  const [isLive, setIsLive] = useState(false);

  // 1. Fetch subjects when Board or Class changes
  useEffect(() => {
    let mounted = true;

    async function loadSubjects() {
      // Clear stale selection and chapters on board or class change
      setLiveChapters([]);
      setIsLoadingChapters(true);

      const live = await fetchSubjects({ boardCode, classGrade });
      if (!mounted) return;

      if (live && live.length > 0) {
        setSubjectsData(live);
        setIsLive(true);

        // Keep selected subject if valid in newly loaded list, otherwise pick first subject
        const matchesExisting = live.find((s) => s.id === selectedSubjectId);
        if (matchesExisting) {
          // Already have valid subject selected
          setIsLoadingChapters(false);
        } else {
          // Check if subjectId query param matches any of the new subjects
          const fromParam = initialSubjectIdParam
            ? live.find((s) => s.id === initialSubjectIdParam)
            : null;
          const nextSubject = fromParam || live[0];
          setSelectedSubjectId(nextSubject.id);
        }
      } else {
        setSubjectsData([]);
        setSelectedSubjectId(null);
        setIsLive(false);
        setIsLoadingChapters(false);
      }
    }

    loadSubjects();
    return () => {
      mounted = false;
    };
  }, [boardCode, classGrade]);

  // 2. Fetch chapters whenever selectedSubjectId changes
  useEffect(() => {
    let mounted = true;

    async function loadChapters() {
      if (!selectedSubjectId) {
        setLiveChapters([]);
        setIsLoadingChapters(false);
        return;
      }

      setIsLoadingChapters(true);
      const chList = await fetchChapters(selectedSubjectId, 100);
      if (!mounted) return;

      // Verify that every returned record belongs to the active subject ID
      const verifiedChapters = (chList || []).filter(
        (ch) => !ch.subject_id || ch.subject_id === selectedSubjectId
      );

      setLiveChapters(verifiedChapters);
      setIsLoadingChapters(false);
    }

    loadChapters();
    return () => {
      mounted = false;
    };
  }, [selectedSubjectId]);

  // Active subject object
  const activeSubject = subjectsData.find((s) => s.id === selectedSubjectId);
  const subjectNames = subjectsData.map((s) => s.name);
  const activeSubjectName = activeSubject?.name || "";

  // Filter chapters by search keyword
  const displayedChapters = liveChapters.filter((c) =>
    c.title.toLowerCase().includes(q.toLowerCase())
  );

  const handleSubjectChange = (subjectName: string) => {
    const found = subjectsData.find((s) => s.name === subjectName);
    if (found && found.id !== selectedSubjectId) {
      // Reset stale chapters before loading new subject
      setLiveChapters([]);
      setSelectedSubjectId(found.id);
      setQ("");
    }
  };

  const handleBoardChange = (label: string) => {
    const found = boardOptions.find((b) => b.label === label);
    if (found && found.code !== boardCode) {
      setBoardCode(found.code);
      setSelectedSubjectId(null);
      setLiveChapters([]);
      setQ("");
    }
  };

  const handleClassChange = (classNumStr: string) => {
    const num = Number(classNumStr);
    if (num !== classGrade) {
      setClassGrade(num);
      setSelectedSubjectId(null);
      setLiveChapters([]);
      setQ("");
    }
  };

  const currentBoardLabel =
    boardOptions.find((b) => b.code === boardCode)?.label || "Telangana State Board";

  return (
    <>
      <PageHead
        demo={!isLive}
        title="Subject Explorer"
        sub={
          isLive
            ? `Viewing verified chapters from ${currentBoardLabel} (Class ${classGrade}).`
            : "Select a board and class to explore official curriculum chapters."
        }
      />

      {/* Board & Class Switcher Controls */}
      <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-navy-900/80">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Education Board
            </span>
            <Tabs
              items={boardOptions.map((b) => b.label)}
              value={currentBoardLabel}
              onChange={handleBoardChange}
            />
          </div>

          <div className="space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Class Grade
            </span>
            <Tabs
              items={classOptions.map((c) => `Class ${c}`)}
              value={`Class ${classGrade}`}
              onChange={(val) => handleClassChange(val.replace("Class ", ""))}
            />
          </div>
        </div>
      </div>

      {/* Subject Tabs and Search Bar */}
      <div className="mb-5 flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {subjectNames.length > 0 ? (
            <Tabs
              items={subjectNames}
              value={activeSubjectName}
              onChange={handleSubjectChange}
            />
          ) : (
            <span className="text-sm italic text-slate-500">
              No subjects registered for this class.
            </span>
          )}

          {isLive && activeSubject && (
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300">
              ✓ Database Connected ({displayedChapters.length} Chapters in {activeSubject.name})
            </span>
          )}
        </div>

        {subjectNames.length > 0 && (
          <input
            aria-label="Search chapters"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={`Search ${activeSubjectName} chapters...`}
            className="w-full max-w-sm rounded-xl border border-slate-300 bg-white p-2.5 text-sm dark:border-white/20 dark:bg-navy-800"
          />
        )}
      </div>

      {/* Content Rendering: Loading, Empty, or Chapter Cards */}
      {isLoadingChapters ? (
        <div className="flex items-center justify-center p-12 text-sm text-slate-500">
          <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          Loading chapters for {activeSubjectName}...
        </div>
      ) : displayedChapters.length === 0 ? (
        <Empty
          title={
            q.trim()
              ? "No chapters match your search"
              : activeSubjectName
              ? `No chapters imported yet for ${activeSubjectName}`
              : "No subject selected"
          }
          hint={
            q.trim()
              ? "Try a different search keyword."
              : `Chapters for ${activeSubjectName || "this subject"} have not been populated in the current syllabus edition.`
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {displayedChapters.map((c) => (
            <Card key={c.id || c.title}>
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-semibold text-indigo-600 dark:text-sky-300">
                    Chapter {c.chapter_number}
                  </span>
                  <h3 className="font-display text-lg font-semibold">{c.title}</h3>
                </div>
                {c.verification_status === "verified" ? (
                  <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold text-sky-800 dark:bg-sky-400/15 dark:text-sky-300">
                    Official
                  </span>
                ) : null}
              </div>

              <p className="mt-1 text-sm text-slate-500">
                About {c.estimated_minutes || 90} min · Not started
              </p>

              {c.learning_objectives && c.learning_objectives.length > 0 && (
                <>
                  <p className="mt-3 text-sm font-semibold">Objectives</p>
                  <ul className="list-disc pl-5 text-sm space-y-1 text-slate-600 dark:text-slate-300">
                    {c.learning_objectives.map((o) => (
                      <li key={o.id || o.description}>{o.description}</li>
                    ))}
                  </ul>
                </>
              )}

              <div className="mt-3">
                <Progress value={0} label={`${c.title} progress`} />
              </div>

              <div className="mt-4 flex items-center justify-between">
                <ButtonLink
                  href={`/learn?chapterId=${c.id}&subjectId=${selectedSubjectId}&board=${currentBoardLabel.includes("Telangana") || currentBoardLabel.includes("TS") ? "TS" : "ICSE"}&class=${classGrade}&subject=${encodeURIComponent(activeSubjectName || "")}&chapter=${encodeURIComponent(c.title)}`}
                  variant="ghost"
                >
                  Open chapter →
                </ButtonLink>
                <span className="text-xs text-slate-400">
                  {c.topic_count ? `${c.topic_count} topics` : "1 core topic"}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

export default function Subjects() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-sm text-slate-500">
          Loading Subject Explorer...
        </div>
      }
    >
      <SubjectsContent />
    </Suspense>
  );
}
