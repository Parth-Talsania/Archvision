import { Github, Linkedin } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Team data                                                          */
/* ------------------------------------------------------------------ */
interface Founder {
  name: string;
  role: string;
  bio: string;
  avatar: string;          // initials fallback
  github?: string;
  linkedin?: string;
}

/*
 * =====================================================================
 *  EDIT SOCIAL LINKS BELOW
 *  Replace the placeholder URLs with your actual profile links.
 *  Set a field to "" (empty string) to hide that icon on the card.
 * =====================================================================
 */
const founders: Founder[] = [
  {
    name: "Mohammed Ayaan",
    role: "Lead AI & Computer Vision Engineer & Frontend Engineer",
    bio: "The bridge between the backend intelligence and the user interface. Spearheaded the OpenCV geometric segmentation pipeline while co-developing the interactive React frontend and aided in AI and DL development.",
    avatar: "MA",
    github:   "https://github.com/ayaanm786",          // <-- paste Mohammed Ayaan's GitHub URL
    linkedin: "https://www.linkedin.com/in/mohammed-ayaan-886b2b264/",      // <-- paste Mohammed Ayaan's LinkedIn URL
  },
  {
    name: "Parth Talsania",
    role: "Deep Learning & OCR Specialist",
    bio: "Architected the semantic recognition engine. Integrated and fine-tuned Deep Learning OCR models to extract and intelligently map blueprint text to structural geometry.",
    avatar: "PT",
    github:   "https://github.com/parth-talsania",          // <-- paste Parth Talsania's GitHub URL
    linkedin: "https://linkedin.com/in/parth-talsania",      // <-- paste Parth Talsania's LinkedIn URL
  },
  {
    name: "Abhishek Rathod",
    role: "Full-Stack Systems Architect, aided in AI, DL & OCR",
    bio: "Engineered the robust backend infrastructure and API bridges, ensuring the heavy Python AI scripts communicate seamlessly with the frontend dashboard in real-time.",
    avatar: "AR",
    github:   "https://github.com/",          // <-- paste Abhishek Rathod's GitHub URL
    linkedin: "https://linkedin.com/in/",      // <-- paste Abhishek Rathod's LinkedIn URL
  },
  {
    name: "Harshil Darji",
    role: "Lead UI/UX Developer",
    bio: "Designed and engineered the immersive \u2018Deep Blue Galaxy\u2019 interface. Focused on glassmorphic components, buttery-smooth animations, and the overall premium user experience.",
    avatar: "HD",
    github:   "https://github.com/",          // <-- paste Harshil Darji's GitHub URL
    linkedin: "https://linkedin.com/in/",      // <-- paste Harshil Darji's LinkedIn URL
  },
  {
    name: "Heli Darji",
    role: "Data Engineering & Analytics Lead",
    bio: "Developed the core mathematical logic for automated square footage calculations, aided in Data Pre-processing and built the real-time JSON data extraction pipeline that powers the analytics dashboard.",
    avatar: "HD",
    github:   "https://github.com/",          // <-- paste Heli Darji's GitHub URL
    linkedin: "https://linkedin.com/in/",      // <-- paste Heli Darji's LinkedIn URL
  },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function Founders() {
  return (
    <section className="relative min-h-[calc(100vh-4rem)] py-16 px-2 sm:px-0">
      {/* ============================================================ */}
      {/*  THE STORY PANEL                                              */}
      {/* ============================================================ */}
      <div className="story-panel mx-auto max-w-5xl rounded-2xl bg-slate-900/50 p-10 sm:p-14 backdrop-blur-lg mb-20">
        <h2 className="font-display text-2xl sm:text-3xl font-bold text-[#00D4FF] mb-8 tracking-tight">
          How ArchVision Started
        </h2>

        <div className="space-y-6 text-[#94A3B8] text-base sm:text-lg leading-relaxed">
          <p>
            We are a group of friends and classmates currently in our 6th
            Semester at the{" "}
            <span className="text-[#38BDF8] font-medium">
              Institute of Advanced Research (IAR)
            </span>
            . What started as late-night tech debates quickly evolved into a
            shared ambition: we didn&apos;t just want to build another basic web
            app for our semester project. We wanted to tackle a complex,
            real-world engineering problem from scratch.
          </p>

          <p>
            Recognizing the massive gap between static architectural drawings
            and modern digital data, we decided to build a true{" "}
            <span className="text-[#38BDF8] font-medium">
              end-to-end Deep Learning and Computer Vision pipeline
            </span>
            . Countless cups of coffee, hundreds of OpenCV contour debugging
            sessions, and a few OCR headaches later,{" "}
            <span className="text-gradient-cyan-purple font-semibold">
              ArchVision
            </span>{" "}
            was born.
          </p>

          <p>
            We built this to prove what undergraduate engineers can do when they
            push the limits of modern AI.
          </p>
        </div>
      </div>

      {/* ============================================================ */}
      {/*  SECTION HEADING                                              */}
      {/* ============================================================ */}
      <div className="mx-auto max-w-5xl text-center mb-14">
        <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight text-gradient-cyan-purple">
          Meet the Founders
        </h2>
        <p className="mt-3 text-[#94A3B8] text-sm sm:text-base">
          The engineers behind the pipeline.
        </p>
      </div>

      {/* ============================================================ */}
      {/*  FOUNDERS GRID                                                */}
      {/* ============================================================ */}
      <div className="mx-auto max-w-6xl flex flex-wrap justify-center gap-8">
        {founders.map((f) => (
          <div
            key={f.name}
            className="founder-card glass-panel group relative flex w-full flex-col items-center rounded-2xl p-8 text-center transition-all duration-300 hover:scale-[1.02] sm:w-[calc(50%-1rem)] lg:w-[calc(33.333%-1.375rem)]"
          >
            {/* Avatar */}
            <div className="avatar-pulse relative mb-5 flex h-20 w-20 items-center justify-center rounded-full border-2 border-[#0EA5E9]/30 bg-gradient-to-br from-[#0EA5E9]/20 to-[#818CF8]/20 text-2xl font-bold text-white select-none">
              {f.avatar}
            </div>

            {/* Name */}
            <h3 className="font-display text-lg font-bold tracking-tight text-white">{f.name}</h3>

            {/* Role */}
            <p className="mt-1 text-xs font-medium uppercase tracking-wider text-[#38BDF8]">
              {f.role}
            </p>

            {/* Bio */}
            <p className="mt-4 flex-1 text-sm leading-relaxed text-[#94A3B8]">
              {f.bio}
            </p>

            {/* Social Links */}
            <div className="relative z-10 mt-6 flex items-center gap-4">
              {f.github && (
                <a
                  href={f.github}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="cursor-pointer rounded-lg p-2 text-[#94A3B8] transition-all duration-300 hover:scale-110 hover:drop-shadow-[0_0_8px_rgba(0,240,255,0.8)] hover:bg-[#0EA5E9]/10 hover:text-[#0EA5E9]"
                  aria-label={`${f.name} GitHub`}
                >
                  <Github className="h-5 w-5" />
                </a>
              )}
              {f.linkedin && (
                <a
                  href={f.linkedin}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="cursor-pointer rounded-lg p-2 text-[#94A3B8] transition-all duration-300 hover:scale-110 hover:drop-shadow-[0_0_8px_rgba(0,240,255,0.8)] hover:bg-[#0EA5E9]/10 hover:text-[#0EA5E9]"
                  aria-label={`${f.name} LinkedIn`}
                >
                  <Linkedin className="h-5 w-5" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
