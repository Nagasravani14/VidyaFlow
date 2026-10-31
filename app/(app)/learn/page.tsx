"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Card, PageHead, Progress, Tabs, Empty, ButtonLink, cx, styles } from "@/components/ui";
import {
  fetchChapterDetail,
  fetchLessonOverview,
  fetchLessonFlashcards,
  generateQuizMCQs,
  evaluateQuizMCQ,
  ChapterItem,
  ConceptCardItem,
  LessonOverviewResponse,
  FlashcardItem,
  QuizMCQItem,
  QuizMCQEvaluateResponse,
} from "@/lib/api";

const LEARN_TABS = [
  "Lesson Overview & AI Theory Cards",
  "Interactive Flashcards",
  "In-Lesson Quick Quiz",
  "Study Guide & Objectives",
];

function LearnContent() {
  const searchParams = useSearchParams();
  const chapterIdParam = searchParams.get("chapterId") ? Number(searchParams.get("chapterId")) : null;
  const subjectIdParam = searchParams.get("subjectId") ? Number(searchParams.get("subjectId")) : null;

  // Active curriculum context from URL query params or defaults
  const boardParam = searchParams.get("board") || "TS";
  const classParam = Number(searchParams.get("class")) || 8;
  const subjectParam = searchParams.get("subject") || "Mathematics";
  const chapterTitleParam = searchParams.get("chapter") || "";

  const [activeTab, setActiveTab] = useState(LEARN_TABS[0]);
  const [chapter, setChapter] = useState<ChapterItem | null>(null);
  const [isLoadingChapter, setIsLoadingChapter] = useState(true);

  // Tab 1: AI Theory Cards State
  const [conceptCards, setConceptCards] = useState<ConceptCardItem[]>([]);
  const [overviewData, setOverviewData] = useState<LessonOverviewResponse | null>(null);
  const [isLoadingCards, setIsLoadingCards] = useState(false);

  // Tab 2: Interactive Flashcards State
  const [flashcards, setFlashcards] = useState<FlashcardItem[]>([]);
  const [currentFcIndex, setCurrentFcIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isLoadingFc, setIsLoadingFc] = useState(false);

  // Tab 3: In-Lesson Quick Quiz State
  const [quizQuestions, setQuizQuestions] = useState<QuizMCQItem[]>([]);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<(string | null)[]>([]);
  const [quizEvaluations, setQuizEvaluations] = useState<(QuizMCQEvaluateResponse | null)[]>([]);
  const [isLoadingQuiz, setIsLoadingQuiz] = useState(false);
  const [quizScore, setQuizScore] = useState(0);

  // Derive final display title
  const chapterTitle =
    chapterTitleParam ||
    chapter?.title ||
    (chapterIdParam ? `Chapter ${chapterIdParam}` : "Linear Equations in One Variable");

  // Load Chapter Detail from DB
  useEffect(() => {
    let mounted = true;
    async function loadChapter() {
      setIsLoadingChapter(true);
      if (chapterIdParam) {
        const detail = await fetchChapterDetail(chapterIdParam);
        if (mounted && detail) {
          setChapter(detail);
        }
      }
      if (mounted) setIsLoadingChapter(false);
    }
    loadChapter();
    return () => {
      mounted = false;
    };
  }, [chapterIdParam]);

  // Load Concept Cards when Tab 1 is chosen or on initial context load
  useEffect(() => {
    let mounted = true;
    async function loadCards() {
      if (conceptCards.length > 0) return;
      setIsLoadingCards(true);
      try {
        const data = await fetchLessonOverview({
          board: boardParam,
          class_num: classParam,
          subject: subjectParam,
          chapter: chapterTitle,
        });
        if (mounted && data) {
          setOverviewData(data);
          setConceptCards(data.concept_cards || []);
        }
      } catch (e) {
        console.error("Failed to load concept cards:", e);
      } finally {
        if (mounted) setIsLoadingCards(false);
      }
    }
    if (activeTab === LEARN_TABS[0]) {
      loadCards();
    }
  }, [activeTab, boardParam, classParam, subjectParam, chapterTitle, conceptCards.length]);

  // Load Flashcards when Tab 2 is active
  useEffect(() => {
    let mounted = true;
    async function loadFc() {
      if (flashcards.length > 0) return;
      setIsLoadingFc(true);
      try {
        const data = await fetchLessonFlashcards({
          board: boardParam,
          class_num: classParam,
          subject: subjectParam,
          chapter: chapterTitle,
        });
        if (mounted && data && data.length > 0) {
          setFlashcards(data);
          setCurrentFcIndex(0);
          setIsFlipped(false);
        }
      } catch (e) {
        console.error("Failed to load flashcards:", e);
      } finally {
        if (mounted) setIsLoadingFc(false);
      }
    }
    if (activeTab === LEARN_TABS[1]) {
      loadFc();
    }
  }, [activeTab, boardParam, classParam, subjectParam, chapterTitle, flashcards.length]);

  // Load Quick Quiz when Tab 3 is active
  useEffect(() => {
    let mounted = true;
    async function loadQuiz() {
      if (quizQuestions.length > 0) return;
      setIsLoadingQuiz(true);
      try {
        const data = await generateQuizMCQs({
          board: boardParam,
          class_num: classParam,
          subject: subjectParam,
          chapter: chapterTitle,
          count: 10,
        });
        if (mounted && data && data.length > 0) {
          setQuizQuestions(data);
          setSelectedAnswers(new Array(data.length).fill(null));
          setQuizEvaluations(new Array(data.length).fill(null));
          setCurrentQIndex(0);
          setQuizScore(0);
        }
      } catch (e) {
        console.error("Failed to load quick quiz:", e);
      } finally {
        if (mounted) setIsLoadingQuiz(false);
      }
    }
    if (activeTab === LEARN_TABS[2]) {
      loadQuiz();
    }
  }, [activeTab, boardParam, classParam, subjectParam, chapterTitle, quizQuestions.length]);

  // Quick Quiz answer selection handler
  const handleSelectQuizOption = async (optionStr: string) => {
    if (selectedAnswers[currentQIndex] !== null) return; // already answered
    const currentQ = quizQuestions[currentQIndex];
    if (!currentQ) return;

    // Optimistically update selection
    const nextAnswers = [...selectedAnswers];
    nextAnswers[currentQIndex] = optionStr;
    setSelectedAnswers(nextAnswers);

    // Call evaluate API
    try {
      const evalResp = await evaluateQuizMCQ({
        question_id: currentQ.id,
        selected_option: optionStr,
        correct_option: currentQ.correct_option,
      });

      const nextEvals = [...quizEvaluations];
      nextEvals[currentQIndex] = evalResp;
      setQuizEvaluations(nextEvals);

      if (evalResp.correct) {
        setQuizScore((prev) => prev + 1);
      }
    } catch (err) {
      console.warn("Quiz evaluation error:", err);
    }
  };

  const handleRegenerateQuiz = async () => {
    setIsLoadingQuiz(true);
    try {
      const data = await generateQuizMCQs({
        board: boardParam,
        class_num: classParam,
        subject: subjectParam,
        chapter: chapterTitle,
        count: 10,
      });
      if (data && data.length > 0) {
        setQuizQuestions(data);
        setSelectedAnswers(new Array(data.length).fill(null));
        setQuizEvaluations(new Array(data.length).fill(null));
        setCurrentQIndex(0);
        setQuizScore(0);
      }
    } finally {
      setIsLoadingQuiz(false);
    }
  };

  // Practice button link passing full active chapter context query params
  const practiceLink = `/practice?board=${boardParam}&class=${classParam}&subject=${encodeURIComponent(
    subjectParam
  )}&chapter=${encodeURIComponent(chapterTitle)}&chapterId=${chapterIdParam || ""}&subjectId=${subjectIdParam || ""}`;

  return (
    <>
      {/* Chapter Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHead
          title={chapterTitle}
          sub={`${boardParam} Board · Class ${classParam} · ${subjectParam} · Official verified curriculum.`}
        />
        <div className="flex items-center gap-2">
          <ButtonLink href="/subjects" variant="ghost">
            ← Subjects
          </ButtonLink>
          <ButtonLink href={practiceLink} variant="primary">
            ⚡ Practice Questions →
          </ButtonLink>
        </div>
      </div>

      {/* 4 Interactive Sub-Tabs */}
      <div className="mb-4 mt-2">
        <Tabs items={LEARN_TABS} value={activeTab} onChange={setActiveTab} />
      </div>

      {/* SUB-TAB 1: Lesson Overview & AI Theory Cards */}
      {activeTab === LEARN_TABS[0] && (
        <div className="space-y-5">
          {/* Top Metadata Header */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              In-Depth Chapter Analysis ({boardParam} Board · Class {classParam})
            </p>
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300">
              ✓ Grounded in Official Textbook
            </span>
          </div>

          {isLoadingCards ? (
            <div className="flex flex-col items-center justify-center p-16 text-center text-sm text-slate-500">
              <div className="mb-3 h-8 w-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent" />
              <p className="font-medium text-slate-700 dark:text-slate-300">
                AI is generating lesson overview &amp; theory cards from textbook...
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Retrieving verified curriculum passages and formulating structured concept cards
              </p>
            </div>
          ) : (
            <>
              {/* Comprehensive 3-Paragraph Chapter Summary */}
              {overviewData?.chapter_summary && (
                <Card className="border-indigo-100/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-navy-900">
                  <div className="mb-3 flex items-center justify-between border-b border-slate-100 pb-3 dark:border-white/5">
                    <div className="flex items-center gap-2">
                      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-100 text-sm text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300">
                        📖
                      </span>
                      <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                        Comprehensive Curriculum Summary: {chapterTitle}
                      </h3>
                    </div>
                    <span className="text-[11px] font-medium text-slate-400">
                      Official Syllabus Scope
                    </span>
                  </div>
                  <div className="space-y-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                    {overviewData.chapter_summary.split("\n\n").map((para, pIdx) => (
                      <p key={pIdx} className="text-justify">
                        {para}
                      </p>
                    ))}
                  </div>
                </Card>
              )}

              {/* 5-8 Detailed Key Concept Cards */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-display text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                    Key Concept Breakdown Cards ({conceptCards.length} Concepts)
                  </h4>
                  <span className="text-xs text-slate-400">Definitions · Formulas · Applications</span>
                </div>

                {conceptCards.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {conceptCards.map((card, idx) => (
                      <Card
                        key={card.id || idx}
                        className="flex flex-col justify-between border-slate-200/80 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-white/10 dark:bg-navy-900/90"
                      >
                        <div className="space-y-3">
                          <div className="flex items-start justify-between gap-2 border-b border-slate-100 pb-2.5 dark:border-white/5">
                            <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                              {card.title}
                            </h3>
                            <span className="shrink-0 rounded bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                              Concept {idx + 1}
                            </span>
                          </div>

                          <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                            {card.summary}
                          </p>

                          {card.definition && (
                            <div className="rounded-lg border border-slate-100 bg-slate-50/80 p-2.5 text-xs dark:border-white/5 dark:bg-navy-950/40">
                              <span className="font-semibold text-slate-900 dark:text-white">
                                📌 Formal Definition:{" "}
                              </span>
                              <span className="text-slate-700 dark:text-slate-300">
                                {card.definition}
                              </span>
                            </div>
                          )}

                          {card.formula && (
                            <div className="rounded-lg bg-indigo-50/70 p-2.5 dark:bg-indigo-950/30">
                              <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-800 dark:text-indigo-300">
                                📐 Primary Formula / Law:
                              </span>
                              <p className="mt-0.5 font-mono text-xs font-medium text-indigo-950 dark:text-indigo-200">
                                {card.formula}
                              </p>
                            </div>
                          )}

                          {card.real_world_example && (
                            <div className="rounded-lg bg-emerald-50/60 p-2.5 text-xs text-emerald-950 dark:bg-emerald-950/20 dark:text-emerald-200">
                              <span className="font-semibold text-emerald-800 dark:text-emerald-300">
                                🌍 Real-World Application:{" "}
                              </span>
                              {card.real_world_example}
                            </div>
                          )}

                          {card.key_points && card.key_points.length > 0 && (
                            <div className="space-y-1 border-t border-slate-100 pt-2.5 dark:border-white/5">
                              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                                Core Takeaways:
                              </p>
                              <ul className="list-disc space-y-1 pl-4 text-xs text-slate-600 dark:text-slate-300">
                                {card.key_points.map((pt, pIdx) => (
                                  <li key={pIdx}>{pt}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>

                        {card.source_reference && (
                          <div className="mt-3 border-t border-slate-100 pt-2 text-[11px] text-slate-400 dark:border-white/5">
                            📖 Reference: {card.source_reference}
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                ) : (
                  <Card className="p-8 text-center text-sm text-slate-500">
                    No concept cards available for this topic yet.
                  </Card>
                )}
              </div>
            </>
          )}

          {/* Prescribed Next Step & Recommended Learning Path */}
          {overviewData?.prescribed_next_step && (
            <Card className="border-indigo-200 bg-gradient-to-r from-indigo-50/80 via-white to-sky-50/60 p-5 shadow-sm dark:border-indigo-800/60 dark:from-indigo-950/40 dark:via-navy-900 dark:to-sky-950/30">
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-base text-white shadow-md">
                  🎯
                </span>
                <div className="flex-1 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                      Prescribed Next Step &amp; Adaptive Learning Path
                    </h4>
                    <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-300">
                      AI Tutor Recommended
                    </span>
                  </div>
                  <p className="text-sm font-medium text-indigo-950 dark:text-indigo-200">
                    {overviewData.prescribed_next_step}
                  </p>
                  {overviewData.recommended_learning_path &&
                    overviewData.recommended_learning_path.length > 0 && (
                      <div className="mt-3 border-t border-indigo-100/80 pt-2.5 dark:border-white/10">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Recommended Progression:
                        </p>
                        <ol className="mt-1.5 list-decimal space-y-1 pl-4 text-xs text-slate-700 dark:text-slate-300">
                          {overviewData.recommended_learning_path.map((step, sIdx) => (
                            <li key={sIdx}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                </div>
              </div>
            </Card>
          )}

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <button
              onClick={() => setActiveTab(LEARN_TABS[1])}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-navy-800 dark:text-slate-300"
            >
              🃏 Review Active Recall Flashcards (8+ Cards) →
            </button>
            <ButtonLink href={practiceLink} variant="primary">
              Take Chapter Practice Questions →
            </ButtonLink>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: Interactive Flashcards */}
      {activeTab === LEARN_TABS[1] && (
        <div className="mx-auto max-w-2xl space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Active Recall Flashcards
            </p>
            <span className="text-xs text-slate-500">
              Card {flashcards.length > 0 ? currentFcIndex + 1 : 0} of {flashcards.length}
            </span>
          </div>

          {isLoadingFc ? (
            <div className="flex items-center justify-center p-16 text-sm text-slate-500">
              <div className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
              Loading interactive flashcards...
            </div>
          ) : flashcards.length > 0 ? (
            <>
              {/* Flip Card Container */}
              <div
                onClick={() => setIsFlipped(!isFlipped)}
                className="group relative min-h-[260px] cursor-pointer rounded-2xl border border-indigo-200/80 bg-gradient-to-br from-white to-indigo-50/40 p-8 shadow-md transition-all duration-300 hover:border-indigo-400 hover:shadow-lg dark:border-indigo-800/60 dark:from-navy-900 dark:to-indigo-950/40"
              >
                <div className="flex items-center justify-between">
                  <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300">
                    🏷️ {flashcards[currentFcIndex]?.concept_tag || flashcards[currentFcIndex]?.concept || chapterTitle}
                  </span>
                  <span className="text-xs text-indigo-600 underline group-hover:text-indigo-800 dark:text-indigo-400">
                    {isFlipped ? "↺ Flip to Question" : "↻ Click to Reveal Answer"}
                  </span>
                </div>

                <div className="mt-8 flex min-h-[120px] flex-col justify-center text-center">
                  {!isFlipped ? (
                    <div>
                      <span className="mb-2 block text-xs font-semibold uppercase tracking-widest text-slate-400">
                        Active Recall Question
                      </span>
                      <h3 className="font-display text-xl font-semibold text-slate-900 dark:text-white">
                        {flashcards[currentFcIndex]?.front}
                      </h3>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <span className="mb-1 block text-xs font-semibold uppercase tracking-widest text-emerald-600 dark:text-emerald-400">
                        Answer &amp; Syllabus Principle
                      </span>
                      <p className="text-base font-medium leading-relaxed text-slate-800 dark:text-slate-100">
                        {flashcards[currentFcIndex]?.back}
                      </p>
                      {flashcards[currentFcIndex]?.summary && (
                        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                          💡 Key takeaway: {flashcards[currentFcIndex]?.summary}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <p className="mt-6 text-center text-xs text-slate-400">
                  Tip: Test yourself aloud before flipping!
                </p>
              </div>

              {/* Navigation Controls */}
              <div className="flex items-center justify-between pt-2">
                <button
                  disabled={currentFcIndex === 0}
                  onClick={() => {
                    setCurrentFcIndex((prev) => Math.max(0, prev - 1));
                    setIsFlipped(false);
                  }}
                  className={cx(styles.ghost, "disabled:opacity-40")}
                >
                  ← Previous Card
                </button>
                <button
                  onClick={() => setIsFlipped(!isFlipped)}
                  className="rounded-xl border border-indigo-200 bg-white px-4 py-2 text-xs font-semibold text-indigo-700 shadow-sm transition hover:bg-indigo-50 dark:border-white/10 dark:bg-navy-800 dark:text-indigo-300"
                >
                  {isFlipped ? "Show Question" : "Show Answer"}
                </button>
                <button
                  disabled={currentFcIndex >= flashcards.length - 1}
                  onClick={() => {
                    setCurrentFcIndex((prev) => Math.min(flashcards.length - 1, prev + 1));
                    setIsFlipped(false);
                  }}
                  className={cx(styles.primary, "disabled:opacity-40")}
                >
                  Next Card →
                </button>
              </div>
            </>
          ) : (
            <Card className="p-8 text-center text-sm text-slate-500">
              No flashcards available for this topic yet.
            </Card>
          )}
        </div>
      )}

      {/* SUB-TAB 3: In-Lesson Quick Quiz */}
      {activeTab === LEARN_TABS[2] && (
        <div className="mx-auto max-w-2xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                In-Lesson Chapter Check ({chapterTitle})
              </p>
              <p className="text-xs text-slate-400">
                Score: {quizScore} / {quizQuestions.length}
              </p>
            </div>
            <button
              onClick={handleRegenerateQuiz}
              disabled={isLoadingQuiz}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-white/10 dark:bg-navy-800 dark:text-slate-300"
            >
              🔄 Refresh Questions
            </button>
          </div>

          {isLoadingQuiz ? (
            <div className="flex items-center justify-center p-16 text-sm text-slate-500">
              <div className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
              Generating interactive quiz for {chapterTitle}...
            </div>
          ) : quizQuestions.length > 0 ? (
            (() => {
              const currentQ = quizQuestions[currentQIndex];
              const selectedOpt = selectedAnswers[currentQIndex];
              const currentEval = quizEvaluations[currentQIndex];

              return (
                <Card className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">
                      Question {currentQIndex + 1} of {quizQuestions.length}
                    </span>
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                      RAG Verified
                    </span>
                  </div>

                  <h3 className="font-display text-lg font-semibold text-slate-900 dark:text-white">
                    {currentQ.question}
                  </h3>

                  <div className="grid gap-2.5">
                    {currentQ.options.map((opt, optIdx) => {
                      const isChosen = selectedOpt === opt;
                      const isCorrectChoice =
                        selectedOpt !== null &&
                        (opt === currentQ.correct_option ||
                          optIdx === currentQ.correct_option_index);
                      const isWrongChoice = isChosen && !currentEval?.correct;

                      return (
                        <button
                          key={opt + optIdx}
                          onClick={() => handleSelectQuizOption(opt)}
                          disabled={selectedOpt !== null}
                          className={cx(
                            "rounded-xl border p-3.5 text-left text-sm font-medium transition",
                            isCorrectChoice
                              ? "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
                              : isWrongChoice
                              ? "border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
                              : isChosen
                              ? "border-indigo-500 bg-indigo-50 text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-200"
                              : "border-slate-200 hover:border-indigo-400 hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
                          )}
                        >
                          <span className="mr-2 inline-block h-5 w-5 rounded-full border border-slate-300 text-center text-xs leading-5 dark:border-white/20">
                            {String.fromCharCode(65 + optIdx)}
                          </span>
                          {opt}
                        </button>
                      );
                    })}
                  </div>

                  {/* Instant Feedback & Solution */}
                  {selectedOpt !== null && (
                    <div
                      className={cx(
                        "rounded-xl p-3.5 text-sm",
                        currentEval?.correct
                          ? "bg-emerald-50 text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200"
                          : "bg-rose-50 text-rose-900 dark:bg-rose-950/30 dark:text-rose-200"
                      )}
                    >
                      <p className="font-semibold">
                        {currentEval?.correct ? "✓ Correct!" : "✗ Not quite."}
                      </p>
                      <p className="mt-1 text-xs opacity-90">
                        {currentQ.solution || currentEval?.explanation}
                      </p>
                    </div>
                  )}

                  {/* Question Navigator */}
                  <div className="flex items-center justify-between border-t border-slate-100 pt-3 dark:border-white/5">
                    <button
                      disabled={currentQIndex === 0}
                      onClick={() => setCurrentQIndex((prev) => prev - 1)}
                      className={cx(styles.ghost, "disabled:opacity-40")}
                    >
                      Previous
                    </button>
                    {currentQIndex < quizQuestions.length - 1 ? (
                      <button
                        onClick={() => setCurrentQIndex((prev) => prev + 1)}
                        className={styles.primary}
                      >
                        Next Question →
                      </button>
                    ) : (
                      <ButtonLink href={practiceLink} variant="primary">
                        Complete Practice Set →
                      </ButtonLink>
                    )}
                  </div>
                </Card>
              );
            })()
          ) : (
            <Card className="p-8 text-center text-sm text-slate-500">
              No questions found for this topic.
            </Card>
          )}
        </div>
      )}

      {/* SUB-TAB 4: Study Guide & Objectives */}
      {activeTab === LEARN_TABS[3] && (
        <Card className="space-y-4">
          <div>
            <h2 className="font-display text-xl font-semibold text-slate-900 dark:text-white">
              Official Syllabus &amp; Learning Objectives
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Verified curricular standards for {boardParam} Board Class {classParam} {subjectParam}.
            </p>
          </div>

          <div className="rounded-xl bg-slate-50 p-4 dark:bg-white/5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Prescribed Chapter Objectives
            </p>
            {chapter?.learning_objectives && chapter.learning_objectives.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm text-slate-700 dark:text-slate-300">
                {chapter.learning_objectives.map((obj) => (
                  <li key={obj.id || obj.description}>
                    <b>{obj.code}:</b> {obj.description} (Taxonomy: {obj.bloom_taxonomy_level})
                  </li>
                ))}
              </ul>
            ) : (
              <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm text-slate-700 dark:text-slate-300">
                <li>Master key terminologies, statutory definitions, and theoretical laws.</li>
                <li>Derive formulas, check dimensional homogeneity, and state boundary assumptions.</li>
                <li>Solve multi-step numerical and analytical problems aligned to board examinations.</li>
              </ul>
            )}
          </div>

          <div className="mt-6 flex flex-wrap gap-3 border-t border-slate-100 pt-4 dark:border-white/5">
            <ButtonLink href={`/coach`} variant="ghost">
              💬 Ask AI Coach about {chapterTitle}
            </ButtonLink>
            <ButtonLink href={practiceLink} variant="primary">
              ⚡ Launch Full Practice Exam
            </ButtonLink>
          </div>
        </Card>
      )}
    </>
  );
}

export default function Learn() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-sm text-slate-500">
          Loading Chapter Study Room...
        </div>
      }
    >
      <LearnContent />
    </Suspense>
  );
}
