import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-[#27272A] bg-[#09090B] px-3 py-1 text-sm text-[#FAFAFA] shadow-none placeholder:text-[#71717A] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2DD4BF]/35",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";
