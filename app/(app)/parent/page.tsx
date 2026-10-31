"use client";

import { useState, useEffect } from "react";
import { Card, PageHead, Progress, ButtonLink, cx } from "@/components/ui";
import { fetchParentDashboardStats } from "@/lib/api";

export default function ParentPortal() {
  const [stats, setStats] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadStats() {
      try {
        const data = await fetchParentDashboardStats();
        if (mounted && data) {
          setStats(data);
        }
      } catch (err) {
        console.warn("Using parent portal fallback:", err);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    loadStats();
    return () => {
      mounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center text-sm text-slate-500">
        <div className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
        Loading Parent Portal &amp; Student Analytics...
      </div>
    );
  }

  const profile = stats?.student_profile || {
    name: "Arjun Rao",
    student_id: "VF-2026-9042",
    board: "ICSE",
    class_grade: 9,
    school: "Hyderabad Public School",
  };

  const overview = stats?.study_overview || {
    total_study_time_hours: 34.5,
    weekly_study_time_hours: 6.2,
    total_quizzes_completed: 18,
    overall_accuracy_percentage: 84.5,
    streak_days: 12,
  };

  const weakChapters = stats?.weak_chapters || [];
  const strongChapters = stats?.strong_chapters || [];
  const assignments = stats?.completed_assignments || [];
  const quizzes = stats?.recent_quiz_history || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 dark:border-white/10">
        <div>
          <PageHead
            title="Parent Portal & Student Analytics"
            sub={`Real-time learning insights and academic progress for ${profile.name} (${profile.board} Class ${profile.class_grade}).`}
          />
        </div>
        <div className="flex items-center gap-2">
          <ButtonLink href="/learn" variant="ghost">
            View Lesson Room
          </ButtonLink>
          <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-300">
            👨‍👩‍👧 Parent View Active
          </span>
        </div>
      </div>

      {/* Student Profile Card */}
      <Card className="border-indigo-200/80 bg-gradient-to-r from-indigo-50/60 via-white to-sky-50/40 dark:border-white/10 dark:from-navy-900 dark:via-navy-900/90 dark:to-indigo-950/30">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-indigo-600 text-xl font-bold text-white shadow-md">
              {profile.name.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-xl font-bold text-slate-900 dark:text-white">
                  {profile.name}
                </h2>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Enrolled &amp; Active
                </span>
              </div>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Student ID: <code className="font-mono">{profile.student_id}</code> · {profile.school} · {profile.board} Class {profile.class_grade}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6 text-center">
            <div>
              <p className="font-display text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                {overview.total_study_time_hours} hrs
              </p>
              <p className="text-[11px] font-semibold uppercase text-slate-400">Total Study Time</p>
            </div>
            <div>
              <p className="font-display text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {overview.overall_accuracy_percentage}%
              </p>
              <p className="text-[11px] font-semibold uppercase text-slate-400">Quiz Accuracy</p>
            </div>
            <div>
              <p className="font-display text-2xl font-bold text-amber-500">
                🔥 {overview.streak_days} Days
              </p>
              <p className="text-[11px] font-semibold uppercase text-slate-400">Study Streak</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Weak Chapters (Priority Attention) & Strong Chapters */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Areas Needing Attention */}
        <Card className="border-rose-200 bg-white dark:border-rose-900/50 dark:bg-navy-900">
          <div className="flex items-center justify-between border-b border-rose-100 pb-3 dark:border-rose-900/30">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-rose-600 text-xs text-white">
                ⚠️
              </span>
              <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                Areas for Improvement &amp; Action Plan
              </h3>
            </div>
            <span className="text-xs font-semibold text-rose-600 dark:text-rose-400">
              {weakChapters.length} Chapters
            </span>
          </div>

          <div className="mt-4 space-y-3.5">
            {weakChapters.map((ch: any, idx: number) => (
              <div
                key={idx}
                className="rounded-xl border border-rose-100 bg-rose-50/40 p-3.5 dark:border-rose-950 dark:bg-rose-950/20"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-900 dark:text-white">
                    {ch.subject}: {ch.chapter}
                  </p>
                  <span className="rounded bg-rose-200/80 px-2 py-0.5 text-xs font-bold text-rose-800 dark:bg-rose-900 dark:text-rose-200">
                    {ch.mastery_score_pct || ch.accuracy_pct}% Mastery
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-700 dark:text-slate-300">
                  <b>Recommended Parent Support:</b>{" "}
                  {ch.recommended_focus || ch.recommended_action || "Encourage 10 min daily flashcard review on definitions."}
                </p>
                <div className="mt-2.5 flex items-center justify-between pt-1">
                  <span className="text-[11px] text-slate-400">
                    Board: {ch.board} Class {ch.class || ch.class_num}
                  </span>
                  <ButtonLink
                    href={`/learn?board=${ch.board}&class=${ch.class || ch.class_num}&subject=${encodeURIComponent(ch.subject)}&chapter=${encodeURIComponent(ch.chapter)}`}
                    variant="ghost"
                  >
                    Open Chapter Room →
                  </ButtonLink>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Mastered Strong Chapters */}
        <Card className="border-emerald-200 bg-white dark:border-emerald-900/50 dark:bg-navy-900">
          <div className="flex items-center justify-between border-b border-emerald-100 pb-3 dark:border-emerald-900/30">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-600 text-xs text-white">
                ✓
              </span>
              <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
                Strong Chapters &amp; Academic Milestones
              </h3>
            </div>
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              {strongChapters.length} Mastered
            </span>
          </div>

          <div className="mt-4 space-y-3.5">
            {strongChapters.map((ch: any, idx: number) => (
              <div
                key={idx}
                className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3.5 dark:border-emerald-950 dark:bg-emerald-950/20"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-900 dark:text-white">
                    {ch.subject}: {ch.chapter}
                  </p>
                  <span className="rounded bg-emerald-200/80 px-2 py-0.5 text-xs font-bold text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                    {ch.mastery_score_pct || ch.accuracy_pct}%
                  </span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>Curriculum: {ch.board} Class {ch.class || ch.class_num}</span>
                  <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                    ★ Ready for Board Exams
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Graded Quizzes & Teacher Feedback */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Recent Quizzes */}
        <Card>
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-white/5">
            <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
              Recent Quiz History
            </h3>
            <span className="text-xs text-slate-400">Past 7 Days</span>
          </div>
          <div className="mt-3 divide-y divide-slate-100 dark:divide-white/5">
            {quizzes.map((qz: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between py-2.5 text-xs">
                <div>
                  <p className="font-semibold text-slate-900 dark:text-white">
                    {qz.subject} - {qz.chapter}
                  </p>
                  <p className="text-slate-400">{qz.date}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-slate-900 dark:text-white">
                    {qz.score} / {qz.total} ({qz.percentage}%)
                  </p>
                  <span
                    className={cx(
                      "font-semibold",
                      qz.percentage >= 80 ? "text-emerald-600" : "text-amber-500"
                    )}
                  >
                    {qz.percentage >= 80 ? "Passed" : "Needs Review"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Completed Assignments & Teacher Feedback */}
        <Card>
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-white/5">
            <h3 className="font-display text-base font-semibold text-slate-900 dark:text-white">
              Teacher Assessments &amp; Remarks
            </h3>
            <span className="text-xs text-slate-400">Verified Submissions</span>
          </div>
          <div className="mt-3 space-y-3">
            {assignments.map((asg: any, idx: number) => (
              <div key={idx} className="rounded-xl bg-slate-50 p-3 text-xs dark:bg-white/5">
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-slate-900 dark:text-white">{asg.title}</p>
                  <span className="font-bold text-indigo-600 dark:text-indigo-400">{asg.score}</span>
                </div>
                <p className="mt-1 text-slate-600 dark:text-slate-300">
                  <span className="font-medium text-slate-700 dark:text-slate-200">Teacher Note:</span> {asg.teacher_feedback}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">Completed on {asg.date_completed}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
