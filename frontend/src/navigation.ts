let guard: (() => boolean) | null = null;
const indexKey = "mededgeNavigationIndex";
let index = typeof window !== "undefined" && Number.isInteger(window.history.state?.[indexKey]) ? window.history.state[indexKey] as number : 0;
let restoring = false;

if (typeof window !== "undefined") {
  window.history.replaceState({ ...window.history.state, [indexKey]: index }, "");
  window.addEventListener("popstate", (event) => {
    if (event.state?.mededgeInternalNavigation) return;
    if (restoring) { restoring = false; event.stopImmediatePropagation(); return; }
    const nextIndex = event.state?.[indexKey];
    if (guard && !guard()) {
      event.stopImmediatePropagation();
      if (Number.isInteger(nextIndex) && nextIndex !== index) {
        restoring = true;
        window.history.go(index - nextIndex);
      }
      return;
    }
    if (Number.isInteger(nextIndex)) index = nextIndex;
  }, true);
}

/** Only one editable workspace is mounted at a time. */
export function registerNavigationGuard(next: () => boolean): () => void {
  guard = next;
  return () => { if (guard === next) guard = null; };
}

export function confirmNavigation(): boolean {
  return !restoring && (!guard || guard());
}

export function navigate(to: string, replace = false, confirmed = false): boolean {
  if (restoring || (!confirmed && !confirmNavigation())) return false;
  if (!replace) index++;
  const state = { [indexKey]: index };
  if (replace) window.history.replaceState(state, "", to);
  else window.history.pushState(state, "", to);
  window.dispatchEvent(new PopStateEvent("popstate", { state: { ...state, mededgeInternalNavigation: true } }));
  window.scrollTo(0, 0);
  return true;
}
