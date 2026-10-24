export interface Recovery { title: string; content: string; base_version: number }
export function readRecovery(id: string): Recovery | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(`blog-gen:draft:${id}`) || 'null');
    return value && typeof value.title === 'string' && typeof value.content === 'string' && Number.isInteger(value.base_version) ? value : null;
  } catch { return null; }
}
export function storeRecovery(id: string, value: Recovery) { sessionStorage.setItem(`blog-gen:draft:${id}`, JSON.stringify(value)); }
export function clearRecovery(id: string) { sessionStorage.removeItem(`blog-gen:draft:${id}`); }
export function sameText(a: { title: string; content: string }, b: { title: string; content: string }) { return a.title === b.title && a.content === b.content; }

// A save from an unmounted editor must not clear a newer editor's buffer.
export function acknowledgeRecovery(id: string, saved: Recovery, current: Recovery, normalized: Recovery = current) {
  const stored = readRecovery(id);
  if (stored && !sameText(stored, current)) return;
  if (sameText(saved, normalized)) clearRecovery(id);
  else storeRecovery(id, { ...normalized, base_version: saved.base_version });
}
