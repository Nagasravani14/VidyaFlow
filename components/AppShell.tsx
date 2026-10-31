"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brand, ThemeToggle, cx } from "./ui";

type RoleType = "student" | "teacher" | "parent";

interface NavItem {
  label: string;
  href: string;
  icon?: string;
}

const STUDENT_NAV: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: "📊" },
  { label: "Subjects Explorer", href: "/subjects", icon: "📚" },
  { label: "Lesson Study Room", href: "/learn", icon: "📖" },
  { label: "Practice Arena", href: "/practice", icon: "⚡" },
  { label: "Learning Map", href: "/map", icon: "🗺️" },
  { label: "AI Doubt Coach", href: "/coach", icon: "💬" },
];

const TEACHER_NAV: NavItem[] = [
  { label: "Teacher Portal", href: "/teacher", icon: "👩‍🏫" },
  { label: "1-Click Assignment Generator", href: "/teacher", icon: "⚡" },
  { label: "Curriculum Browser", href: "/subjects", icon: "📚" },
];

const PARENT_NAV: NavItem[] = [
  { label: "Parent Portal", href: "/parent", icon: "👨‍👩‍👧" },
  { label: "Academic Progress & Hours", href: "/parent", icon: "📈" },
  { label: "Child Lesson View", href: "/learn", icon: "📖" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();

  // Determine current active role from URL
  const currentRole: RoleType = path.startsWith("/teacher")
    ? "teacher"
    : path.startsWith("/parent")
    ? "parent"
    : "student";

  const navItems =
    currentRole === "teacher"
      ? TEACHER_NAV
      : currentRole === "parent"
      ? PARENT_NAV
      : STUDENT_NAV;

  return (
    <div className="min-h-screen lg:flex">
      {/* Sidebar (Desktop) */}
      <aside className="hidden w-64 shrink-0 flex-col justify-between border-r border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-navy-800 lg:flex">
        <div>
          {/* Brand Logo */}
          <div className="mb-5 px-2">
            <Brand />
          </div>

          {/* Role Switcher Tabs */}
          <div className="mb-5 rounded-xl bg-slate-100 p-1 dark:bg-white/5">
            <p className="px-2 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Active Portal
            </p>
            <div className="mt-1 grid grid-cols-3 gap-1">
              <Link
                href="/dashboard"
                className={cx(
                  "rounded-lg py-1.5 text-center text-xs font-semibold transition",
                  currentRole === "student"
                    ? "bg-white text-indigo-700 shadow-sm dark:bg-navy-700 dark:text-white"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                )}
              >
                Student
              </Link>
              <Link
                href="/teacher"
                className={cx(
                  "rounded-lg py-1.5 text-center text-xs font-semibold transition",
                  currentRole === "teacher"
                    ? "bg-white text-indigo-700 shadow-sm dark:bg-navy-700 dark:text-white"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                )}
              >
                Teacher
              </Link>
              <Link
                href="/parent"
                className={cx(
                  "rounded-lg py-1.5 text-center text-xs font-semibold transition",
                  currentRole === "parent"
                    ? "bg-white text-indigo-700 shadow-sm dark:bg-navy-700 dark:text-white"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                )}
              >
                Parent
              </Link>
            </div>
          </div>

          {/* Role-Specific Navigation Menu */}
          <div className="px-2 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {currentRole === "student"
              ? "Student Learning Tools"
              : currentRole === "teacher"
              ? "Teacher Tools"
              : "Parent Analytics"}
          </div>

          <nav className="flex flex-col gap-1" aria-label="Main navigation">
            {navItems.map((item) => {
              const isCurrent = path === item.href;
              return (
                <Link
                  key={item.href + item.label}
                  href={item.href}
                  aria-current={isCurrent ? "page" : undefined}
                  className={cx(
                    "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition",
                    isCurrent
                      ? "bg-indigo-600 text-white shadow-glow"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/10"
                  )}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer: System Status */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50 p-3 text-xs dark:border-white/10 dark:bg-navy-900/60">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              Local RAG Engine Active
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
            Telangana &amp; ICSE (Grades 6–10) · 100% Free
          </p>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="min-w-0 flex-1">
        {/* Sticky Header */}
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-white/10 dark:bg-navy-900/90">
          <div className="flex items-center justify-between px-4 py-3 sm:px-8">
            <div className="flex items-center gap-3">
              <div className="lg:hidden">
                <Brand className="text-lg" />
              </div>
              <div className="hidden items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300 sm:flex">
                <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                  {currentRole.toUpperCase()} PORTAL
                </span>
                <span>·</span>
                <span className="text-slate-500">VidyaFlow AI Learning Platform</span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Portal Switcher Pill on Mobile / Desktop */}
              <div className="flex items-center gap-1 text-xs">
                {currentRole !== "student" && (
                  <Link
                    href="/dashboard"
                    className="rounded-lg border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50 dark:border-white/10 dark:text-slate-300"
                  >
                    Student
                  </Link>
                )}
                {currentRole !== "teacher" && (
                  <Link
                    href="/teacher"
                    className="rounded-lg border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50 dark:border-white/10 dark:text-slate-300"
                  >
                    Teacher
                  </Link>
                )}
                {currentRole !== "parent" && (
                  <Link
                    href="/parent"
                    className="rounded-lg border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50 dark:border-white/10 dark:text-slate-300"
                  >
                    Parent
                  </Link>
                )}
              </div>
              <ThemeToggle />
            </div>
          </div>

          {/* Mobile Nav Links */}
          <nav
            className="flex gap-1 overflow-x-auto px-4 pb-2 lg:hidden"
            aria-label="Mobile Navigation"
          >
            {navItems.map((item) => (
              <Link
                key={item.href + item.label}
                href={item.href}
                className={cx(
                  "whitespace-nowrap rounded-xl px-3 py-1.5 text-xs font-medium transition",
                  path === item.href
                    ? "bg-indigo-600 text-white shadow-glow"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/10"
                )}
              >
                {item.icon} {item.label}
              </Link>
            ))}
          </nav>
        </header>

        {/* Page Content */}
        <main className="mx-auto max-w-6xl p-4 sm:p-8">{children}</main>
      </div>
    </div>
  );
}
