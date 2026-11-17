import { HostedFooter } from '@/components/Footer'
import { HowItWorks } from '@/components/Landing'
import { PublicTopBar } from '@/components/TopBar'

/** « Comment ça marche », in the top bar: the three steps with their screens (the sign-up button is in the top bar). */
export function HowPage({ hosted, signedIn = false }: { hosted: boolean; signedIn?: boolean }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-ink">
      <PublicTopBar signedIn={signedIn} />
      {/* Centred in the window on a computer. */}
      <main className="mx-auto flex w-full max-w-[64rem] flex-1 flex-col px-6 pt-10 pb-16 lg:justify-center lg:py-6">
        {/* The three steps and the screen of the one shown beside it (as on the home page). */}
        <HowItWorks page />
      </main>
      <HostedFooter className="px-6 pb-8" hosted={hosted} />
    </div>
  )
}
