import { cn } from '@/lib/utils'

/** Each link with its short name for a phone (the footer on two short lines there, not five). */
const LINKS = [
  ['#/securite', 'Sécurité et données', 'Sécurité'],
  ['#/confidentialite', 'Confidentialité', 'Confidentialité'],
  ['#/cgu', "Conditions d'utilisation", 'CGU'],
  ['#/mentions-legales', 'Mentions légales', 'Mentions'],
  ['mailto:contact@paybybot.fr', 'contact@paybybot.fr', 'Contact'],
]

/** Legal links everywhere, and that PayByBot is not PayByPhone. */
export function HostedFooter({ className }: { className?: string; hosted?: boolean; linksOnly?: boolean }) {
  return (
    <footer className={cn('space-y-2 text-center text-sm text-ink/60 max-sm:space-y-1 max-sm:text-xs', className)}>
      <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 max-sm:gap-x-3" aria-label="Informations">
        {LINKS.map(([href, label, short]) => (
          <a key={href} href={href} aria-label={label} className="underline-offset-4 hover:text-ink hover:underline">
            <span className="sm:hidden">{short}</span>
            <span className="max-sm:hidden">{label}</span>
          </a>
        ))}
      </nav>
      {/* Said everywhere, not only in the legal pages: an independent service, not PayByPhone's. */}
      <p className="text-balance text-ink/45">
        <span className="max-sm:hidden">PayByBot est un service indépendant, non affilié à PayByPhone.</span>
        <span className="sm:hidden">Service indépendant, non affilié à PayByPhone.</span>
      </p>
    </footer>
  )
}
