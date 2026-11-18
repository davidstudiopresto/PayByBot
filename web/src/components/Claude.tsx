import { useEffect, useState } from 'react'
import { Check, Copy, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { PayByBot } from '@/components/signs'
import { api } from '@/lib/api'
import { ui } from '@/lib/styles'
import { cn } from '@/lib/utils'

/** « Claude » in the dashboard's bar, beside « Inviter un proche »: how to add PayByBot to Claude (3 steps and the
 *  address to copy), or since when it is connected, with « Déconnecter ». */
export function ClaudeButton({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)} disabled={disabled} className={cn(ui.pillBlue, 'gap-2')}>
        <Sparkles className="size-4" /> <span className="hidden lg:inline">Utiliser avec Claude</span>
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

  const steps = [
    <>Dans Claude : <b className="font-medium text-ink">Réglages › Connecteurs › Ajouter un connecteur personnalisé</b>.</>,
    <>
      Collez cette adresse :
      <span className="mt-2 flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg bg-ink/[0.05] px-3 py-2 font-mono text-[0.9rem] text-ink">{address}</code>
        <button onClick={copy} className={cn(ui.pillGray, 'shrink-0 gap-1.5')}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />} {copied ? 'Copiée' : 'Copier'}
        </button>
      </span>
    </>,
    <>Cliquez <b className="font-medium text-ink">Se connecter</b>, puis <b className="font-medium text-ink">Autoriser</b>.</>,
  ]

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={ui.dialog}>
        <div className="space-y-5 p-6 pt-7">
          <div>
            <DialogTitle className={ui.dialogTitle}>Utiliser avec Claude</DialogTitle>
            <DialogDescription className="mt-1 text-ink/60">
              Demandez à Claude vos tickets, une pause ou un renouvellement, en une phrase. Il passe par <PayByBot />, sans
              jamais voir votre mot de passe.
            </DialogDescription>
          </div>
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
            <ol className="space-y-4">
              {steps.map((step, i) => (
                <li key={i} className="flex gap-3 text-[0.95rem] leading-relaxed text-ink/70">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-eu/[0.08] text-sm font-semibold text-eu">{i + 1}</span>
                  <span className="min-w-0 flex-1">{step}</span>
                </li>
              ))}
            </ol>
          )}
          {since === undefined && <Loader2 className="mx-auto size-4 animate-spin text-ink/45" />}
        </div>
      </DialogContent>
    </Dialog>
  )
}
