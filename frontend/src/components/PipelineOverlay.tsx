import { useEffect, useState } from "react";
import {
  ScanSearch,
  Layers,
  BrainCircuit,
  Merge,
  Check,
  FileText,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Step definitions                                                    */
/* ------------------------------------------------------------------ */
interface PipelineStep {
  id: string;
  label: string;
  sublabel: string;
  Icon: React.ElementType;
}

const STEPS: PipelineStep[] = [
  {
    id: "ingest",
    label: "INGEST",
    sublabel: "Scanning raw blueprint DPI & dimensions",
    Icon: ScanSearch,
  },
  {
    id: "segment",
    label: "SEGMENT",
    sublabel: "OpenCV morphological wall extraction",
    Icon: Layers,
  },
  {
    id: "recognize",
    label: "RECOGNIZE",
    sublabel: "Deep Learning semantic text scanning",
    Icon: BrainCircuit,
  },
  {
    id: "fuse",
    label: "FUSE",
    sublabel: "Mapping text anchors to geometric room areas",
    Icon: Merge,
  },
];

/**
 * Duration (ms) to advance through steps 0 → 2.
 * Step 3 (FUSE) stays "active" until the real pipeline finishes.
 */
const STEP_DURATIONS = [2500, 4000, 5000];

/* ------------------------------------------------------------------ */
/*  Props                                                               */
/* ------------------------------------------------------------------ */
interface PdfProgress {
  step: string;
  page: number;
  total: number;
  message: string;
}

interface PipelineOverlayProps {
  visible: boolean;
  preview: string | null;
  fileName: string;
  pipelineComplete: boolean;
  onAnimationDone?: () => void;
  isPdf?: boolean;
  pdfProgress?: PdfProgress | null;
}

/* ------------------------------------------------------------------ */
/*  Component                                                           */
/* ------------------------------------------------------------------ */
export default function PipelineOverlay({
  visible,
  preview,
  fileName,
  pipelineComplete,
  onAnimationDone,
  isPdf,
  pdfProgress,
}: PipelineOverlayProps) {
  // -1 = not started, 0‑3 = active step, 4 = all done
  const [activeStep, setActiveStep] = useState(-1);
  // True once the timed steps (0→2) have all advanced, leaving step 3 as active
  const [reachedLastStep, setReachedLastStep] = useState(false);

  /* Advance steps 0→2 on fixed timers; pause at step 3 ("FUSE") */
  useEffect(() => {
    if (!visible) {
      setActiveStep(-1);
      setReachedLastStep(false);
      return;
    }

    setActiveStep(0);
    setReachedLastStep(false);

    const timers: ReturnType<typeof setTimeout>[] = [];
    let cumulative = 0;

    STEP_DURATIONS.forEach((dur, i) => {
      cumulative += dur;
      timers.push(
        setTimeout(() => {
          setActiveStep(i + 1);
          // After the last timed step fires, step 3 becomes active
          if (i === STEP_DURATIONS.length - 1) {
            setReachedLastStep(true);
          }
        }, cumulative)
      );
    });

    return () => timers.forEach(clearTimeout);
  }, [visible]);

  /* When pipeline truly finishes AND we've reached the last animated step,
     mark all steps complete then notify parent after a short delay. */
  useEffect(() => {
    if (!pipelineComplete || !visible) return;

    // If the API finished before the timed animation reached step 3,
    // fast-forward to step 3 first so the user sees it briefly.
    if (!reachedLastStep) {
      setActiveStep(3);
      setReachedLastStep(true);
      // After a brief pause showing step 3 active, mark all done
      const t = setTimeout(() => setActiveStep(4), 600);
      return () => clearTimeout(t);
    }

    // Already at step 3 — mark all complete
    setActiveStep(4);
  }, [pipelineComplete, reachedLastStep, visible]);

  /* Once activeStep reaches 4 (all done), wait a moment then notify parent */
  useEffect(() => {
    if (activeStep !== 4 || !visible) return;
    const t = setTimeout(() => onAnimationDone?.(), 800);
    return () => clearTimeout(t);
  }, [activeStep, visible, onAnimationDone]);

  if (!visible) return null;

  return (
    <div className="pipeline-overlay fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="pipeline-panel glass-panel mx-4 flex w-full max-w-4xl flex-col gap-8 rounded-2xl p-8 sm:flex-row sm:p-10">
        {/* ---- LEFT: Thumbnail ---- */}
        <div className="flex flex-col items-center gap-3 sm:w-52">
          <div className="relative flex h-40 w-40 items-center justify-center overflow-hidden rounded-xl border border-[rgba(56,189,248,0.2)] bg-slate-900/60">
            {preview ? (
              <img
                src={preview}
                alt="Blueprint preview"
                className="h-full w-full object-cover"
              />
            ) : (
              <FileText className="h-12 w-12 text-[#0EA5E9]/60" />
            )}

            {/* Scan line */}
            <div className="scan-line-overlay absolute left-0 h-[2px] w-full bg-gradient-to-r from-transparent via-[#00F0FF] to-transparent opacity-70" />
          </div>
          <p className="max-w-[180px] truncate text-center text-xs text-[#94A3B8]">
            {fileName}
          </p>
          {isPdf && pdfProgress && (
            <div className="mt-2 w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-slate-900/60 px-3 py-2">
              <p className="text-xs font-mono text-[#00F0FF] uppercase tracking-wider">
                {pdfProgress.step}
              </p>
              <p className="mt-0.5 text-[10px] text-[#94A3B8]">
                {pdfProgress.message}
              </p>
            </div>
          )}
        </div>

        {/* ---- RIGHT: Stepper ---- */}
        <div className="flex flex-1 flex-col justify-center gap-0">
          {STEPS.map((step, i) => {
            const status: "pending" | "active" | "complete" =
              i < activeStep ? "complete" : i === activeStep ? "active" : "pending";

            return (
              <div key={step.id} className="flex items-stretch gap-4">
                {/* Icon + vertical connector */}
                <div className="flex flex-col items-center">
                  {/* Step circle */}
                  <div
                    className={`step-circle relative flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all duration-500 ${
                      status === "complete"
                        ? "border-[#4ADE80] bg-[#4ADE80]/10"
                        : status === "active"
                        ? "step-active border-[#00F0FF] bg-[#00F0FF]/10"
                        : "border-slate-600/40 bg-slate-800/40"
                    }`}
                  >
                    {status === "complete" ? (
                      <Check className="h-5 w-5 text-[#4ADE80]" />
                    ) : (
                      <step.Icon
                        className={`h-5 w-5 transition-colors duration-500 ${
                          status === "active"
                            ? "text-[#00F0FF]"
                            : "text-slate-500"
                        }`}
                      />
                    )}

                    {/* Spinning dashed ring for active state */}
                    {status === "active" && (
                      <svg
                        className="step-spin-ring absolute inset-[-4px] h-[calc(100%+8px)] w-[calc(100%+8px)]"
                        viewBox="0 0 48 48"
                      >
                        <circle
                          cx="24"
                          cy="24"
                          r="22"
                          fill="none"
                          stroke="#00F0FF"
                          strokeWidth="1.5"
                          strokeDasharray="6 4"
                          strokeLinecap="round"
                          opacity="0.6"
                        />
                      </svg>
                    )}
                  </div>

                  {/* Vertical connector line (not on last step) */}
                  {i < STEPS.length - 1 && (
                    <div
                      className={`w-[2px] flex-1 min-h-[24px] transition-colors duration-500 ${
                        i < activeStep
                          ? "bg-[#4ADE80]/50"
                          : i === activeStep
                          ? "bg-[#00F0FF]/30"
                          : "bg-slate-700/30"
                      }`}
                    />
                  )}
                </div>

                {/* Text */}
                <div className="pb-6">
                  <p
                    className={`font-mono text-sm font-bold tracking-wider transition-colors duration-500 ${
                      status === "complete"
                        ? "text-[#4ADE80]"
                        : status === "active"
                        ? "text-[#00F0FF]"
                        : "text-slate-500"
                    }`}
                  >
                    {step.label}
                  </p>
                  <p
                    className={`mt-0.5 text-xs transition-colors duration-500 ${
                      status === "active"
                        ? "text-[#94A3B8]"
                        : status === "complete"
                        ? "text-[#4ADE80]/60"
                        : "text-slate-600"
                    }`}
                  >
                    {step.sublabel}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
