let guard: (() => boolean) | null = null;

/** Only one editable workspace is mounted at a time. */
export function registerNavigationGuard(next: () => boolean): () => void {
  guard = next;
  return () => { if (guard === next) guard = null; };
}

export function navigate(to: string, replace = false): void {
  if (guard && !guard()) return;
  if (replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
}
