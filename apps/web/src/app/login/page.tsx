"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/login", { email, password });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#09090B] px-4">
      <TopProgress show={loading} />
      <div className="w-full max-w-md rounded-md border border-[#27272A] bg-[#0C0C0E] p-8">
        <h1 className="text-3xl font-semibold tracking-tight text-[#FAFAFA]">Cable installation</h1>
        <p className="mt-2 text-sm text-[#71717A]">
          Sign in to manage <span className="text-[#2DD4BF]">Progressliste</span> and{" "}
          <span className="text-[#F97316]">Gesamtliste</span>.
        </p>
        <form className="mt-8 space-y-4" onSubmit={onSubmit}>
          <label className="block text-xs text-[#71717A]">
            Email
            <Input className="mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block text-xs text-[#71717A]">
            Password
            <Input
              className="mt-1"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="text-sm text-[#F87171]">{error}</p>}
          <Button className="w-full" type="submit" disabled={loading}>
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
