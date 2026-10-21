export const API = process.env.NEXT_PUBLIC_API ?? 'http://localhost:8002'

export type Ages = '5-6' | '7-8' | '9-10'

export interface Cue {
  text: string
  start: number
  end: number
}

export interface PageView {
  text: string
  image_url: string | null
  audio_url: string
  cues: Cue[]
}

export interface StoryView {
  story_id: string
  status: 'queued' | 'writing' | 'drawing' | 'narrating' | 'done' | 'failed' | 'retrying'
  created: number
  request: { name: string; ages: Ages; likes: string; lesson: string }
  title?: string
  pages?: PageView[]
  readability?: {
    fernandez_huerta: number
    words_per_sentence: number
    on_target: boolean
    target: { min_index: number; words_per_sentence: [number, number] }
    drafts: number
  }
}

export const STATUS: Record<StoryView['status'], string> = {
  queued: 'En la fila',
  writing: 'Escribiendo el cuento',
  drawing: 'Pintando las ilustraciones',
  narrating: 'Grabando la narración',
  done: 'Listo',
  failed: 'No se pudo hacer',
  retrying: 'Intentando de nuevo',
}

export async function createStory(body: { name: string; ages: Ages; likes: string; lesson: string }) {
  const r = await fetch(`${API}/stories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail?.reasons?.join(' ') ?? 'No se pudo crear el cuento')
  return data as { story_id: string }
}

export const listStories = async (): Promise<StoryView[]> => (await fetch(`${API}/stories`)).json()
export const getStory = async (id: string): Promise<StoryView> => (await fetch(`${API}/stories/${id}`)).json()
