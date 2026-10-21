import type { Metadata } from 'next'
import { Atkinson_Hyperlegible, Nunito } from 'next/font/google'
import './globals.css'

const nunito = Nunito({ subsets: ['latin'], variable: '--font-story', weight: ['400', '700', '800'] })
// designed for low-vision readers and often used for dyslexia: letters that can't be mistaken for each other
const atkinson = Atkinson_Hyperlegible({ subsets: ['latin'], variable: '--font-easy', weight: ['400', '700'] })

export const metadata: Metadata = {
  title: 'Cuentos a mi medida',
  description: 'Cuentos ilustrados y narrados para cada niño, al nivel de lectura de su edad',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${nunito.variable} ${atkinson.variable}`}>
      <body>{children}</body>
    </html>
  )
}
