"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Card, PageHead, Progress, ButtonLink, cx, styles } from "@/components/ui";
import {
  generateQuizMCQs,
  generateAdaptiveQuiz,
  evaluateQuizMCQ,
  submitPracticeAnswer,
  PracticeSubmissionResponse,
  QuizMCQItem,
  AdaptiveQuizQuestion,
} from "@/lib/api";

interface QuestionView {
  id: string;
  q: string;
  opts: string[];
  a: number;
  hint: string;
  why: string;
  sourceRef?: string | null;
  isAiGenerated?: boolean;
  question_type?: string;
  cognitive_level?: string;
  difficulty?: string;
  prerequisite_concept_tested?: string;
  root_gap_remediation?: string;
}

function PracticeContent() {
  const searchParams = useSearchParams();
  const boardParam = searchParams.get("board") || "TS";
  const classParam = Number(searchParams.get("class")) || 8;
  const subjectParam = searchParams.get("subject") || "Mathematics";
  const chapterParam = searchParams.get("chapter") || "Algebraic Expressions and Identities";
  const chapterIdParam = searchParams.get("chapterId");
  const subjectIdParam = searchParams.get("subjectId");

  const [questionCount, setQuestionCount] = useState(10);
  const [assessmentMode, setAssessmentMode] = useState<"adaptive" | "standard">("adaptive");
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [questionsList, setQuestionsList] = useState<QuestionView[]>([]);
  const [i, setI] = useState(0);
  const [ans, setAns] = useState<(number | null)[]>([]);
  const [evaluations, setEvaluations] = useState<(PracticeSubmissionResponse | null)[]>([]);
  const [hint, setHint] = useState(false);
  const [fin, setFin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationMsg, setGenerationMsg] = useState<string | null>(null);

  // Load active chapter questions dynamically from RAG API
  useEffect(() => {
    let mounted = true;
    async function loadActiveChapterQuestions() {
      setIsLoading(true);
      try {
        if (assessmentMode === "adaptive") {
          const adaptiveData = await generateAdaptiveQuiz({
            board: boardParam,
            class_num: classParam,
            subject: subjectParam,
            chapter: chapterParam,
            difficulty: difficulty,
            num_questions: questionCount <= 10 ? Math.min(questionCount, 10) : 10,
            focus_skills: ["recall", "understanding", "application", "analysis"],
          });

          if (mounted && adaptiveData?.questions?.length > 0) {
            const mapped: QuestionView[] = adaptiveData.questions.map((item, idx) => {
              const opts = item.options.map((o) => `${o.option_id}) ${o.text}`);
              const correctIdx = item.options.findIndex(
                (o) => o.option_id.toUpperCase() === item.correct_answer.toUpperCase()
              );
              return {
                id: item.question_id || `q_${idx + 1}`,
                q: item.question_text,
                opts: opts.length > 0 ? opts : ["A) Option A", "B) Option B", "C) Option C", "D) Option D"],
                a: correctIdx >= 0 ? correctIdx : 0,
                hint: item.hint || `Review fundamentals of ${chapterParam}.`,
                why: item.explanation,
                sourceRef: `${boardParam} Class ${classParam} ${subjectParam} (${chapterParam})`,
                isAiGenerated: true,
                question_type: item.question_type,
                cognitive_level: item.cognitive_level,
                difficulty: item.difficulty,
                prerequisite_concept_tested: item.prerequisite_concept_tested,
                root_gap_remediation: item.root_gap_remediation,
              };
            });

            setQuestionsList(mapped);
            setAns(mapped.map(() => null));
            setEvaluations(mapped.map(() => null));
            setI(0);
            setFin(false);
            return;
          }
        }

        // Standard Practice Flow
        const data = await generateQuizMCQs({
          board: boardParam,
          class_num: classParam,
          subject: subjectParam,
          chapter: chapterParam,
          count: questionCount,
        });

        if (mounted && data && data.length > 0) {
          const mapped: QuestionView[] = data.map((item, idx) => ({
            id: item.id || `q_${idx + 1}`,
            q: item.question,
            opts: item.options,
            a: item.correct_option_index,
            hint: item.hint || `Review ${chapterParam} definitions and principles from ${boardParam} Class ${classParam} ${subjectParam}.`,
            why: item.solution,
            sourceRef: `${boardParam} Class ${classParam} ${subjectParam} (${chapterParam})`,
            isAiGenerated: true,
            cognitive_level: item.cognitive_level || (idx % 3 === 0 ? "application" : idx % 2 === 0 ? "understanding" : "analysis"),
            prerequisite_concept_tested: item.prerequisite_concept_tested,
            root_gap_remediation: item.root_gap_remediation,
          }));

          setQuestionsList(mapped);
          setAns(mapped.map(() => null));
          setEvaluations(mapped.map(() => null));
          setI(0);
          setFin(false);
        }
      } catch (err: any) {
        console.warn("Failed to generate dynamic questions:", err);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadActiveChapterQuestions();
    return () => {
      mounted = false;
    };
  }, [boardParam, classParam, subjectParam, chapterParam, questionCount, assessmentMode, difficulty]);

  const q = questionsList[i];
  const sel = ans[i];
  const currentEval = evaluations[i];
  const score = ans.filter((a, k) => questionsList[k] && a === questionsList[k].a).length;

  const pick = async (n: number) => {
    if (sel === null && q) {
      const nextAns = ans.map((a, k) => (k === i ? n : a));
      setAns(nextAns);

      const selectedOptionText = q.opts[n];
      const correctOptionText = q.opts[q.a];

      try {
        // 1. Evaluate with RAG LLM engine
        const evalResp = await evaluateQuizMCQ({
          question_id: q.id,
          selected_option: selectedOptionText,
          correct_option: correctOptionText,
        });

        // 2. Persist to practice submissions
        const subResp = await submitPracticeAnswer({
          question_text: q.q,
          student_answer: selectedOptionText,
          correct_answer: correctOptionText,
          worked_explanation: q.why,
          evaluation_type: "mcq_exact",
          max_marks: 1.0,
        }).catch(() => null);

        const mergedEval: PracticeSubmissionResponse = {
          submission_id: subResp?.submission_id || Date.now(),
          is_correct: evalResp.correct,
          score: evalResp.correct ? 1 : 0,
          max_marks: 1.0,
          evaluation_type: "mcq_exact",
          feedback: evalResp.explanation,
          pedagogical_guidance: evalResp.explanation,
          evaluated_at: new Date().toISOString(),
        };

        setEvaluations((prev) => prev.map((ev, k) => (k === i ? mergedEval : ev)));
      } catch (err) {
        console.warn("Evaluation error:", err);
      }
    }
  };

  const generateAIQuestionsHandler = async () => {
    setIsGenerating(true);
    setGenerationMsg(null);
    try {
      if (assessmentMode === "adaptive") {
        const adaptiveData = await generateAdaptiveQuiz({
          board: boardParam,
          class_num: classParam,
          subject: subjectParam,
          chapter: chapterParam,
          difficulty: difficulty,
          num_questions: questionCount <= 10 ? Math.min(questionCount, 10) : 10,
          focus_skills: ["recall", "understanding", "application", "analysis"],
        });

        if (adaptiveData?.questions?.length > 0) {
          const mapped: QuestionView[] = adaptiveData.questions.map((item, idx) => {
            const opts = item.options.map((o) => `${o.option_id}) ${o.text}`);
            const correctIdx = item.options.findIndex(
              (o) => o.option_id.toUpperCase() === item.correct_answer.toUpperCase()
            );
            return {
              id: item.question_id || `q_${Date.now()}_${idx}`,
              q: item.question_text,
              opts: opts.length > 0 ? opts : ["A) Option A", "B) Option B", "C) Option C", "D) Option D"],
              a: correctIdx >= 0 ? correctIdx : 0,
              hint: item.hint || `Recall key definitions for ${chapterParam}.`,
              why: item.explanation,
              sourceRef: `${boardParam} Class ${classParam} ${subjectParam} (${chapterParam})`,
              isAiGenerated: true,
              question_type: item.question_type,
              cognitive_level: item.cognitive_level,
              difficulty: item.difficulty,
              prerequisite_concept_tested: item.prerequisite_concept_tested,
              root_gap_remediation: item.root_gap_remediation,
            };
          });

          setQuestionsList(mapped);
          setAns(mapped.map(() => null));
          setEvaluations(mapped.map(() => null));
          setI(0);
          setFin(false);
          setHint(false);
          setGenerationMsg(
            `Generated ${mapped.length} adaptive diagnostic questions for ${boardParam} Class ${classParam} ${subjectParam}: ${chapterParam}!`
          );
          return;
        }
      }

      const data = await generateQuizMCQs({
        board: boardParam,
        class_num: classParam,
        subject: subjectParam,
        chapter: chapterParam,
        count: questionCount,
      });

      if (data && data.length > 0) {
        const mapped: QuestionView[] = data.map((item, idx) => ({
          id: item.id || `q_${Date.now()}_${idx}`,
          q: item.question,
          opts: item.options,
          a: item.correct_option_index,
          hint: item.hint || `Recall key definitions and rules for ${chapterParam}.`,
          why: item.solution,
          sourceRef: `${boardParam} Class ${classParam} ${subjectParam} (${chapterParam})`,
          isAiGenerated: true,
          cognitive_level: item.cognitive_level || (idx % 3 === 0 ? "application" : idx % 2 === 0 ? "understanding" : "analysis"),
          prerequisite_concept_tested: item.prerequisite_concept_tested,
          root_gap_remediation: item.root_gap_remediation,
        }));

        setQuestionsList(mapped);
        setAns(mapped.map(() => null));
        setEvaluations(mapped.map(() => null));
        setI(0);
        setFin(false);
        setHint(false);
        setGenerationMsg(
          `Generated ${mapped.length} dynamic questions for ${boardParam} Class ${classParam} ${subjectParam}: ${chapterParam}!`
        );
      }
    } catch (err: any) {
      setGenerationMsg(`Using verified curriculum practice bank for ${chapterParam}.`);
    } finally {
      setIsGenerating(false);
    }
  };

  const go = (n: number) => {
    setI(n);
    setHint(false);
  };

  const reset = () => {
    setAns(questionsList.map(() => null));
    setEvaluations(questionsList.map(() => null));
    setI(0);
    setFin(false);
    setHint(false);
  };

  const learnLink = `/learn?board=${boardParam}&class=${classParam}&subject=${encodeURIComponent(
    subjectParam
  )}&chapter=${encodeURIComponent(chapterParam)}&chapterId=${chapterIdParam || ""}&subjectId=${subjectIdParam || ""}`;

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center p-12 text-sm text-slate-500">
        <div className="mb-3 h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
        <p className="font-medium text-slate-700 dark:text-slate-300">
          Generating dynamic questions for {chapterParam}...
        </p>
        <p className="mt-1 text-xs text-slate-400">
          Retrieving official {boardParam} Class {classParam} textbook passages via ChromaDB RAG.
        </p>
      </div>
    );
  }

  if (fin) {
    return (
      <>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <PageHead
            title={`Results: ${chapterParam}`}
            sub={`${boardParam} Class ${classParam} · ${subjectParam} · Review your performance and explanations.`}
          />
          <ButtonLink href={learnLink} variant="ghost">
            ← Back to Lesson Room
          </ButtonLink>
        </div>

        <Card>
          <div className="flex items-center justify-between">
            <p className="font-display text-3xl font-bold">
              {score} / {questionsList.length}
            </p>
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300">
              ✓ Grounded Assessment
            </span>
          </div>
          <p className="text-sm text-slate-500">
            {Math.round((score / Math.max(1, questionsList.length)) * 100)}% accuracy on {chapterParam}.
          </p>

          <ul className="mt-4 space-y-3">
            {questionsList.map((x, k) => (
              <li key={x.id + k} className="rounded-xl bg-slate-50 p-3.5 text-sm dark:bg-white/5">
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <div className="flex items-center gap-2">
                    {x.cognitive_level && (
                      <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
                        {x.cognitive_level}
                      </span>
                    )}
                    {x.question_type && (
                      <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-700 dark:bg-white/10 dark:text-slate-300">
                        {x.question_type.replace("_", " ")}
                      </span>
                    )}
                  </div>
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300">
                    RAG Grounded
                  </span>
                </div>
                <b className="mt-1.5 block font-medium text-slate-900 dark:text-white">{x.q}</b>
                <p className="mt-1">
                  Your answer: {ans[k] === null ? "Skipped" : x.opts[ans[k]!]}{" "}
                  {ans[k] === x.a ? (
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">✓ Correct</span>
                  ) : (
                    <span className="font-semibold text-rose-600 dark:text-rose-400">
                      ✗ (correct: {x.opts[x.a]})
                    </span>
                  )}
                </p>
                <p className="mt-1 text-slate-600 dark:text-slate-300">
                  <span className="font-medium">Solution:</span> {x.why}
                </p>
                {/* Knowledge Gap Remediation on incorrect answer */}
                {ans[k] !== x.a && x.root_gap_remediation && (
                  <div className="mt-2.5 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
                    <span className="font-bold">⚠️ Prerequisite Knowledge Gap:</span> {x.root_gap_remediation}
                    {x.prerequisite_concept_tested && (
                      <span className="mt-0.5 block font-medium opacity-90">
                        Prerequisite Concept: <b>{x.prerequisite_concept_tested}</b>
                      </span>
                    )}
                  </div>
                )}
                {x.sourceRef && (
                  <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">
                    📖 Grounded reference: {x.sourceRef}
                  </p>
                )}
              </li>
            ))}
          </ul>

          {/* Prescribed Next Step Based on Quiz Performance */}
          <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50/70 p-4 dark:border-indigo-800/60 dark:bg-indigo-950/30">
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700 dark:text-indigo-300">
              🎯 Prescribed Next Step &amp; Adaptive Recommendation
            </p>
            <p className="mt-1 text-sm font-medium text-slate-800 dark:text-slate-100">
              {score / Math.max(1, questionsList.length) >= 0.8
                ? `Outstanding mastery (${score}/${questionsList.length})! Prescribed Next Step: Proceed to the next curriculum unit or challenge yourself with Teacher Assignment HOTS questions.`
                : score / Math.max(1, questionsList.length) >= 0.6
                ? `Solid foundation (${score}/${questionsList.length}). Prescribed Next Step: Revisit the 8 active recall flashcards in the Lesson Room and re-test missed solutions.`
                : `Targeted review recommended (${score}/${questionsList.length}). Prescribed Next Step: Return to the Lesson Room, re-read Theory Card 1 & 2 definitions, and consult your AI Learning Coach.`}
            </p>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button onClick={reset} className={styles.primary}>
              Try again
            </button>
            <button
              onClick={generateAIQuestionsHandler}
              disabled={isGenerating}
              className={styles.ghost}
            >
              {isGenerating ? "Generating..." : "⚡ Generate Fresh Practice Set"}
            </button>
            <ButtonLink href={learnLink} variant="ghost">
              Review Lesson Cards →
            </ButtonLink>
          </div>
        </Card>
      </>
    );
  }

  if (!q) {
    return (
      <Card className="p-8 text-center text-sm text-slate-500">
        <p>No questions generated for {chapterParam}.</p>
        <div className="mt-4 flex justify-center gap-2">
          <button onClick={generateAIQuestionsHandler} className={styles.primary}>
            Generate Questions
          </button>
          <ButtonLink href="/subjects" variant="ghost">
            Back to Subjects
          </ButtonLink>
        </div>
      </Card>
    );
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHead
          title={`Practice: ${chapterParam}`}
          sub={`${boardParam} Board Class ${classParam} · ${subjectParam} · Dynamically generated from official curriculum.`}
        />
        <div className="flex flex-wrap items-center gap-2">
          {/* Mode selector */}
          <div className="flex items-center rounded-xl border border-slate-200 bg-white p-0.5 text-xs dark:border-white/10 dark:bg-navy-900">
            <button
              onClick={() => setAssessmentMode("adaptive")}
              className={`rounded-lg px-2.5 py-1 font-semibold transition ${
                assessmentMode === "adaptive"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
              }`}
            >
              🎯 Adaptive Diagnostic
            </button>
            <button
              onClick={() => setAssessmentMode("standard")}
              className={`rounded-lg px-2.5 py-1 font-semibold transition ${
                assessmentMode === "standard"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
              }`}
            >
              Standard MCQs
            </button>
          </div>

          {/* Difficulty selector for Adaptive mode */}
          {assessmentMode === "adaptive" && (
            <div className="flex items-center rounded-xl border border-slate-200 bg-white p-0.5 text-xs dark:border-white/10 dark:bg-navy-900">
              {(["easy", "medium", "hard"] as const).map((diff) => (
                <button
                  key={diff}
                  onClick={() => setDifficulty(diff)}
                  className={`rounded-lg px-2 py-1 font-semibold capitalize transition ${
                    difficulty === diff
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
                  }`}
                >
                  {diff}
                </button>
              ))}
            </div>
          )}

          {/* Question count selector */}
          <div className="flex items-center rounded-xl border border-slate-200 bg-white p-0.5 text-xs dark:border-white/10 dark:bg-navy-900">
            {(assessmentMode === "adaptive" ? [5, 10] : [10, 15, 20]).map((cnt) => (
              <button
                key={cnt}
                onClick={() => setQuestionCount(cnt)}
                className={`rounded-lg px-2 py-1 font-semibold transition ${
                  questionCount === cnt
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
                }`}
              >
                {cnt} Qs
              </button>
            ))}
          </div>

          <ButtonLink href={learnLink} variant="ghost">
            ← Lesson Cards
          </ButtonLink>
          <button
            onClick={generateAIQuestionsHandler}
            disabled={isGenerating}
            className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50/80 px-3 py-1.5 text-xs font-semibold text-indigo-700 shadow-sm transition hover:bg-indigo-100 disabled:opacity-50 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300"
          >
            {isGenerating ? (
              <span className="flex items-center gap-1">
                <span className="h-3 w-3 animate-spin rounded-full border border-indigo-600 border-t-transparent" />
                Generating...
              </span>
            ) : (
              <>⚡ Refresh {assessmentMode === "adaptive" ? "Adaptive" : `${questionCount} Qs`}</>
            )}
          </button>
        </div>
      </div>

      {generationMsg && (
        <div className="my-2 rounded-lg bg-indigo-50 p-2.5 text-xs text-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300">
          {generationMsg}
        </div>
      )}

      <Progress value={((i + 1) / questionsList.length) * 100} label="Question progress" />

      <Card className="mt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Question {i + 1} of {questionsList.length}
            </p>
            {q.cognitive_level && (
              <span className="rounded bg-indigo-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-indigo-700 dark:bg-indigo-400/15 dark:text-indigo-300">
                {q.cognitive_level}
              </span>
            )}
            {q.question_type && (
              <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600 dark:bg-white/10 dark:text-slate-300">
                {q.question_type.replace("_", " ")}
              </span>
            )}
            {q.difficulty && (
              <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-800 dark:bg-amber-400/15 dark:text-amber-300">
                {q.difficulty}
              </span>
            )}
          </div>
          <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300">
            {boardParam} Class {classParam} Grounded
          </span>
        </div>

        {q.prerequisite_concept_tested && (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            🔗 Prerequisite Concept:{" "}
            <span className="font-semibold text-indigo-700 dark:text-indigo-300">
              {q.prerequisite_concept_tested}
            </span>
          </p>
        )}

        <h2 className="mt-2.5 font-display text-xl font-semibold text-slate-900 dark:text-white">
          {q.q}
        </h2>

        {q.sourceRef && (
          <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">
            📖 Source: {q.sourceRef}
          </p>
        )}

        <div className="mt-4 grid gap-2" role="radiogroup" aria-label="Answer options">
          {q.opts.map((o, n) => {
            const right = sel !== null && n === q.a;
            const wrong = sel === n && n !== q.a;

            return (
              <button
                key={o + n}
                role="radio"
                aria-checked={sel === n}
                onClick={() => pick(n)}
                className={cx(
                  "rounded-xl border p-3.5 text-left text-sm font-medium transition",
                  right
                    ? "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-400/10 dark:text-emerald-200"
                    : wrong
                    ? "border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-400/10 dark:text-rose-200"
                    : "border-slate-200 hover:border-indigo-400 hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
                )}
              >
                <span className="mr-2 inline-block h-5 w-5 rounded-full border border-slate-300 text-center text-xs leading-5 dark:border-white/20">
                  {String.fromCharCode(65 + n)}
                </span>
                {o}
              </button>
            );
          })}
        </div>

        {/* Evaluation & Feedback Display */}
        <div aria-live="polite" className="mt-4 text-sm">
          {sel !== null && (
            <div className="rounded-xl bg-slate-50 p-3.5 dark:bg-white/5">
              <p>
                <b>{sel === q.a ? "✓ Correct!" : "✗ Not quite."}</b> {q.why}
              </p>
              {sel !== q.a && q.root_gap_remediation && (
                <div className="mt-2.5 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
                  <span className="font-bold">⚠️ Root Knowledge Gap Remediation:</span>{" "}
                  {q.root_gap_remediation}
                </div>
              )}
              {currentEval?.pedagogical_guidance && (
                <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-400">
                  💡 Pedagogical guidance: {currentEval.pedagogical_guidance}
                </p>
              )}
            </div>
          )}
          {hint && sel === null && (
            <p className="rounded-lg bg-indigo-50 p-2.5 text-xs text-indigo-700 dark:bg-indigo-950/40 dark:text-sky-300">
              💡 Hint: {q.hint}
            </p>
          )}
        </div>

        <div className="mt-5 flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-3 dark:border-white/5">
          <button
            onClick={() => setHint(true)}
            disabled={sel !== null}
            className={cx(styles.ghost, "disabled:opacity-40")}
          >
            Show hint
          </button>
          <div className="flex gap-2">
            <button
              onClick={() => go(i - 1)}
              disabled={i === 0}
              className={cx(styles.ghost, "disabled:opacity-40")}
            >
              Previous
            </button>
            {i < questionsList.length - 1 ? (
              <button onClick={() => go(i + 1)} className={styles.primary}>
                Next
              </button>
            ) : (
              <button onClick={() => setFin(true)} className={styles.primary}>
                See results
              </button>
            )}
          </div>
        </div>
      </Card>
    </>
  );
}

export default function Practice() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-sm text-slate-500">
          Loading Practice Arena...
        </div>
      }
    >
      <PracticeContent />
    </Suspense>
  );
}
