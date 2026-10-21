'use client'

import Link from 'next/link'
import { use, useEffect, useRef, useState } from 'react'
import { getStory, STATUS, type StoryView } from '@/lib/api'

export default function Reader({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [story, setStory] = useState<StoryView | null>(null)
  const [page, setPage] = useState(0)
  const [easy, setEasy] = useState(false)
  const [now, setNow] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const audio = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    let stop = false
    const poll = async () => {
      const s = await getStory(id)
      if (stop) return
      setStory(s)
      if (s.status !== 'done' && s.status !== 'failed') setTimeout(poll, 3000)
    }
    poll()
    return () => {
      stop = true
    }
  }, [id])

  if (!story) return <main className="reader loading">Abriendo el cuento…</main>
  if (story.status !== 'done' || !story.pages) {
    return (
      <main className="reader loading">
        <Link href="/" className="back">← Biblioteca</Link>
        <div className="making">
          <div className="spinner" aria-hidden />
          <h2>{STATUS[story.status]}</h2>
          <p>Un cuento para {story.request.name}, sobre {story.request.likes}.</p>
        </div>
      </main>
    )
  }

  const p = story.pages[page]
  const r = story.readability
  const onTime = () => {
    const t = audio.current?.currentTime ?? 0
    setNow(p.cues.findIndex((c) => t >= c.start && t <= c.end + 0.35))
  }
  const goTo = (n: number) => {
    audio.current?.pause()
    setNow(-1)
    setPlaying(false)
    setPage(n)
  }
  const toggle = () => {
    if (!audio.current) return
    if (audio.current.paused) audio.current.play()
    else audio.current.pause()
  }

  return (
    <main className={easy ? 'reader easy' : 'reader'}>
      <div className="bar">
        <Link href="/" className="back">← Biblioteca</Link>
        <h1>{story.title}</h1>
        <label className="toggle">
          <input type="checkbox" checked={easy} onChange={(e) => setEasy(e.target.checked)} />
          Lectura fácil
        </label>
      </div>

      <article className="spread">
        <div className="picture">
          {p.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={p.image_url} alt={`Ilustración de la página ${page + 1}`} />
          ) : (
            <div className="no-picture">Esta página no tiene ilustración</div>
          )}
        </div>
        <div className="words">
          <p className="text">
            {p.cues.map((c, i) => (
              <span key={i} className={i === now ? 'cue now' : 'cue'}>
                {c.text}{' '}
              </span>
            ))}
          </p>
          <button className="listen" onClick={toggle}>
            {playing ? '❚❚ Pausa' : '▶ Escuchar'}
          </button>
          <audio ref={audio} src={p.audio_url} onTimeUpdate={onTime} onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)} onEnded={() => setNow(-1)} />
        </div>
      </article>

      <nav className="pager">
        <button onClick={() => goTo(page - 1)} disabled={page === 0}>← Anterior</button>
        <span>
          Página {page + 1} de {story.pages.length}
        </span>
        <button onClick={() => goTo(page + 1)} disabled={page === story.pages.length - 1}>Siguiente →</button>
      </nav>

      {r && (
        <footer className="level">
          Para {story.request.ages} años · índice de lectura Fernández-Huerta {r.fernandez_huerta} (meta ≥{' '}
          {r.target.min_index}) · {r.words_per_sentence} palabras por oración (meta {r.target.words_per_sentence[0]}–
          {r.target.words_per_sentence[1]}) · {r.on_target ? 'en el nivel' : 'fuera del nivel'}
          {r.rewrites > 0 ? ` tras ${r.rewrites} ${r.rewrites === 1 ? 'reescritura' : 'reescrituras'}` : ''}
        </footer>
      )}
    </main>
  )
}
