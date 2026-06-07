import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-[6px] px-5 py-3 text-sm font-extrabold transition-[background-color,color,border-color,box-shadow,transform] duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 active:translate-y-px disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[var(--accent)] text-white shadow-[0_16px_34px_rgba(7,91,99,0.22)] hover:bg-[var(--accent-strong)] focus-visible:outline-[var(--accent)]",
        secondary: "border border-[var(--line-strong)] bg-white text-[var(--ink)] hover:border-[var(--accent)] hover:text-[var(--accent)] focus-visible:outline-[var(--accent)]",
        ghost: "text-[var(--ink)] hover:bg-[var(--accent-soft)] hover:text-[var(--accent)] focus-visible:outline-[var(--accent)]",
      },
      size: {
        default: "h-11",
        lg: "min-h-13 px-7 text-base",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { buttonVariants };
