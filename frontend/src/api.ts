import type {
  GenerateRequest, GenerateResponse, Account, AccountPreview, UploadRequest, UploadResponse,
  Goal, ScheduledPost, PlanResult,
} from './types'

const BASE = '/api'

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data as { detail?: string }).detail || `请求失败 ${res.status}`)
  return data as T
}

const post = <T>(url: string, body: unknown) =>
  req<T>(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const generateContent = (r: GenerateRequest) => post<GenerateResponse>('/generate', r)
export const uploadNote = (r: UploadRequest) => post<UploadResponse>('/upload', r)

export const getAccounts = () => req<Account[]>('/accounts')
export const previewAccount = (cookie: string) => post<AccountPreview>('/accounts/preview', { cookie })
export const createAccount = (name: string, cookie: string) => post<Account>('/accounts', { name, cookie })
export const deleteAccount = (id: string) => fetch(`${BASE}/accounts/${id}`, { method: 'DELETE' })

export const getGoals = (account_id?: string) =>
  req<Goal[]>(`/goals${account_id ? `?account_id=${account_id}` : ''}`)
export const createGoal = (body: Omit<Goal, 'id' | 'active' | 'created_at'>) => post<Goal>('/goals', body)
export const deleteGoal = (id: number) => fetch(`${BASE}/goals/${id}`, { method: 'DELETE' })
export const toggleGoal = (id: number, active: boolean) =>
  req(`/goals/${id}/toggle?active=${active}`, { method: 'PATCH' })
export const updateGoal = (id: number, body: Omit<Goal, 'id' | 'active' | 'created_at'>) =>
  req(`/goals/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const planGoal = (goal_id: number) =>
  req<PlanResult>(`/goals/${goal_id}/plan`, { method: 'POST' })

export const getGoalPosts = (goal_id: number) => req<ScheduledPost[]>(`/goals/${goal_id}/posts`)
export const getAllPosts = () => req<ScheduledPost[]>('/posts')
export const runPostNow = (id: number) => req(`/posts/${id}/run`, { method: 'POST' })

export const updateAccountCookie = (id: string, cookie: string) =>
  req(`/accounts/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cookie }) })

export const startBrowser = (account_id: string) => post('/browser/start', { account_id })
export const stopBrowser = () => req('/browser/stop', { method: 'POST' })
export const getBrowserStatus = () => req<{ status: string; request_count: number }>('/browser/status')
export const getBrowserRequests = () => req<Array<Record<string, unknown>>>('/browser/requests')
