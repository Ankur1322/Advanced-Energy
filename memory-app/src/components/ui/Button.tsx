import type { ButtonHTMLAttributes, PropsWithChildren } from "react";
import { cn } from "../../lib/utils";

export function Button({ className, children, ...props }: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>) {
  return <button className={cn("inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-50", className)} {...props}>{children}</button>;
}