import { Avatar } from '@heroui/react'
import { HostedFooter } from '@/components/Footer'
import { PUBLISHER } from '@/components/Legal'
import { PayByBot } from '@/components/signs'
import { PublicTopBar } from '@/components/TopBar'
import { ui } from '@/lib/styles'

const STUDIO_URL = 'https://studiopresto.fr/'

// The founders; `photo` stays empty until the pictures are ready (their initials show in the meantime).
const FOUNDERS: { name: string; role: string; photo?: string; linkedin: string }[] = [
  { name: 'Rafaël Maurin', role: 'Cofondateur, CEO', photo: '/team/rafael.webp', linkedin: 'https://www.linkedin.com/in/rafa%C3%ABl-maurin-040652205/' },
  { name: 'David Guenoun', role: 'Cofondateur, CTO', photo: '/team/david.webp', linkedin: 'https://www.linkedin.com/in/david-guenoun-2758b9133/' },
]

/** LinkedIn's « in » mark (Simple Icons), in the current colour. */
function LinkedInIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z" />
    </svg>
  )
}

const initials = (name: string) =>
  name
    .split(' ')
    .map((w) => w[0])
    .join('')

/** « Qui sommes-nous », in the top bar: who runs PayByBot. Text only. */
export function AboutPage({ hosted, signedIn = false }: { hosted: boolean; signedIn?: boolean }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-ink">
      <PublicTopBar signedIn={signedIn} />
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 pt-16 pb-20 sm:pt-20">
        <h1 className={ui.title}>Qui sommes-nous</h1>
        <p className={ui.subtitle}>
          <PayByBot /> est un service français, édité par{' '}
          <a href={STUDIO_URL} target="_blank" rel="noopener noreferrer" className={ui.link}>
            {PUBLISHER.name}
          </a>
          , une société basée à Paris.
        </p>

        <hr className="mt-8 border-ink/10" />
        {/* One row per founder: the face, then the name over the role, the LinkedIn mark at the end. */}
        <ul aria-label="Les fondateurs" className="mt-8 grid gap-6 sm:grid-cols-2">
          {FOUNDERS.map((f) => (
            <li key={f.name} className="flex items-center gap-4">
              <Avatar className="size-20 shrink-0">
                {f.photo && <Avatar.Image src={f.photo} alt={f.name} />}
                <Avatar.Fallback>{initials(f.name)}</Avatar.Fallback>
              </Avatar>
              <span className="min-w-0 flex-1">
                <span className="block text-[1.05rem] font-medium text-ink">{f.name}</span>
                <span className="block text-sm text-ink/60">{f.role}</span>
              </span>
              <a
                href={f.linkedin}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`${f.name} sur LinkedIn`}
                className="-m-2 shrink-0 p-2 text-ink/35 transition hover:text-[#0a66c2]"
              >
                <LinkedInIcon className="size-[18px]" />
              </a>
            </li>
          ))}
        </ul>
      </main>
      <HostedFooter className="px-6 pb-8" hosted={hosted} />
    </div>
  )
}
