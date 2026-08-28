import type { ButtonHTMLAttributes, HTMLAttributes, PropsWithChildren } from "react";
import { cn } from "../lib";

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const variants = {
    primary: "bg-sage-700 text-white hover:bg-sage-900",
    secondary: "bg-sage-100 text-sage-900 hover:bg-sage-300/60",
    ghost: "bg-transparent text-sage-700 hover:bg-sage-100",
    danger: "bg-red-100 text-red-800 hover:bg-red-200",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Badge({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <span className={cn("rounded-full bg-sage-100 px-3 py-1 text-xs font-medium text-sage-700", className)}>{children}</span>;
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("surface p-5", className)} {...props} />;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-sage-300 bg-white/40 px-6 py-12 text-center">
      <p className="font-semibold text-ink">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{body}</p>
    </div>
  );
}

