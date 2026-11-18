import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { PublicTopBar } from '@/components/TopBar'
import { PayByBot, PayByPhone } from '@/components/signs'
import { Notice } from '@/components/ui/notice'
import { api, type Me } from '@/lib/api'
import { clearClaudeAuth } from '@/lib/claudeAuth'
import { ui } from '@/lib/styles'
import { cn } from '@/lib/utils'

/** The request Claude opened this page with (« #/autoriser?r=… »), sealed by the server. */
function pendingRequest() {
  return new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('r') ?? ''
}

const CAN = [
  'Voir vos tickets en cours, vos véhicules et vos renouvellements',
  'Mettre en pause, reprendre, activer ou arrêter un renouvellement, toujours après vous avoir demandé',
]

/** « Autoriser Claude » : opened from Claude when PayByBot is added as a connector. The user is signed in already
 *  (else the sign-in comes first); one tap gives Claude its own access, never the PayByPhone password. */
export function Authorize({ me }: { me: Me }) {
  const r = pendingRequest()
  const [client, setClient] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState<'allow' | 'deny' | null>(null)

  useEffect(() => {
    if (!r) return setError('Lien incomplet. Reconnectez PayByBot depuis Claude.')
    api.oauthRequest(r).then(
      (x) => setClient(x.client),
      (e) => setError((e as Error).message),
    )
  }, [r])

  async function answer(allow: boolean) {
    setSending(allow ? 'allow' : 'deny')
    setError(null)
    try {
      const { redirect } = await api.oauthApprove(r, allow)
      clearClaudeAuth()
      window.location.href = redirect // back to Claude
    } catch (e) {
      setError((e as Error).message)
      setSending(null)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-background text-ink">
      <PublicTopBar signedIn />
      <main className="flex flex-1 items-start justify-center px-5 pt-10 pb-16 sm:items-center sm:pt-0">
        <div className="w-full max-w-[26rem] space-y-5 rounded-2xl border border-ink/10 bg-white p-6 shadow-[0_30px_60px_-28px_rgb(11_16_36/0.3),0_8px_18px_-10px_rgb(11_16_36/0.1)] sm:p-7">
          <div>
            <h1 className="font-heading text-[1.35rem] font-medium tracking-[-0.02em] text-ink">
              Autoriser {client ?? 'Claude'}
            </h1>
            <p className="mt-1 text-[0.95rem] text-ink/60">
              à accéder à votre compte <PayByBot />
              {me.username && !me.demo ? <> ({me.username.replace(/^\+33/, '0').replace(/(\d{2})(?=\d)/g, '$1 ')})</> : null}.
            </p>
          </div>
          <ul className="space-y-2.5 text-[0.95rem] text-ink">
            {CAN.map((line) => (
              <li key={line} className="flex gap-2.5">
                <Check className="mt-0.5 size-[1.1rem] shrink-0 text-eu" strokeWidth={2.25} aria-hidden />
                {line}
              </li>
            ))}
          </ul>
          <p className="text-sm leading-relaxed text-ink/60">
            Claude ne voit jamais votre mot de passe <PayByPhone />. Vous pouvez le déconnecter à tout moment dans Mon compte.
          </p>
          {error && <Notice>{error}</Notice>}
          <div className="space-y-2">
            <button
              type="button"
              disabled={!client || !!sending || (me.demo && me.hosted)}
              onClick={() => answer(true)}
              className={cn(
                ui.primary,
                'h-14 w-full rounded-xl border-0 bg-[linear-gradient(90deg,var(--eu)_0%,#2a66d1_100%)] text-lg text-white shadow-[0_14px_30px_-12px_var(--eu)] hover:bg-transparent hover:brightness-110 disabled:opacity-70',
              )}
            >
              {sending === 'allow' ? <Loader2 className="size-5 animate-spin" /> : 'Autoriser'}
            </button>
            <button
              type="button"
              disabled={!client || !!sending}
              onClick={() => answer(false)}
              className="h-11 w-full rounded-xl text-[0.95rem] text-ink/60 transition hover:text-ink disabled:opacity-60"
            >
              {sending === 'deny' ? <Loader2 className="mx-auto size-4 animate-spin" /> : 'Refuser'}
            </button>
          </div>
          {me.demo && me.hosted && <p className="text-center text-sm text-ink/60">Le compte de démonstration ne se connecte pas à Claude.</p>}
        </div>
      </main>
    </div>
  )
}
