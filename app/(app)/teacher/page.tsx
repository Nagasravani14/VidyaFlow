"use client";

import { useState } from "react";
import { Card, PageHead, ButtonLink, cx, styles } from "@/components/ui";
import {
  generateTeacherAssignment,
  TeacherAssignmentResponse,
} from "@/lib/api";

const BOARDS = [
  { id: "TS", label: "Telangana State Board (SCERT)" },
  { id: "ICSE", label: "ICSE Board (CISCE)" },
];

const CLASSES = [6, 7, 8, 9, 10];

const SUBJECTS_BY_BOARD: Record<string, string[]> = {
  TS: ["Mathematics", "Physical Science", "Biological Science", "Social Studies"],
  ICSE: ["Mathematics", "Physical Science", "Biological Science", "Social Studies"],
};

const CHAPTER_SAMPLES: Record<string, string[]> = {
  Mathematics: [
    "Algebraic Expressions and Identities",
    "Real Numbers and Trigonometry",
    "Linear Equations in One Variable",
    "Quadratic Equations and Matrices",
    "Knowing Our Numbers",
  ],
  "Physical Science": [
    "Refraction of Light at Curved Surfaces",
    "Force and Pressure",
    "Current Electricity and Electromagnetism",
    "Laws of Motion",
    "Playing with Magnets",
  ],
  "Biological Science": [
    "Cell - The Basic Unit of Life",
    "Life Processes: Nutrition and Respiration",
    "Photosynthesis and Respiration",
    "Genetics: Mendel's Laws and DNA",
    "Our Food and Its Components",
  ],
  "Social Studies": [
    "India: Relief Features and Water Resources",
    "The Indian Constitution",
    "First War of Independence and UN Organization",
    "Globe - Model of the Earth",
    "Democratic Government and Constitution",
  ],
};

const SAMPLE_STUDENTS = [
  { name: "Aarav Sharma", score: 88, status: "Mastered" },
  { name: "Bhavana Reddy", score: 64, status: "Needs Review" },
  { name: "Chaitanya Rao", score: 92, status: "Mastered" },
  { name: "Divya Patel", score: 58, status: "Critical Attention" },
  { name: "Eshwar Varma", score: 76, status: "Steady Progress" },
  { name: "Fatima Begum", score: 84, status: "Mastered" },
];

