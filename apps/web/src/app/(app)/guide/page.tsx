export default function GuidePage() {
  return (
    <div className="prose prose-sm max-w-2xl text-[#111827]">
      <h1 className="text-2xl font-semibold">Guide</h1>
      <p className="text-[#6B7280]">
        Upload Progressliste + Gesamtliste on All cables. Filters apply server-side. Exports stay on the API
        (CaTra / Kurzliste). Streamlit remains available locally until cutover.
      </p>
      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-[#6B7280]">
        <li>Deploy: Docker Compose on Hetzner — see deploy/HETZNER.md</li>
        <li>Design: docs/design-system.md</li>
        <li>Auth: email/password with roles admin / planner / worker</li>
      </ul>
    </div>
  );
}
