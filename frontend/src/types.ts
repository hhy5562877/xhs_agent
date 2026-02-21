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
  xhs_user_id: string
  nickname: string
  avatar_url: string
  fans: string
  created_at: string
}

export interface AccountPreview {
  xhs_user_id: string
  nickname: string
  avatar_url: string
  fans: string
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
  account_id: string
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

export interface SystemConfig {
  siliconflow_api_key: string
  siliconflow_base_url: string
  text_model: string
  vision_model: string
  image_api_key: string
  image_api_base_url: string
  image_model: string
  wxpusher_app_token: string
  wxpusher_uids: string
  cos_secret_id: string
  cos_secret_key: string
  cos_region: string
  cos_bucket: string
  cos_path_prefix: string
}

export interface AccountImage {
  id: number
  group_id: number
  account_id: string
  file_path: string
  original_name: string
  category: ImageCategory
  user_prompt: string
  annotation: string
  status: 'pending' | 'done' | 'failed'
  created_at: string
}

export interface ImageGroup {
  id: number
  account_id: string
  category: ImageCategory
  user_prompt: string
  annotation: string
  status: 'pending' | 'done' | 'failed'
  created_at: string
  images: AccountImage[]
}

export type ImageCategory = 'style' | 'person' | 'product' | 'scene' | 'brand'

export const IMAGE_CATEGORY_MAP: Record<ImageCategory, { name: string; desc: string }> = {
  style:   { name: '风格参考', desc: '整体视觉调性参考' },
  person:  { name: '人物形象', desc: '真人/IP/宠物' },
  product: { name: '产品素材', desc: '要推广的产品/物品' },
  scene:   { name: '场景环境', desc: '拍摄场景/背景' },
  brand:   { name: '品牌元素', desc: 'Logo、色卡、视觉规范' },
}

export const IMAGE_CATEGORIES: ImageCategory[] = ['style', 'person', 'product', 'scene', 'brand']
