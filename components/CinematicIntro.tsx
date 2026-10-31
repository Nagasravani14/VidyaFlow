"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Image from "next/image";

interface CinematicIntroProps {
  /** Optional callback fired when intro finishes or is skipped */
  onComplete?: () => void;
  /** Force the intro to play regardless of sessionStorage */
  forcePlay?: boolean;
}

const STORAGE_KEY = "vf_cinematic_intro_seen";

export default function CinematicIntro({ onComplete, forcePlay = false }: CinematicIntroProps) {
  const [isVisible, setIsVisible] = useState<boolean>(false);
  const [isExiting, setIsExiting] = useState<boolean>(false);
  const [step, setStep] = useState<number>(0);
  const [imageError, setImageError] = useState<boolean>(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const timeoutsRef = useRef<number[]>([]);
  const animFrameRef = useRef<number | null>(null);

  const clearAllTimeouts = useCallback(() => {
    timeoutsRef.current.forEach((t) => window.clearTimeout(t));
    timeoutsRef.current = [];
  }, []);

  const finishIntro = useCallback(
    (immediate = false) => {
      clearAllTimeouts();

      try {
        sessionStorage.setItem(STORAGE_KEY, "true");
      } catch {
        // Storage might be restricted in private/iframe browsing
      }

      document.body.style.overflow = "";

      if (immediate) {
        setIsVisible(false);
        onComplete?.();
        return;
      }

      setIsExiting(true);
      const exitTimer = window.setTimeout(() => {
        setIsVisible(false);
        onComplete?.();
      }, 700);
      timeoutsRef.current.push(exitTimer);
    },
    [clearAllTimeouts, onComplete]
  );

  const startAnimationSequence = useCallback(() => {
    clearAllTimeouts();
    setIsVisible(true);
    setIsExiting(false);
    setStep(0);
    document.body.style.overflow = "hidden";

    // Step 1: 600ms - Hero image begins gradual reveal & slow zoom
    const t1 = window.setTimeout(() => setStep(1), 600);
    // Step 2: 1500ms - Anamorphic energy streak & logo pulse
    const t2 = window.setTimeout(() => setStep(2), 1500);
    // Step 3: 2300ms - Brand title "VIDYAFLOW" reveals with cinematic shimmer
    const t3 = window.setTimeout(() => setStep(3), 2300);
    // Step 4: 3300ms - Tagline "Learn smarter. Grow stronger. Go beyond."
    const t4 = window.setTimeout(() => setStep(4), 3300);
    // Step 5: 4800ms - Seamless dissolve transition into landing page
    const t5 = window.setTimeout(() => finishIntro(false), 4800);

    timeoutsRef.current.push(t1, t2, t3, t4, t5);
  }, [clearAllTimeouts, finishIntro]);

  // Initial check on mount
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Check reduced motion preference
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      try {
        sessionStorage.setItem(STORAGE_KEY, "true");
      } catch {}
      return;
    }

    // Check URL override: ?intro=1
    const searchParams = new URLSearchParams(window.location.search);
    const hasForceParam = searchParams.get("intro") === "1";

    let alreadySeen = false;
    try {
      alreadySeen = sessionStorage.getItem(STORAGE_KEY) === "true";
    } catch {}

    if (forcePlay || hasForceParam || !alreadySeen) {
      startAnimationSequence();
    }

    // Listen for custom replay event
    const handleReplayEvent = () => {
      startAnimationSequence();
    };
    window.addEventListener("vf-replay-intro", handleReplayEvent);

    return () => {
      window.removeEventListener("vf-replay-intro", handleReplayEvent);
      clearAllTimeouts();
      document.body.style.overflow = "";
    };
  }, [forcePlay, startAnimationSequence, clearAllTimeouts]);

  // Keyboard shortcut: Escape to skip
  useEffect(() => {
    if (!isVisible) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        finishIntro(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isVisible, finishIntro]);

  // Ambient Starfield / Energy Particles Canvas
  useEffect(() => {
    if (!isVisible) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Particle pool with cinematic colors
    const colors = [
      "rgba(56, 189, 248, ",  // Cyan
      "rgba(129, 140, 248, ", // Indigo
      "rgba(192, 132, 252, ", // Violet
      "rgba(34, 211, 238, ",  // Teal
    ];

    const particleCount = Math.min(Math.floor((width * height) / 25000), 55);
    const particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 2 + 0.8,
      speedX: (Math.random() - 0.5) * 0.35,
      speedY: -Math.random() * 0.45 - 0.1, // gently float upward
      baseAlpha: Math.random() * 0.5 + 0.3,
      alpha: Math.random() * 0.5 + 0.3,
      alphaSpeed: (Math.random() * 0.02 + 0.008) * (Math.random() > 0.5 ? 1 : -1),
      color: colors[Math.floor(Math.random() * colors.length)],
    }));

    let isRunning = true;
    const render = () => {
      if (!isRunning) return;
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.speedX;
        p.y += p.speedY;
        p.alpha += p.alphaSpeed;

        if (p.alpha > p.baseAlpha + 0.2 || p.alpha < 0.15) {
          p.alphaSpeed = -p.alphaSpeed;
        }

        if (p.y < -10) p.y = height + 10;
        if (p.x < -10) p.x = width + 10;
        if (p.x > width + 10) p.x = -10;

        ctx.fillStyle = `${p.color}${Math.max(0, Math.min(1, p.alpha))})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      isRunning = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener("resize", handleResize);
    };
  }, [isVisible]);

  if (!isVisible) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="VidyaFlow Introductory Animation"
      className={`fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-navy-950 text-slate-100 transition-all duration-700 ease-out ${
        isExiting ? "opacity-0 scale-105 pointer-events-none" : "opacity-100 scale-100"
      }`}
    >
      {/* Skip Button */}
      <div className="absolute top-5 right-5 sm:top-8 sm:right-8 z-40">
        <button
          type="button"
          onClick={() => finishIntro(false)}
          className="group flex items-center gap-2 rounded-full border border-sky-400/30 bg-navy-900/70 px-4 py-2 text-xs sm:text-sm font-medium text-sky-200 backdrop-blur-md shadow-lg shadow-sky-950/50 transition-all duration-300 hover:border-sky-300 hover:bg-sky-500/20 hover:text-white hover:shadow-cyan-500/20 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        >
          <span>Skip Intro</span>
          <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-slate-300 group-hover:text-white">
            Esc
          </span>
          <svg
            className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Deep Midnight & Cosmic Radial Glow Background */}
      <div
        className="absolute inset-0 bg-navy-950 pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(29, 27, 76, 0.6) 0%, rgba(13, 19, 48, 0.85) 45%, #050818 90%)",
        }}
      />

      {/* Atmospheric Nebula Glow Behind Content */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center overflow-hidden">
        <div className="h-[420px] w-[620px] rounded-full bg-gradient-to-r from-sky-600/25 via-indigo-600/30 to-violet-600/25 blur-[120px] animate-vf-glow-pulse" />
      </div>

      {/* Hero Image Reveal with Cinematic Dolly Zoom & Vignette */}
      {step >= 1 && !imageError && (
        <div
          className="absolute inset-0 pointer-events-none overflow-hidden animate-vf-hero-zoom"
          style={{
            WebkitMaskImage:
              "radial-gradient(ellipse at 50% 50%, rgba(0,0,0,1) 40%, rgba(0,0,0,0.5) 70%, transparent 95%)",
            maskImage:
              "radial-gradient(ellipse at 50% 50%, rgba(0,0,0,1) 40%, rgba(0,0,0,0.5) 70%, transparent 95%)",
          }}
        >
          <Image
            src="/hero-heroes.png"
            alt="VidyaFlow Heroes"
            fill
            priority
            sizes="100vw"
            className="object-cover object-center brightness-75 contrast-110"
            onError={() => setImageError(true)}
          />
          {/* Subtle cinematic gradient vignette overlays */}
          <div className="absolute inset-0 bg-gradient-to-t from-navy-950 via-transparent to-navy-950/80 opacity-80" />
          <div className="absolute inset-0 bg-gradient-to-r from-navy-950/90 via-transparent to-navy-950/90" />
        </div>
      )}

      {/* Particle Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none z-10"
        aria-hidden="true"
      />

      {/* Center Cinematic Energy Shockwave */}
      {step >= 2 && (
        <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-15">
          <div className="h-64 w-64 rounded-full border border-cyan-400/50 bg-gradient-to-tr from-cyan-500/10 via-indigo-500/15 to-violet-500/10 blur-sm animate-vf-shockwave" />
        </div>
      )}

      {/* Anamorphic Horizontal Light Flare Streak */}
      {step >= 2 && (
        <div className="absolute inset-x-0 pointer-events-none flex items-center justify-center z-20">
          <div
            className="h-[3px] w-full max-w-5xl rounded-full bg-gradient-to-r from-transparent via-cyan-300 via-50% to-transparent blur-[1px] animate-vf-flare"
            style={{
              boxShadow: "0 0 30px 4px rgba(56, 189, 248, 0.8), 0 0 60px 8px rgba(129, 140, 248, 0.5)",
            }}
          />
        </div>
      )}

      {/* Main Brand & Tagline Content */}
      <div className="relative z-30 mx-auto flex flex-col items-center px-4 text-center max-w-4xl">
        {/* Brand Emblem Pulse */}
        {step >= 2 && (
          <div className="mb-4 sm:mb-6 animate-vf-logo flex items-center justify-center">
            <div className="relative">
              <svg viewBox="0 0 32 32" className="h-16 w-16 sm:h-20 sm:w-20" aria-hidden="true">
                <defs>
                  <linearGradient id="intro_vfg" x1="0" y1="0" x2="1" y2="1">
                    <stop stopColor="#38bdf8" />
                    <stop offset="0.5" stopColor="#818cf8" />
                    <stop offset="1" stopColor="#c084fc" />
                  </linearGradient>
                  <filter id="intro_glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                <path d="M4 9l12-5 12 5-12 5z" fill="url(#intro_vfg)" filter="url(#intro_glow)" />
                <path
                  d="M9 14v6c0 2 3.2 4 7 4s7-2 7-4v-6l-7 3z"
                  fill="url(#intro_vfg)"
                  opacity=".85"
                />
                <circle cx="28" cy="10" r="2.2" fill="#67e8f9" filter="url(#intro_glow)" />
              </svg>
              {/* Center point spark */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-1 w-1 bg-white rounded-full shadow-[0_0_16px_4px_#38bdf8]" />
            </div>
          </div>
        )}

        {/* Brand Title: VIDYAFLOW */}
        {step >= 3 && (
          <div className="animate-vf-title">
            <h1
              className="font-display text-4xl sm:text-6xl md:text-7xl font-extrabold uppercase animate-vf-shimmer select-none"
              style={{
                backgroundImage:
                  "linear-gradient(90deg, #f8fafc 0%, #7dd3fc 25%, #e0e7ff 50%, #c084fc 75%, #f8fafc 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                filter:
                  "drop-shadow(0 0 25px rgba(56, 189, 248, 0.65)) drop-shadow(0 0 55px rgba(129, 140, 248, 0.4))",
              }}
            >
              VIDYAFLOW
            </h1>
          </div>
        )}

        {/* Tagline Reveal */}
        {step >= 4 && (
          <div className="mt-4 sm:mt-6 animate-vf-tagline flex flex-col items-center">
            {/* Horizontal glowing accent rule */}
            <div className="mb-4 h-[1px] w-32 sm:w-48 bg-gradient-to-r from-transparent via-sky-400 to-transparent opacity-80" />

            <p className="font-display text-lg sm:text-2xl md:text-3xl font-semibold tracking-wide text-sky-100 sm:tracking-wider">
              Learn smarter. Grow stronger. Go beyond.
            </p>

            <p className="mt-3 text-xs sm:text-sm font-medium tracking-widest uppercase text-indigo-200/80">
              AI-Powered Adaptive Learning &bull; Classes 6–10
            </p>
          </div>
        )}
      </div>

      {/* Bottom Cinematic Accent Lighting */}
      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-navy-950 via-navy-950/60 to-transparent pointer-events-none" />
    </div>
  );
}

/**
 * ReplayIntroButton:
 * A subtle, lightweight button that can be embedded anywhere to trigger
 * the cinematic intro animation on demand (useful for testing & demoing).
 */
export function ReplayIntroButton({ className = "" }: { className?: string }) {
  const triggerReplay = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("vf-replay-intro"));
    }
  };

  return (
    <button
      type="button"
      onClick={triggerReplay}
      className={`inline-flex items-center gap-1.5 rounded-full border border-indigo-400/30 bg-indigo-950/40 px-3 py-1.5 text-xs font-medium text-sky-300 transition hover:border-sky-300 hover:bg-indigo-900/60 hover:text-white ${className}`}
      title="Replay Cinematic Intro"
      aria-label="Replay intro animation"
    >
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span>Intro</span>
    </button>
  );
}
