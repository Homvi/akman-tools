"use client";

export function TopProgress({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div className="fixed left-0 right-0 top-0 z-50 h-0.5 overflow-hidden bg-[#27272A]">
      <div className="top-progress-bar h-full bg-[#2DD4BF]" />
    </div>
  );
}
