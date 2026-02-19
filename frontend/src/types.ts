export interface GenerateRequest {
  topic: string
  style: string
  aspect_ratio: string
  image_count: number
}

export interface XHSContent {
  title: string
  body: string
  hashtags: string[]
  image_prompts: string[]
}

export interface GeneratedImage {
  url?: string
  b64_json?: string
}

export interface GenerateResponse {
  content: XHSContent
  images: GeneratedImage[]
}

export interface Account {
  id: string
  name: string
  cookie_preview: string
  created_at: string
}

export interface UploadRequest {
  account_id?: string
  cookie?: string
  title: string
  desc: string
  image_urls: string[]
  hashtags: string[]
}

export interface UploadResponse {
  success: boolean
  note_id?: string
  detail?: string
}

export interface Goal {
  id: number
  title: string
  description: string
  style: string
  post_freq: number
  active: number
  created_at: string
}

export interface ScheduledPost {
  id: number
  goal_id: number
  account_id: string
  topic: string
  style: string
  aspect_ratio: string
  image_count: number
  scheduled_at: string
  status: 'pending' | 'running' | 'done' | 'failed'
  result_title?: string
  note_id?: string
  error?: string
  created_at: string
}

export interface PlanResult {
  analysis: string
  posts: ScheduledPost[]
}
