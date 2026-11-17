import Link from "next/link";
import { ArrowRight } from "lucide-react";

const FEATURES = [
  ["01", "Ask your workspace", "Questions answered from your documents, meeting notes and records — every claim cited back to its source."],
  ["02", "Meeting intelligence", "Drop in a transcript. Get the decisions, action items, owners and deadlines pulled out for you."],
  ["03", "Decision tracker", "A searchable record of what was decided, why, who approved it, and whether it still stands."],
  ["04", "Action items", "Every open task in one list. Overdue and ownerless work is impossible to miss."],
  ["05", "Knowledge gaps", "Unanswered questions, stale documents and contradicting sources, surfaced before they bite."],
  ["06", "Team workspace", "Projects, shared documents, roles and permissions, and chat history that persists."],
];

const PROBLEMS = [
  "Decisions happen in meetings and evaporate.",
  "Answers get buried in chat threads.",
  "Requirements live in five versions of the same PDF.",
  "Nobody remembers who owned the task.",
  "New hires ask what was already answered.",
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b-2 border-ink px-8 py-4">
        <span className="display text-xl">WorkflowWise</span>
        <nav className="flex items-center gap-6">
          <a href="#features" className="label hover:underline">Features</a>
          <Link
            href="/login"
            className="label border-2 border-ink bg-ink px-4 py-2 font-bold text-paper hover:bg-acid hover:text-ink"
          >
            Sign in
          </Link>
        </nav>
      </header>

      <section className="grid-bg grid grid-cols-12 border-b-2 border-ink">
        <div className="col-span-12 border-ink px-8 py-20 lg:col-span-8 lg:border-r-2">
          <p className="label mb-6 inline-block bg-acid px-2 py-1 font-bold">Team knowledge &amp; decision intelligence</p>
          <h1 className="display text-[clamp(3rem,8vw,7.5rem)]">
            Your team&apos;s
            <br />
            institutional
            <br />
            <span className="bg-ink px-3 text-paper">memory.</span>
          </h1>
          <p className="mt-8 max-w-xl text-lg leading-relaxed">
            WorkflowWise remembers what your team knows, what it decided, and what needs to happen next — and shows
            its sources.
          </p>
          <div className="mt-10 flex gap-4">
            <Link
              href="/login"
              className="inline-flex h-12 items-center gap-2 border-2 border-ink bg-acid px-6 font-mono text-sm font-bold uppercase tracking-widest shadow-[var(--shadow-hard)] hover:-translate-x-px hover:-translate-y-px"
            >
              Open your workspace <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
        <div className="col-span-12 flex flex-col justify-center bg-ink px-8 py-12 text-paper lg:col-span-4">
          <p className="label mb-6 text-acid">The problem / 10-person startup</p>
          <ol className="space-y-4">
            {PROBLEMS.map((p, i) => (
              <li key={p} className="flex gap-4 border-b border-paper/20 pb-4 last:border-0">
                <span className="font-mono text-xs text-acid">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-lg leading-snug">{p}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="features" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        {FEATURES.map(([n, title, body]) => (
          <article key={n} className="group border-b-2 border-r-2 border-ink p-8 hover:bg-acid">
            <span className="font-mono text-sm">{n}</span>
            <h2 className="display mt-6 text-3xl">{title}</h2>
            <p className="mt-4 max-w-sm leading-relaxed text-muted group-hover:text-ink">{body}</p>
          </article>
        ))}
      </section>

      <footer className="flex items-center justify-between px-8 py-6">
        <span className="label">WorkflowWise</span>
        <span className="label text-muted">Next.js · FastAPI · Supabase · pgvector · Gemini</span>
      </footer>
    </div>
  );
}
