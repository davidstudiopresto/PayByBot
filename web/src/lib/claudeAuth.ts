/** The authorization Claude asked for (« #/autoriser?r=… »), kept for this tab while the user signs in or signs up:
 *  after the sign-up's code, back to « Autoriser Claude » instead of the dashboard. Sealed by the server, expires in
 *  15 minutes (the server refuses it after that anyway). */
const KEY = 'pbb-claude-auth'
const TTL = 15 * 60 * 1000

export function keepClaudeAuth(r: string) {
  try {
    if (r) sessionStorage.setItem(KEY, JSON.stringify({ r, at: Date.now() }))
  } catch {
    // storage blocked: the user reconnects from Claude
  }
}

export function pendingClaudeAuth(): string | null {
  try {
    const kept = JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as { r: string; at: number } | null
    return kept && Date.now() - kept.at < TTL ? kept.r : null
  } catch {
    return null
  }
}

export function clearClaudeAuth() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // nothing kept
  }
}
