import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap border-2 border-ink font-mono text-xs font-bold uppercase tracking-[0.1em] transition-[transform,box-shadow] duration-75 disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-2 focus-visible:ring-offset-paper [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-ink text-paper hover:bg-ink/85 active:translate-y-px",
        accent:
          "bg-acid text-ink shadow-[var(--shadow-hard)] hover:-translate-x-px hover:-translate-y-px active:translate-x-1 active:translate-y-1 active:shadow-none",
        outline:
          "bg-paper text-ink shadow-[var(--shadow-hard-sm)] hover:bg-paper-2 active:translate-x-0.5 active:translate-y-0.5 active:shadow-none",
        ghost: "border-transparent bg-transparent text-ink hover:border-ink hover:bg-paper-2",
        danger:
          "bg-signal text-ink shadow-[var(--shadow-hard-sm)] active:translate-x-0.5 active:translate-y-0.5 active:shadow-none",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-8 px-3 text-[11px]",
        lg: "h-12 px-6 text-sm",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { buttonVariants };
