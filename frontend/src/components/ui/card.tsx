import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div data-slot="card" className={cn("border-2 border-ink bg-white shadow-[var(--shadow-hard)]", className)} {...props} />
  );
}

export function CardHeader({
  className,
  index,
  title,
  action,
}: {
  className?: string;
  index?: string;
  title: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-3 border-b-2 border-ink bg-paper-2 px-4 py-2", className)}>
      <div className="flex items-center gap-3">
        {index && <span className="label bg-ink px-1.5 py-0.5 text-paper">{index}</span>}
        <h3 className="label font-bold">{title}</h3>
      </div>
      {action}
    </div>
  );
}

const badgeVariants = cva("label inline-flex items-center gap-1 border-2 border-ink px-1.5 py-px text-[10px] font-bold", {
  variants: {
    tone: {
      default: "bg-white text-ink",
      ink: "bg-ink text-paper",
      acid: "bg-acid text-ink",
      signal: "bg-signal text-ink",
      cobalt: "bg-cobalt text-white",
      ok: "bg-ok text-white",
      muted: "bg-paper-2 text-muted border-muted",
    },
  },
  defaultVariants: { tone: "default" },
});

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="border-2 border-dashed border-ink/50 bg-paper px-6 py-10 text-center">
      <p className="display text-xl">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}
