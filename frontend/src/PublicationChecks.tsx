export function PublicationChecks({ items }: { items: { text: string; target: string }[] }) {
  function focusRequirement(id: string) {
    const target = document.getElementById(id);
    if (!target) return;
    let ancestor = target.parentElement;
    while (ancestor) { if (ancestor instanceof HTMLDetailsElement) ancestor.open = true; ancestor = ancestor.parentElement; }
    target.scrollIntoView({ block: "center" });
    (target.matches("input, textarea, button") ? target : target.querySelector<HTMLElement>("input, textarea") || target.querySelector<HTMLElement>("button"))?.focus({ preventScroll: true });
  }
  return <section className="publication-checks" aria-label="Publication checks"><h2>Before publishing</h2>
    {items.length ? <ul>{items.map(item => <li key={item.target}><button className="text-link" type="button" onClick={() => focusRequirement(item.target)}>{item.text}</button></li>)}</ul> : <p>All checks complete. Ready to publish.</p>}
  </section>;
}
