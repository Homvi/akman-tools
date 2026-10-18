import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-xs font-medium text-[#A1A1AA]",
        className
      )}
      {...props}
    />
  );
}
