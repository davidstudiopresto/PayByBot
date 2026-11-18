import { useEffect, useState } from 'react'
import { Check, Copy, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import { ui } from '@/lib/styles'
import { cn } from '@/lib/utils'

/** « Claude » in the dashboard's bar, beside « Inviter un proche »: how to add PayByBot to Claude (3 steps and the
 *  address to copy), or since when it is connected, with « Déconnecter ». */
export function ClaudeButton({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)} disabled={disabled} aria-label="Utiliser avec Claude" className={cn(ui.pillGray, 'gap-2')}>
        <ClaudeMark className="size-[1.15rem]" /> <span className="hidden lg:inline">Claude</span>
      </button>
      {open && <ClaudeDialog onClose={() => setOpen(false)} />}
    </>
  )
}

function ClaudeDialog({ onClose }: { onClose: () => void }) {
  const address = `${window.location.origin}/mcp`
  const [since, setSince] = useState<string | null | undefined>(undefined)
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api.account().then((a) => setSince(a.claudeSince ?? null), () => setSince(null))
  }, [])

  async function copy() {
    try {
      await navigator.clipboard.writeText(address)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.message(address)
    }
  }
  async function disconnect() {
    setBusy(true)
    try {
      await api.disconnectClaude()
      setSince(null)
      toast.success('Claude est déconnecté.')
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={ui.dialog}>
        <div className="space-y-5 p-6 pt-7">
          <div className="flex items-center gap-3">
            <ClaudeMark className="size-7" />
            <DialogTitle className={ui.dialogTitle}>Utiliser avec Claude</DialogTitle>
          </div>
          <DialogDescription className="sr-only">L'adresse du connecteur PayByBot, à coller dans Claude.</DialogDescription>
          {since ? (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-ink/10 bg-white px-4 py-3">
              <span className="min-w-0">
                <span className="block text-ink">Connecté</span>
                <span className="block text-sm text-ink/60">
                  depuis le {new Date(since).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })}
                </span>
              </span>
              <button onClick={disconnect} disabled={busy} className={cn(ui.pillGray, 'shrink-0 gap-1.5')}>
                {busy && <Loader2 className="size-3.5 animate-spin" />}
                Déconnecter
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <button
                onClick={copy}
                className="flex h-14 w-full items-center justify-between gap-3 rounded-xl border border-ink/10 bg-white pr-2 pl-4 text-left transition hover:border-ink/25"
              >
                <span className="min-w-0 truncate font-mono text-[0.95rem] text-ink">{address.replace(/^https?:\/\//, '')}</span>
                <span className={cn(ui.pillBlue, 'h-10 shrink-0 gap-1.5')}>
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />} {copied ? 'Copiée' : 'Copier'}
                </span>
              </button>
              <p className="text-sm text-ink/60">À coller dans Claude › Réglages › Connecteurs.</p>
            </div>
          )}
          {since === undefined && <Loader2 className="mx-auto size-4 animate-spin text-ink/45" />}
        </div>
      </DialogContent>
    </Dialog>
  )
}

/** Claude's mark (its spark, in Claude's orange), redrawn: shows at a glance, even without the word, what the button is. */
export function ClaudeMark({ className }: { className?: string }) {
  const rays = Array.from({ length: 12 }, (_, i) => i * 30)
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <g fill="#D97757" transform="translate(12 12)">
        {rays.map((a, i) => (
          <rect key={a} x="-1.15" y={i % 2 ? -10 : -11.5} width="2.3" height={i % 2 ? 8.5 : 10} rx="1.15" transform={`rotate(${a + (i % 3) * 4})`} />
        ))}
      </g>
    </svg>
  )
}
