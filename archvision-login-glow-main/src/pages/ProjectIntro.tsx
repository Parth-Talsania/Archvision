import { Brain, Cog, Building2 } from "lucide-react";

const pillars = [
  {
    emoji: "\u{1F9E0}",
    Icon: Brain,
    title: "The Theoretical Gap",
    text: "Historically, architectural floor plans have been \u2018dead\u2019 images\u2014readable by humans but opaque to machines. ArchVision bridges the gap between semantic understanding and spatial geometry, enabling computers to natively understand the relationships, scale, and function of drawn environments.",
  },
  {
    emoji: "\u2699\uFE0F",
    Icon: Cog,
    title: "The Technical Stack",
    text: "Built on a dual-path pipeline. We utilize aggressive Morphological Operations (OpenCV) for topological wall segmentation, parallelized with Deep Learning (EasyOCR) for semantic text extraction. Finally, a custom data-fusion algorithm maps text anchors to geometric centroids to generate highly accurate JSON spatial arrays.",
  },
  {
    emoji: "\u{1F3E2}",
    Icon: Building2,
    title: "Real-World Utility",
    text: "ArchVision automates the most tedious parts of real estate and architectural planning. Instantly audit usable square footage, generate space-allocation metrics, and convert legacy PDF blueprints into smart-home ready digital twins.",
  },
];

export default function ProjectIntro() {
  return (
    <section className="relative min-h-[calc(100vh-4rem)] py-16 px-2 sm:px-0">
      {/* ---- Hero Header ---- */}
      <div className="mx-auto max-w-4xl text-center mb-20">
        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight tracking-tight text-gradient-cyan-purple">
          ArchVision: Intelligence for Spatial&nbsp;Design
        </h1>

        <p className="mt-6 text-lg sm:text-xl leading-relaxed text-[#38BDF8]">
          Transforming static 2D blueprints into dynamic, computable, and
          actionable spatial data using advanced&nbsp;AI.
        </p>
      </div>

      {/* ---- Three Pillars Grid ---- */}
      <div className="mx-auto max-w-6xl grid gap-8 md:grid-cols-3">
        {pillars.map(({ emoji, Icon, title, text }) => (
          <div
            key={title}
            className="pillar-card glass-panel group relative flex flex-col rounded-2xl p-8 transition-all duration-300 hover:scale-[1.02]"
          >
            {/* Icon area */}
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-xl border border-[#0EA5E9]/20 bg-[#0EA5E9]/10 transition-colors duration-300 group-hover:border-[#0EA5E9]/40 group-hover:bg-[#0EA5E9]/20">
              <span className="text-2xl" aria-hidden="true">
                {emoji}
              </span>
            </div>

            {/* Title */}
            <h2 className="mb-3 font-display text-xl font-bold tracking-tight text-white">{title}</h2>

            {/* Body */}
            <p className="flex-1 text-sm leading-relaxed text-[#94A3B8]">
              {text}
            </p>

            {/* Subtle bottom accent line */}
            <div className="mt-6 h-px w-full bg-gradient-to-r from-transparent via-[#0EA5E9]/30 to-transparent" />
          </div>
        ))}
      </div>
    </section>
  );
}
