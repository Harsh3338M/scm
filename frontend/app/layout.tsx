import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'NexGen SCM Control Tower | Supply Chain Digital Twin',
  description:
    'Real-time supply chain anomaly detection and routing platform powered by Vertex AI, AlloyDB, and Google Cloud Pub/Sub.',
  keywords: ['supply chain', 'digital twin', 'anomaly detection', 'logistics', 'Google Cloud'],
  authors: [{ name: 'NexGen SCM Team' }],
  openGraph: {
    title: 'NexGen SCM Control Tower',
    description: 'Real-time supply chain anomaly detection platform',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
      </head>
      <body className="bg-[#080b14] text-slate-100 font-sans antialiased min-h-screen">
        {/* Ambient background glow effects */}
        <div
          aria-hidden="true"
          className="fixed inset-0 pointer-events-none overflow-hidden -z-10"
        >
          <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-neon-400/5 rounded-full blur-[120px]" />
          <div className="absolute top-1/2 -right-40 w-[400px] h-[400px] bg-violet-500/5 rounded-full blur-[100px]" />
          <div className="absolute bottom-0 left-1/3 w-[300px] h-[300px] bg-midnight-700/20 rounded-full blur-[80px]" />
        </div>
        {children}
      </body>
    </html>
  )
}
