'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { createStory, listStories, STATUS, type Ages, type StoryView } from '@/lib/api'

const AGES: { value: Ages; label: string; hint: string }[] = [
  { value: '5-6', label: '5 a 6 años', hint: 'oraciones de 3 a 8 palabras' },
  { value: '7-8', label: '7 a 8 años', hint: 'oraciones de 5 a 11 palabras' },
  { value: '9-10', label: '9 a 10 años', hint: 'oraciones de 7 a 15 palabras' },
]

export default function Home() {
  const [name, setName] = useState('')
  const [ages, setAges] = useState<Ages>('7-8')
  const [likes, setLikes] = useState('')
  const [lesson, setLesson] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [shelf, setShelf] = useState<StoryView[]>([])

  const refresh = useCallback(() => listStories().then(setShelf).catch(() => {}), [])
  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [refresh])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await createStory({ name: name.trim(), ages, likes: likes.trim(), lesson: lesson.trim() })
      setLikes('')
      setLesson('')
      refresh()
    } catch (err) {
      setError(String((err as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="home">
      <header className="brand">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="logo" src="/icon.svg" alt="" width={52} height={52} />
        <div>
          <h1>Cuentos a mi medida</h1>
          <p>Un cuento ilustrado y narrado para tu hijo o hija, escrito al nivel de lectura de su edad.</p>
        </div>
      </header>

      <div className="columns">
        <form className="card create" onSubmit={submit}>
          <h2>Crear un cuento</h2>
          <label>
            Nombre del protagonista
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Salomé" maxLength={30} required />
          </label>
          <fieldset>
            <legend>Edad del lector</legend>
            <div className="chips">
              {AGES.map((a) => (
                <button type="button" key={a.value} className={ages === a.value ? 'chip on' : 'chip'}
                  onClick={() => setAges(a.value)}>
                  {a.label}
                  <small>{a.hint}</small>
                </button>
              ))}
            </div>
          </fieldset>
          <label>
            ¿Qué le gusta?
            <input value={likes} onChange={(e) => setLikes(e.target.value)} placeholder="los colibríes y bailar cumbia"
              maxLength={200} required />
          </label>
          <label>
            Una enseñanza (opcional)
            <input value={lesson} onChange={(e) => setLesson(e.target.value)} placeholder="pedir ayuda cuando algo es difícil"
              maxLength={120} />
          </label>
          {error && <p className="error">No pudimos hacer ese cuento: {error}</p>}
          <button className="primary" disabled={busy || !name.trim() || !likes.trim()}>
            {busy ? 'Revisando el pedido…' : 'Hacer el cuento'}
          </button>
          <p className="privacy">
            Nunca pedimos fotos. El cuento se hace con lo que escribes, en este computador, y no sale de aquí.
          </p>
        </form>

        <section className="shelf">
          <h2>La biblioteca</h2>
          {shelf.length === 0 && <p className="muted">Todavía no hay cuentos.</p>}
          <ul>
            {shelf.map((s) => (
              <li key={s.story_id}>
                <Link href={`/cuento/${s.story_id}`} className="book">
                  <span className={`spine ${s.status}`} />
                  <span className="title">{s.title ?? `Un cuento para ${s.request.name}`}</span>
                  <span className="meta">
                    {s.request.name} · {s.request.ages} años · {STATUS[s.status]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}