export default function TeacherPortal() {
  const [board, setBoard] = useState("TS");
  const [classNum, setClassNum] = useState(8);
  const [subject, setSubject] = useState("Mathematics");
  const [chapter, setChapter] = useState("Algebraic Expressions and Identities");
  const [difficulty, setDifficulty] = useState("Medium");
  const [customTitle, setCustomTitle] = useState("");

  const [assignment, setAssignment] = useState<TeacherAssignmentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showAnswerKey, setShowAnswerKey] = useState(false);
  const [copiedStatus, setCopiedStatus] = useState(false);

  // When subject changes, set default chapter
  const handleSubjectChange = (newSubj: string) => {
    setSubject(newSubj);
    const available = CHAPTER_SAMPLES[newSubj] || [];
    if (available.length > 0) {
      setChapter(available[0]);
    }
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    setCopiedStatus(false);
    try {
      const resp = await generateTeacherAssignment({
        board,
        class_num: classNum,
        subject,
        chapter,
        difficulty,
        assignment_title: customTitle.trim() || undefined,
      });
      setAssignment(resp);
      setShowAnswerKey(false);
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to generate assignment. Check backend connection.");
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (!assignment) return;
    const lines = [
      `# ${assignment.title}`,
      `**Board:** ${assignment.board} | **Class:** ${assignment.class_num} | **Subject:** ${assignment.subject} | **Chapter:** ${assignment.chapter}`,
      `**Total Marks:** ${assignment.total_marks} | **Time Allowed:** ${assignment.estimated_duration_minutes} minutes | **Difficulty:** ${assignment.difficulty}`,
      "",
      "## Instructions:",
      ...assignment.instructions.map((ins, i) => `${i + 1}. ${ins}`),
      "",
      "---",
      "## Section A: Multiple Choice Questions (5 Marks)",
      ...(assignment.section_a || assignment.section_a_mcqs).map((q) => `Q${q.q_num}. ${q.question} [${q.marks} Mark]\n${q.options.join("\n")}\n`),
      "---",
      "## Section B: Short Answer Questions (10 Marks)",
      ...(assignment.section_b || assignment.section_b_short_answers).map((q) => `Q${q.q_num}. ${q.question} [${q.marks} Marks]\n`),
      "---",
      "## Section C: Conceptual / HOTS Questions (10 Marks)",
      ...(assignment.section_c || assignment.section_c_hots).map((q) => `Q${q.q_num}. ${q.question} [${q.marks} Marks]\n${(q.sub_parts || []).map((p) => `   - ${p}`).join("\n")}\n`),
    ];

    if (showAnswerKey && assignment.teacher_answer_key) {
      lines.push(
        "",
        "===",
        "## CONFIDENTIAL TEACHER ANSWER KEY & MARKING SCHEME",
        "### Section A Answers:",
        ...assignment.teacher_answer_key.section_a.map((k) => `Q${k.q_num}: Correct: ${k.answer} (${k.explanation})`),
        "",
        "### Section B Marking Rubric:",
        ...assignment.teacher_answer_key.section_b.map((k) => `Q${k.q_num}: ${k.model_answer}\nRubric: ${k.marking_scheme}`),
        "",
        "### Section C Marking Rubric:",
        ...assignment.teacher_answer_key.section_c.map((k) => `Q${k.q_num}: ${k.model_answer}\nRubric: ${k.marking_scheme}`)
      );
    }

    navigator.clipboard.writeText(lines.join("\n"));
    setCopiedStatus(true);
    setTimeout(() => setCopiedStatus(false), 2500);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 dark:border-white/10">
        <div>
          <PageHead
            title="Teacher Portal & Assessment Hub"
            sub="Generate 1-click curriculum-grounded homework packets, track student mastery heatmaps, and export answer keys."
          />
        </div>
        <div className="flex items-center gap-2">
          <ButtonLink href="/subjects" variant="ghost">
            Curriculum Browser
          </ButtonLink>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300">
            ✓ Teacher Role Active
          </span>
        </div>
      </div>

      {/* 1-Click Assignment Generator Form */}
      <Card className="border-indigo-200/80 bg-white shadow-sm dark:border-white/10 dark:bg-navy-900/90">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-white/5">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-sm text-white shadow-sm">
              ⚡
            </span>
            <h2 className="font-display text-lg font-semibold text-slate-900 dark:text-white">
              1-Click AI Homework &amp; Quiz Generator
            </h2>
          </div>
          <span className="text-xs text-slate-400">
            Strictly Grounded in Board Textbooks via Local RAG
          </span>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Board Selector */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Board
            </label>
            <select
              value={board}
              onChange={(e) => setBoard(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 text-sm font-medium text-slate-900 shadow-sm focus:border-indigo-500 dark:border-white/20 dark:bg-navy-800 dark:text-white"
            >
              {BOARDS.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.label}
                </option>
              ))}
            </select>
          </div>

          {/* Class Grade */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Class Grade
            </label>
            <select
              value={classNum}
              onChange={(e) => setClassNum(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 text-sm font-medium text-slate-900 shadow-sm focus:border-indigo-500 dark:border-white/20 dark:bg-navy-800 dark:text-white"
            >
              {CLASSES.map((c) => (
                <option key={c} value={c}>
                  Class {c}
                </option>
              ))}
            </select>
          </div>

          {/* Subject */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Subject
            </label>
            <select
              value={subject}
              onChange={(e) => handleSubjectChange(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 text-sm font-medium text-slate-900 shadow-sm focus:border-indigo-500 dark:border-white/20 dark:bg-navy-800 dark:text-white"
            >
              {(SUBJECTS_BY_BOARD[board] || []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {/* Difficulty */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Difficulty Tier
            </label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 text-sm font-medium text-slate-900 shadow-sm focus:border-indigo-500 dark:border-white/20 dark:bg-navy-800 dark:text-white"
            >
              <option value="Easy">Standard / Foundational</option>
              <option value="Medium">Medium / Board Level</option>
              <option value="Hard">Advanced / HOTS Focused</option>
            </select>
          </div>
        </div>

        {/* Chapter Selection / Custom Input */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Target Chapter
            </label>
            <select
              value={chapter}
              onChange={(e) => setChapter(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 text-sm font-medium text-slate-900 shadow-sm focus:border-indigo-500 dark:border-white/20 dark:bg-navy-800 dark:text-white"
            >
              {(CHAPTER_SAMPLES[subject] || ["General Chapter Unit"]).map((ch) => (
                <option key={ch} value={ch}>
                  {ch}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Custom Assignment Title (Optional)
            </label>
            <input
              type="text"
              placeholder={`e.g. Weekly Homework Packet - ${chapter}`}
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2.5 text-sm text-slate-900 shadow-sm focus:border-indigo-500 dark:border-white/20 dark:bg-navy-800 dark:text-white"
            />
          </div>
        </div>

        {errorMsg && (
          <div className="mt-3 rounded-lg bg-rose-50 p-2.5 text-xs text-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
            {errorMsg}
          </div>
        )}

        {/* Generate Button */}
        <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 dark:border-white/5">
          <span className="text-xs text-slate-500">
            Generates 5 MCQs (5m), 5 Short Answers (10m), 2 HOTS Problems (10m) + Teacher Key (25 Marks)
          </span>
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className={cx(
              styles.primary,
              "inline-flex items-center gap-2 px-5 py-2.5 shadow-md disabled:opacity-50"
            )}
          >
            {isLoading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                AI is generating 25-mark examination packet from textbook...
              </>
            ) : (
              <>⚡ 1-Click Generate Assignment Packet (25 Marks)</>
            )}
          </button>
        </div>
      </Card>

      {/* Generated Assignment Packet View */}
      {assignment && (
        <Card className="space-y-6 border-indigo-200 bg-white p-6 shadow-md dark:border-white/10 dark:bg-navy-900/90">
          {/* Assignment Header */}
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4 dark:border-white/10">
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-bold text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                  {assignment.board} Class {assignment.class_num}
                </span>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  {assignment.subject}
                </span>
                <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  {assignment.difficulty}
                </span>
              </div>
              <h2 className="mt-2 font-display text-2xl font-bold text-slate-900 dark:text-white">
                {assignment.title}
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Chapter: <b>{assignment.chapter}</b> · Maximum Marks: <b>{assignment.total_marks}</b> · Time Allowed: <b>{assignment.estimated_duration_minutes} Minutes</b>
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={copyToClipboard}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 dark:border-white/20 dark:bg-navy-800 dark:text-slate-200"
              >
                {copiedStatus ? "✓ Copied to Clipboard!" : "📋 Copy as Markdown"}
              </button>
              <button
                onClick={() => setShowAnswerKey(!showAnswerKey)}
                className={cx(
                  "inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold shadow-sm transition",
                  showAnswerKey
                    ? "bg-rose-600 text-white hover:bg-rose-700"
                    : "bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300"
                )}
              >
                {showAnswerKey ? "🔒 Hide Answer Key" : "🔑 Show Teacher Answer Key"}
              </button>
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700"
              >
                🖨️ Print Worksheet
              </button>
            </div>
          </div>

          {/* Instructions */}
          <div className="rounded-xl bg-slate-50 p-4 dark:bg-white/5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              General Instructions
            </p>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs text-slate-700 dark:text-slate-300">
              {assignment.instructions.map((ins, i) => (
                <li key={i}>{ins}</li>
              ))}
            </ul>
          </div>

          {/* SECTION A: MCQs */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2 dark:border-white/5">
              <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                Section A: Multiple Choice Questions (5 Marks)
              </h3>
              <span className="text-xs text-slate-400">1 mark each</span>
            </div>
            <div className="space-y-4">
              {assignment.section_a_mcqs.map((q) => (
                <div key={q.q_num} className="rounded-xl border border-slate-200/80 p-4 dark:border-white/10">
                  <p className="text-sm font-medium text-slate-900 dark:text-white">
                    <span className="font-bold text-indigo-600 dark:text-indigo-400">Q{q.q_num}.</span> {q.question}
                  </p>
                  <div className="mt-2.5 grid gap-2 sm:grid-cols-2 text-xs">
                    {q.options.map((opt, oIdx) => (
                      <div
                        key={oIdx}
                        className="rounded-lg bg-slate-50 p-2 text-slate-700 dark:bg-white/5 dark:text-slate-300"
                      >
                        {opt}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* SECTION B: Short Answer */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2 dark:border-white/5">
              <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                Section B: Conceptual Short Answer Questions (10 Marks)
              </h3>
              <span className="text-xs text-slate-400">5 Questions · 2 marks each</span>
            </div>
            <div className="space-y-3">
              {(assignment.section_b || assignment.section_b_short_answers).map((q) => (
                <div key={q.q_num} className="rounded-xl border border-slate-200/80 p-4 dark:border-white/10">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                      <span className="font-bold text-indigo-600 dark:text-indigo-400">Q{q.q_num}.</span> {q.question}
                    </p>
                    <span className="shrink-0 text-xs text-slate-400">[{q.marks} Marks]</span>
                  </div>
                  {q.expected_length && (
                    <p className="mt-1 text-xs italic text-slate-400">
                      Expected response: {q.expected_length}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* SECTION C: HOTS Questions */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2 dark:border-white/5">
              <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                Section C: Higher Order Thinking Skills (HOTS) &amp; Application Problems (10 Marks)
              </h3>
              <span className="text-xs text-slate-400">2 Questions · 5 marks each</span>
            </div>
            <div className="space-y-3">
              {(assignment.section_c || assignment.section_c_hots).map((q) => (
                <div key={q.q_num} className="rounded-xl border border-slate-200/80 p-4 dark:border-white/10">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                      <span className="font-bold text-indigo-600 dark:text-indigo-400">Q{q.q_num}.</span> {q.question}
                    </p>
                    <span className="shrink-0 text-xs text-slate-400">[{q.marks} Marks]</span>
                  </div>
                  {q.sub_parts && q.sub_parts.length > 0 && (
                    <ul className="mt-2 space-y-1 pl-4 text-xs text-slate-600 dark:text-slate-300">
                      {q.sub_parts.map((p, pIdx) => (
                        <li key={pIdx}>{p}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* TEACHER ANSWER KEY (CONFIDENTIAL) */}
          {showAnswerKey && (
            <div className="rounded-2xl border-2 border-dashed border-rose-300 bg-rose-50/50 p-6 dark:border-rose-800/60 dark:bg-rose-950/20">
              <div className="flex items-center justify-between border-b border-rose-200 pb-3 dark:border-rose-800/40">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🔑</span>
                  <h3 className="font-display text-lg font-bold text-rose-900 dark:text-rose-200">
                    Confidential Teacher Answer Key &amp; Step-by-Step Marking Rubric
                  </h3>
                </div>
                <span className="rounded bg-rose-200/80 px-2 py-0.5 text-xs font-semibold text-rose-900 dark:bg-rose-900/60 dark:text-rose-200">
                  Teacher Eyes Only
                </span>
              </div>

              {/* Section A Key */}
              <div className="mt-4 space-y-2">
                <p className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                  Section A Solutions:
                </p>
                <div className="grid gap-2 text-xs sm:grid-cols-2">
                  {assignment.teacher_answer_key.section_a.map((k) => (
                    <div key={k.q_num} className="rounded-lg bg-white/80 p-2.5 dark:bg-navy-800">
                      <b>Q{k.q_num}:</b> Correct Option: <code className="text-rose-700 dark:text-rose-300">{k.answer}</code>
                      <p className="mt-0.5 text-slate-600 dark:text-slate-300">{k.explanation}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Section B Key */}
              <div className="mt-4 space-y-2">
                <p className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                  Section B Model Answers &amp; Marking Breakdown:
                </p>
                <div className="space-y-2 text-xs">
                  {assignment.teacher_answer_key.section_b.map((k) => (
                    <div key={k.q_num} className="rounded-lg bg-white/80 p-3 dark:bg-navy-800">
                      <p><b>Q{k.q_num} Model Answer:</b> {k.model_answer}</p>
                      <p className="mt-1 text-emerald-700 dark:text-emerald-400">
                        <b>Marking Scheme:</b> {k.marking_scheme}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Section C Key */}
              <div className="mt-4 space-y-2">
                <p className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                  Section C HOTS Step-by-Step Solutions:
                </p>
                <div className="space-y-2 text-xs">
                  {assignment.teacher_answer_key.section_c.map((k) => (
                    <div key={k.q_num} className="rounded-lg bg-white/80 p-3 dark:bg-navy-800">
                      <p><b>Q{k.q_num} Model Solution:</b> {k.model_answer}</p>
                      <p className="mt-1 text-emerald-700 dark:text-emerald-400">
                        <b>Step-by-Step Rubric:</b> {k.marking_scheme}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Grading Rubric */}
              <div className="mt-5 border-t border-rose-200/80 pt-3 dark:border-rose-800/40">
                <p className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                  Mastery Scale &amp; Performance Feedback:
                </p>
                <div className="mt-2 grid gap-2 sm:grid-cols-4 text-xs">
                  {assignment.grading_rubric.map((r, rIdx) => (
                    <div key={rIdx} className="rounded-lg bg-white/80 p-2.5 dark:bg-navy-800">
                      <span className="font-bold text-slate-900 dark:text-white">
                        {r.grade} ({r.score_range} pts)
                      </span>
                      <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">{r.feedback}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Class Mastery Heatmap & Remedial Tracking */}
      <Card>
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-white/5">
          <div>
            <h3 className="font-display text-lg font-semibold text-slate-900 dark:text-white">
              Class Mastery Heatmap &amp; Remedial Roster
            </h3>
            <p className="text-xs text-slate-500">
              Live tracking for Class {classNum} {subject} ({board} Board)
            </p>
          </div>
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
            6 Enrolled Students
          </span>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 dark:border-white/10">
                <th className="pb-2 font-semibold">Student Name</th>
                <th className="pb-2 font-semibold">Chapter Mastery</th>
                <th className="pb-2 font-semibold">Status</th>
                <th className="pb-2 font-semibold">Prescribed Teacher Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-white/5">
              {SAMPLE_STUDENTS.map((s, idx) => (
                <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-white/5">
                  <td className="py-2.5 font-medium text-slate-900 dark:text-white">{s.name}</td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
                        <div
                          className={cx(
                            "h-full rounded-full",
                            s.score >= 80 ? "bg-emerald-500" : s.score >= 60 ? "bg-amber-400" : "bg-rose-500"
                          )}
                          style={{ width: `${s.score}%` }}
                        />
                      </div>
                      <span className="font-semibold">{s.score}%</span>
                    </div>
                  </td>
                  <td className="py-2.5">
                    <span
                      className={cx(
                        "rounded px-2 py-0.5 text-[11px] font-semibold",
                        s.score >= 80
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : s.score >= 60
                          ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                          : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                      )}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-600 dark:text-slate-300">
                    {s.score < 60
                      ? "Assign 1-click remedial packet on Chapter definitions"
                      : s.score < 80
                      ? "Recommend flashcard review on formula derivations"
                      : "Eligible for advanced HOTS Section C packet"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
