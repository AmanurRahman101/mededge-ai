let guard: (() => boolean) | null = null;
const indexKey = "mededgeNavigationIndex";
let index = typeof window !== "undefined" && Number.isInteger(window.history.state?.[indexKey]) ? window.history.state[indexKey] as number : 0;
let restoring = false;
const scrollPositions = new Map<string, number>();
const locationKey = () => window.location.pathname + window.location.search;
export function restorePageScroll() {
  const y = scrollPositions.get(locationKey());
  if (y !== undefined) requestAnimationFrame(() => window.scrollTo(0, y));
}

export function doctorChartUrl(patientId: string, page = 0) {
  return `/doctor?${new URLSearchParams({ patient: patientId, section: "history", ...(page ? { page: String(page) } : {}) })}`;
}
export function doctorRecordUrl(runId: string, patientId: string, offset = 0) {
  return `/doctor/records/${encodeURIComponent(runId)}?${new URLSearchParams({ patient: patientId, page: String(Math.floor(offset / 20)) })}`;
}
export function recordReturnUrl(patientId?: string) {
  if (!patientId) return "/doctor";
  const params = new URLSearchParams(window.location.search);
  const page = params.get("patient") === patientId ? Math.max(0, Number(params.get("page")) || 0) : 0;
  return doctorChartUrl(patientId, page);
}

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
  scrollPositions.set(locationKey(), window.scrollY);
  if (!replace) index++;
  const state = { [indexKey]: index };
  if (replace) window.history.replaceState(state, "", to);
  else window.history.pushState(state, "", to);
  window.dispatchEvent(new PopStateEvent("popstate", { state: { ...state, mededgeInternalNavigation: true } }));
  window.scrollTo(0, scrollPositions.get(locationKey()) ?? 0);
  return true;
}
