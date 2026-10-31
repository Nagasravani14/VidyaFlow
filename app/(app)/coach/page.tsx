"use client";

import { useState, useEffect, useRef } from "react";
import { languages } from "@/lib/data";
import { Card, PageHead, cx, styles } from "@/components/ui";
import {
  sendTutorChatMessage,
  fetchTutorStatus,
  TutorCitation,
  TutorStatusResponse,
} from "@/lib/api";

interface ChatBubble {
  id: string;
  from: "you" | "system";
  text: string;
  keyPoints?: string[];
  hints?: string[];
  citations?: TutorCitation[];
  isGrounded?: boolean;
  groundingNotes?: string;
  modelName?: string;
  error?: boolean;
}

const prompts = [
  "Can I write 99 as IC in Roman numerals according to my textbook?",
  "Explain the difference between Indian and International place values",
  "How do I round 578 × 161 using the general rule?",
  "Explain linear equations with a real-life example",
];

export default function Coach() {
  const [lang, setLang] = useState("English");
  const [grade, setGrade] = useState(6);
  const [board, setBoard] = useState("TELANGANA_STATE_BOARD");
  const [msgs, setMsgs] = useState<ChatBubble[]>([]);
  const [t, setT] = useState("");
  const [sessionUuid, setSessionUuid] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusInfo, setStatusInfo] = useState<TutorStatusResponse | null>(null);
  const [expandedCitation, setExpandedCitation] = useState<number | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Check tutor status on load
  useEffect(() => {
    let mounted = true;
    fetchTutorStatus().then((s) => {
      if (mounted) setStatusInfo(s);
    });
    return () => {
      mounted = false;
    };
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, isLoading]);

  const send = async (text: string) => {
    if (!text.trim() || isLoading) return;
    const userText = text.trim();
    setT("");

    const userBubble: ChatBubble = {
      id: `user-${Date.now()}`,
      from: "you",
      text: userText,
    };

    setMsgs((prev) => [...prev, userBubble]);
    setIsLoading(true);

    try {
      const resp = await sendTutorChatMessage({
        message: userText,
        session_uuid: sessionUuid,
        board_code: board,
        grade_number: grade,
        subject_name: "Mathematics",
        language: lang,
      });

      if (resp.session_uuid) {
        setSessionUuid(resp.session_uuid);
      }

      const assistantBubble: ChatBubble = {
        id: `asst-${Date.now()}`,
        from: "system",
        text: resp.reply,
        keyPoints: resp.key_points,
        hints: resp.hints,
        citations: resp.citations,
        isGrounded: resp.is_textbook_grounded,
        groundingNotes: resp.grounding_notes,
        modelName: resp.model_name,
      };

      setMsgs((prev) => [...prev, assistantBubble]);
    } catch (err: any) {
      const errorMsg =
        err?.message || "Failed to reach AI Tutor. Please check your backend connection.";
      setMsgs((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          from: "system",
          text: `AI Coach notice: ${errorMsg}`,
          error: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <PageHead
        title="AI Learning Coach"
        sub="Textbook-grounded AI tutor powered by Google Gemini and verified state curriculum."
      />

      <Card className="flex min-h-[32rem] flex-col">
        {/* Controls Bar: Status, Board, Grade & Language */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3 text-xs dark:border-white/10">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cx(
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium",
                statusInfo?.is_available
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
                  : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
              )}
            >
              <span
                className={cx(
                  "h-2 w-2 rounded-full",
                  statusInfo?.is_available ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                )}
              />
              {statusInfo?.is_available
                ? `Gemini ${statusInfo.model} Online`
                : "Checking AI Service..."}
            </span>

            <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">
              Telangana SCERT Class 6 Ingested
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <label htmlFor="board-select" className="font-semibold text-slate-600 dark:text-slate-300">
                Board:
              </label>
              <select
                id="board-select"
                value={board}
                onChange={(e) => setBoard(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white p-1 text-xs dark:border-white/20 dark:bg-navy-900"
              >
                <option value="TELANGANA_STATE_BOARD">Telangana State Board</option>
                <option value="ICSE">ICSE</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <label htmlFor="grade-select" className="font-semibold text-slate-600 dark:text-slate-300">
                Class:
              </label>
              <select
                id="grade-select"
                value={grade}
                onChange={(e) => setGrade(Number(e.target.value))}
                className="rounded-lg border border-slate-300 bg-white p-1 text-xs dark:border-white/20 dark:bg-navy-900"
              >
                <option value={6}>Class 6</option>
                <option value={7}>Class 7</option>
                <option value={8}>Class 8</option>
                <option value={9}>Class 9</option>
                <option value={10}>Class 10</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <label htmlFor="lang" className="font-semibold text-slate-600 dark:text-slate-300">
                Language:
              </label>
              <select
                id="lang"
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white p-1 text-xs dark:border-white/20 dark:bg-navy-900"
              >
                {languages.map((l) => (
                  <option key={l}>{l}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Chat History View */}
        <div className="flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
          {msgs.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-white/15">
              <p className="font-semibold text-slate-700 dark:text-slate-200">
                Welcome to your AI Learning Coach!
              </p>
              <p className="mt-1">
                Ask any question or pick a suggested topic below. Answers are strictly grounded in official SCERT/ICSE textbooks.
              </p>
            </div>
          )}

          {msgs.map((m, k) => (
            <div
              key={m.id || k}
              className={cx(
                "max-w-[88%] rounded-2xl p-4 text-sm leading-relaxed shadow-sm",
                m.from === "you"
                  ? "ml-auto bg-indigo-600 text-white"
                  : m.error
                  ? "bg-rose-50 text-rose-900 border border-rose-200 dark:bg-rose-950/30 dark:text-rose-200 dark:border-rose-800"
                  : "bg-slate-50 text-slate-800 border border-slate-200 dark:bg-navy-900/90 dark:text-slate-100 dark:border-white/10"
              )}
            >
              {/* Message Header for Assistant */}
              {m.from === "system" && !m.error && (
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-1.5 text-xs text-slate-500 dark:border-white/10 dark:text-slate-400">
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                    VidyaFlow AI Tutor
                  </span>
                  {m.isGrounded && (
                    <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300">
                      ✓ Official Textbook Grounded
                    </span>
                  )}
                </div>
              )}

              {/* Message Body formatted */}
              <div className="whitespace-pre-line font-sans">{m.text}</div>

              {/* Key Points Badge List */}
              {m.keyPoints && m.keyPoints.length > 0 && (
                <div className="mt-3 rounded-lg bg-indigo-50/70 p-2.5 text-xs text-indigo-950 dark:bg-indigo-950/40 dark:text-indigo-200">
                  <p className="font-semibold uppercase tracking-wider text-[10px] text-indigo-800 dark:text-indigo-300">
                    Key Concepts to Remember:
                  </p>
                  <ul className="mt-1 list-inside list-disc space-y-0.5">
                    {m.keyPoints.map((kp, idx) => (
                      <li key={idx}>{kp}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Citations Accordion */}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-2 text-xs dark:border-white/10">
                  <p className="font-semibold text-slate-600 dark:text-slate-400">
                    Textbook Citations:
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {m.citations.map((cite, cIdx) => (
                      <button
                        key={cIdx}
                        type="button"
                        onClick={() =>
                          setExpandedCitation(expandedCitation === cIdx ? null : cIdx)
                        }
                        className="rounded-md border border-indigo-200 bg-white px-2 py-1 text-left text-[11px] text-indigo-700 hover:bg-indigo-50 dark:border-white/15 dark:bg-navy-800 dark:text-indigo-300"
                      >
                        📖 {cite.source_title}
                        {cite.page_number ? ` • Page ${cite.page_number}` : ""}
                      </button>
                    ))}
                  </div>

                  {expandedCitation !== null && m.citations[expandedCitation] && (
                    <div className="mt-2 rounded-lg bg-amber-50 p-2 text-[11px] text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                      <p className="font-semibold">
                        {m.citations[expandedCitation].heading || "Section Excerpt"}:
                      </p>
                      <p className="mt-0.5 whitespace-pre-line italic">
                        "{m.citations[expandedCitation].excerpt}"
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Thinking / Loading Indicator */}
          {isLoading && (
            <div className="max-w-[80%] rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 shadow-sm dark:border-white/10 dark:bg-navy-900/90 dark:text-slate-300">
              <div className="flex items-center gap-2">
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
                <span>Consulting official textbook passages &amp; formulating pedagogical explanation...</span>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Suggestion Chips */}
        <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-2 dark:border-white/5">
          {prompts.map((p) => (
            <button
              key={p}
              disabled={isLoading}
              onClick={() => send(p)}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700 hover:bg-slate-200 disabled:opacity-50 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="mt-3 flex gap-2">
          <input
            aria-label="Message"
            value={t}
            disabled={isLoading}
            onChange={(e) => setT(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(t)}
            placeholder="Ask me anything about your textbook syllabus..."
            className="flex-1 rounded-xl border border-slate-300 bg-white p-2.5 text-sm dark:border-white/20 dark:bg-navy-900"
          />
          <button
            onClick={() => send(t)}
            disabled={isLoading || !t.trim()}
            className={cx(styles.primary, "disabled:opacity-50")}
          >
            {isLoading ? "Thinking..." : "Send"}
          </button>
        </div>
      </Card>
    </>
  );
}
