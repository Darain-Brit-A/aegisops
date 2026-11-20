/**
 * Minimal AegisOps Frontend scaffold.
 * Owned by Member 04 (Darain). See docs/HANDOFF_DARAIN.md and docs/DESIGN_SYSTEM.md.
 */
export default function App() {
  return (
    <main
      style={{
        minHeight: "100vh",
        backgroundColor: "var(--bg-canvas)",
        color: "var(--text-primary)",
        padding: "2rem",
      }}
    >
      <header style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1rem" }}>
        <h1 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 600 }}>AegisOps</h1>
        <p style={{ margin: "0.25rem 0 0", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          Observe everything. Expose nothing.
        </p>
      </header>
      <section style={{ marginTop: "1.5rem", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
        <p className="mono">Status: Frontend scaffold ready for Member 04 (Darain) implementation.</p>
      </section>
    </main>
  );
}
