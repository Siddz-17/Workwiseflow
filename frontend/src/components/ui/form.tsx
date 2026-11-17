import * as React from "react";

import { cn } from "@/lib/utils";

const field =
  "w-full border-2 border-ink bg-white px-3 font-sans text-sm text-ink placeholder:text-muted/70 focus:outline-none focus:shadow-[var(--shadow-hard-sm)] focus:-translate-x-px focus:-translate-y-px transition-[transform,box-shadow] duration-75 disabled:opacity-50";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input data-slot="input" className={cn(field, "h-10", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea data-slot="textarea" className={cn(field, "min-h-28 py-2 leading-relaxed", className)} {...props} />;
}

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      data-slot="select"
      className={cn(
        field,
        "h-10 cursor-pointer appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22><path d=%22M1 3h10L6 9z%22 fill=%22%230b0b0b%22/></svg>')] bg-[length:10px] bg-[right_12px_center] bg-no-repeat pr-8",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label data-slot="label" className={cn("label mb-1.5 block text-ink", className)} {...props} />;
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
      {hint && <p className="mt-1 font-mono text-[11px] text-muted">{hint}</p>}
    </div>
  );
}
