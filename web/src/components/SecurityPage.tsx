import { ui } from '@/lib/styles'
import type { ReactNode } from 'react'
import { Building2, KeyRound, Lock, ShieldCheck } from 'lucide-react'
import { HostedFooter } from '@/components/Footer'
import { LEGAL_UPDATED, Mailto, PUBLISHER } from '@/components/Legal'
import { PublicTopBar } from '@/components/TopBar'

const PRACTICE = [
  [Lock, 'Chiffrement', 'AES-128 avec signature HMAC-SHA256, une clé distincte par usage. HTTPS imposé partout (HSTS).'],
  [Building2, 'Hébergement en UE', 'Application et base de données hébergées à Paris, dans l’Union européenne.'],
  [KeyRound, 'Zéro mot de passe stocké', 'Seul un jeton de connexion chiffré est utilisé, effacé au bout de 24 h au plus.'],
  [ShieldCheck, 'Accès verrouillé', 'Base de données fermée, tentatives de connexion limitées, requêtes d’autres sites refusées, vérification anti-robots à l’inscription et à la connexion, pare-feu qui bloque les appels en rafale.'],
] as const

const FRAMEWORK: { title: string; icon: typeof Lock; rows: [string, ReactNode][] }[] = [
  {
    title: 'Chiffrement',
    icon: Lock,
    rows: [
      ['Algorithme', 'AES-128-CBC + HMAC-SHA256'],
      ['Clés', 'Une par usage, rotation possible'],
      ['Transport', 'HTTPS (TLS), HSTS 2 ans'],
      ['Mots de passe', 'Jamais stockés'],
    ],
  },
  {
    title: 'RGPD',
    icon: ShieldCheck,
    rows: [
      ['Responsable', `${PUBLISHER.name}, Paris`],
      ['Hébergement', 'Union européenne (Paris)'],
      ['Droits garantis', 'Accès, rectification, effacement, portabilité'],
      ['Réclamation', 'Auprès de la CNIL'],
    ],
  },
]

const SUBPROCESSORS = [
  ['Vercel', 'Hébergement de l’application', 'Paris (UE)', 'ISO 27001, SOC 2'],
  ['Supabase', 'Base de données des renouvellements', 'Paris (UE)', 'SOC 2'],
  ['Resend', 'E-mails de confirmation', 'Irlande (UE)', 'SOC 2'],
  ['Stripe', 'Paiement de l’abonnement', 'Irlande (UE)', 'PCI DSS niveau 1, SOC 2'],
]

/** « Sécurité », in the top bar: laid out like the other public pages (top bar, title and subtitle, then cards and
 *  label / value rows, as in « Mon compte »). */
export function SecurityPage({ hosted, signedIn = false }: { hosted: boolean; signedIn?: boolean }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-ink">
      <PublicTopBar signedIn={signedIn} />
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 pt-16 pb-20 sm:pt-20">
        <h1 className={ui.title}>Sécurité et données</h1>
        <p className={ui.subtitle}>
          Votre mot de passe n’est jamais stocké. Vos données sont chiffrées, hébergées à Paris, et effacées dès que vous
          arrêtez.
        </p>

        {/* The four guarantees, as plain text: an icon, a title, one sentence. */}
        <ul className="mt-12 grid gap-x-10 gap-y-8 sm:grid-cols-2">
          {PRACTICE.map(([Icon, title, text]) => (
            <li key={title}>
              <Icon className="size-5 text-eu" strokeWidth={1.75} aria-hidden />
              <p className="mt-3 text-[1.05rem] font-medium text-ink">{title}</p>
              <p className="mt-1 text-sm leading-relaxed text-ink/60">{text}</p>
            </li>
          ))}
        </ul>

        {FRAMEWORK.map(({ title, rows }) => (
          <Section key={title} title={title}>
            {rows.map(([k, v]) => (
              <Row key={k} label={k}>
                {v}
              </Row>
            ))}
          </Section>
        ))}

        <Section title="Sous-traitants">
          {SUBPROCESSORS.map(([name, role, where, certs]) => (
            <Row key={name} label={name}>
              <span className="block">{role}</span>
              <span className="block text-sm text-ink/60">
                {where} · {certs}
              </span>
            </Row>
          ))}
        </Section>

        <p className="mt-10 text-[0.95rem] text-ink/60">
          Une question sur la sécurité ? <Mailto />
        </p>
        <p className="mt-2 text-sm text-ink/45">Dernière mise à jour le {LEGAL_UPDATED}</p>
      </main>
      <HostedFooter className="px-6 pb-8" hosted={hosted} />
    </div>
  )
}

/** A titled list of rows, plain text between hairlines (no box). */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-[1.05rem] text-ink/60">{title}</h2>
      <div className="mt-3 divide-y divide-ink/10 border-y border-ink/10">{children}</div>
    </section>
  )
}

/** One row: the label on the left, the value on the right. */
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-h-12 items-center justify-between gap-6 py-3 text-[0.95rem]">
      <span className="shrink-0 text-ink/60">{label}</span>
      <span className="min-w-0 text-right text-ink">{children}</span>
    </div>
  )
}
