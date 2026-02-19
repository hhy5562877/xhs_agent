import { useState, useRef } from 'react'
import {
  Layout, Typography, Button, Select, Form, Input, Card, Tag, Image,
  Modal, Tabs, List, Avatar, Space, Divider, Checkbox,
  message, Spin, Empty, Popconfirm, Row, Col, Alert, Badge, Table,
  InputNumber,
} from 'antd'
import {
  StarOutlined, RocketOutlined, UserOutlined, PlusOutlined,
  DeleteOutlined, CheckCircleFilled, LoadingOutlined,
  PictureOutlined, FileTextOutlined, TeamOutlined,
  BarChartOutlined, CalendarOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import type { GenerateResponse, Account, Goal, ScheduledPost } from './types'
import {
  generateContent, uploadNote, getAccounts, createAccount, deleteAccount,
  getGoals, createGoal, deleteGoal, planGoal, getGoalPosts,
} from './api'

const { Header, Content } = Layout
const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

const STYLES = ['生活方式', '美食探店', '旅行攻略', '穿搭分享', '护肤美妆', '健身运动', '读书学习']
const RATIOS = [
  { label: '3:4（推荐）', value: '3:4' },
  { label: '1:1', value: '1:1' },
  { label: '4:5', value: '4:5' },
  { label: '9:16', value: '9:16' },
]

const STATUS_MAP: Record<string, { color: string; text: string }> = {
  pending: { color: 'blue', text: '待发布' },
  running: { color: 'orange', text: '发布中' },
  done:    { color: 'green', text: '已发布' },
  failed:  { color: 'red',   text: '失败' },
}

export default function App() {
  const [form] = Form.useForm()
  const [goalForm] = Form.useForm()
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  const [activeTab, setActiveTab] = useState('generate')

  // publish modal
  const [publishOpen, setPublishOpen] = useState(false)
  const [publishTab, setPublishTab] = useState('saved')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tempCookie, setTempCookie] = useState('')
  const [saveCookie, setSaveCookie] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [publishing, setPublishing] = useState(false)

  // account manager modal
  const [accountOpen, setAccountOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCookie, setNewCookie] = useState('')
  const [addingAccount, setAddingAccount] = useState(false)

  // operation goals
  const [goals, setGoals] = useState<Goal[]>([])
  const [goalOpen, setGoalOpen] = useState(false)
  const [addingGoal, setAddingGoal] = useState(false)
  const [planningGoalId, setPlanningGoalId] = useState<number | null>(null)
  const [planAccountId, setPlanAccountId] = useState<string>('')
  const [planOpen, setPlanOpen] = useState(false)
  const [planGoalTarget, setPlanGoalTarget] = useState<Goal | null>(null)
  const [posts, setPosts] = useState<ScheduledPost[]>([])
  const [_postsGoalId, setPostsGoalId] = useState<number | null>(null)
  const [postsOpen, setPostsOpen] = useState(false)
  const [planAnalysis, setPlanAnalysis] = useState('')

  const [msgApi, contextHolder] = message.useMessage()

  // ── 生成 ──────────────────────────────────────────────
  async function onGenerate(values: Record<string, unknown>) {
    setGenerating(true); setResult(null)
    try {
      const res = await generateContent({
        topic: values.topic as string, style: values.style as string,
        aspect_ratio: values.aspect_ratio as string, image_count: values.image_count as number,
      })
      setResult(res)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (e: unknown) { msgApi.error((e as Error).message) }
    finally { setGenerating(false) }
  }

  // ── 发布 Modal ────────────────────────────────────────
  async function openPublish() {
    setSelectedId(null); setTempCookie(''); setSaveCookie(false); setSaveName(''); setPublishTab('saved')
    setAccounts(await getAccounts())
    setPublishOpen(true)
  }

  async function onPublish() {
    if (!result) return
    setPublishing(true)
    try {
      let payload: Record<string, unknown> = {}
      if (publishTab === 'saved') {
        if (!selectedId) { msgApi.warning('请选择一个账号'); return }
        payload.account_id = selectedId
      } else {
        if (!tempCookie.trim()) { msgApi.warning('请填写 Cookie'); return }
        payload.cookie = tempCookie.trim()
        if (saveCookie && saveName.trim()) await createAccount(saveName.trim(), tempCookie.trim())
      }
      const imageUrls = result.images.map(img => img.url || '').filter(Boolean)
      const desc = result.content.body + '\n\n' + result.content.hashtags.map(t => '#' + t).join(' ')
      const res = await uploadNote({
        ...payload as { account_id?: string; cookie?: string },
        title: result.content.title, desc, image_urls: imageUrls, hashtags: result.content.hashtags,
      })
      setPublishOpen(false)
      msgApi.success(`发布成功！笔记 ID: ${res.note_id || '已提交'}`)
    } catch (e: unknown) { msgApi.error((e as Error).message) }
    finally { setPublishing(false) }
  }

  // ── 账号管理 ──────────────────────────────────────────
  async function openAccountManager() {
    setAccounts(await getAccounts()); setNewName(''); setNewCookie(''); setAccountOpen(true)
  }

  async function onAddAccount() {
    if (!newName.trim()) { msgApi.warning('请填写账号名称'); return }
    if (!newCookie.trim()) { msgApi.warning('请填写 Cookie'); return }
    setAddingAccount(true)
    try {
      await createAccount(newName.trim(), newCookie.trim())
      setAccounts(await getAccounts()); setNewName(''); setNewCookie('')
      msgApi.success('账号已保存')
    } catch (e: unknown) { msgApi.error((e as Error).message) }
    finally { setAddingAccount(false) }
  }

  async function onDeleteAccount(id: string) {
    await deleteAccount(id); setAccounts(await getAccounts())
    if (selectedId === id) setSelectedId(null)
    msgApi.success('已删除')
  }

  // ── 运营目标 ──────────────────────────────────────────
  async function loadGoals() { setGoals(await getGoals()) }

  async function openGoalManager() { await loadGoals(); setGoalOpen(true) }

  async function onAddGoal(values: Record<string, unknown>) {
    setAddingGoal(true)
    try {
      await createGoal({
        title: values.title as string, description: values.description as string,
        style: values.style as string, post_freq: values.post_freq as number,
      })
      await loadGoals(); goalForm.resetFields()
      msgApi.success('运营目标已创建')
    } catch (e: unknown) { msgApi.error((e as Error).message) }
    finally { setAddingGoal(false) }
  }

  async function onDeleteGoal(id: number) {
    await deleteGoal(id); await loadGoals(); msgApi.success('已删除')
  }

  async function openPlanModal(goal: Goal) {
    setPlanGoalTarget(goal); setPlanAccountId(''); setPlanAnalysis('')
    setAccounts(await getAccounts()); setPlanOpen(true)
  }

  async function onPlan() {
    if (!planGoalTarget) return
    if (!planAccountId) { msgApi.warning('请选择发布账号'); return }
    setPlanningGoalId(planGoalTarget.id)
    try {
      const res = await planGoal(planGoalTarget.id, planAccountId)
      setPlanAnalysis(res.analysis)
      msgApi.success(`AI 已生成 ${res.posts.length} 条发布计划`)
      setPlanOpen(false)
      // 展示排期
      setPostsGoalId(planGoalTarget.id)
      setPosts(await getGoalPosts(planGoalTarget.id))
      setPostsOpen(true)
    } catch (e: unknown) { msgApi.error((e as Error).message) }
    finally { setPlanningGoalId(null) }
  }

  async function openPosts(goal: Goal) {
    setPostsGoalId(goal.id)
    setPosts(await getGoalPosts(goal.id))
    setPostsOpen(true)
  }

  const imgSrc = (img: { url?: string; b64_json?: string }) =>
    img.url || (img.b64_json ? `data:image/png;base64,${img.b64_json}` : '')

  const primaryBtnStyle = {
    background: 'linear-gradient(135deg, #ff2442, #ff6b6b)',
    border: 'none', boxShadow: '0 4px 16px rgba(255,36,66,.35)',
  }

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      {contextHolder}

      <Header style={{
        background: 'linear-gradient(135deg, #ff2442 0%, #ff6b6b 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 32px', boxShadow: '0 2px 16px rgba(255,36,66,.3)',
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        <Space>
          <span style={{ fontSize: 22 }}>🌸</span>
          <Title level={4} style={{ color: '#fff', margin: 0, letterSpacing: 1 }}>小红书 Agent</Title>
        </Space>
        <Space>
          <Button icon={<BarChartOutlined />} onClick={() => { setActiveTab('operation'); openGoalManager() }}
            style={{ background: 'rgba(255,255,255,.15)', border: 'none', color: '#fff' }} ghost>
            运营管理
          </Button>
          <Button icon={<TeamOutlined />} onClick={openAccountManager}
            style={{ background: 'rgba(255,255,255,.15)', border: 'none', color: '#fff' }} ghost>
            账号管理
          </Button>
        </Space>
      </Header>

      <Content style={{ maxWidth: 960, margin: '32px auto', padding: '0 16px', width: '100%' }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} size="large"
          items={[
            { key: 'generate', label: <Space><FileTextOutlined />内容生成</Space>, children: null },
            { key: 'operation', label: <Space><BarChartOutlined />运营管理</Space>, children: null },
          ]}
          style={{ marginBottom: 24 }}
        />

        {/* ── 内容生成 Tab ── */}
        {activeTab === 'generate' && (
          <>
            <Card className="fade-in-up" style={{ borderRadius: 16, boxShadow: '0 4px 24px rgba(0,0,0,.06)', border: 'none' }}
              styles={{ body: { padding: 28 } }}>
              <Space style={{ marginBottom: 20 }}>
                <FileTextOutlined style={{ color: '#ff2442', fontSize: 18 }} />
                <Title level={5} style={{ margin: 0 }}>内容生成</Title>
              </Space>
              <Form form={form} onFinish={onGenerate} layout="vertical"
                initialValues={{ style: '生活方式', aspect_ratio: '3:4', image_count: 1 }}>
                <Form.Item name="topic" label="内容主题" rules={[{ required: true, message: '请输入主题' }]}>
                  <Input placeholder="例如：秋日咖啡馆探店、极简穿搭分享" size="large" />
                </Form.Item>
                <Row gutter={16}>
                  <Col span={8}><Form.Item name="style" label="内容风格">
                    <Select size="large" options={STYLES.map(s => ({ label: s, value: s }))} />
                  </Form.Item></Col>
                  <Col span={8}><Form.Item name="aspect_ratio" label="图片比例">
                    <Select size="large" options={RATIOS} />
                  </Form.Item></Col>
                  <Col span={8}><Form.Item name="image_count" label="图片数量">
                    <Select size="large" options={[1,2,3,4].map(n => ({ label: `${n} 张`, value: n }))} />
                  </Form.Item></Col>
                </Row>
                <Form.Item style={{ marginBottom: 0 }}>
                  <Button type="primary" htmlType="submit" size="large" block loading={generating}
                    icon={<StarOutlined />} style={{ ...primaryBtnStyle, height: 48, fontSize: 16, fontWeight: 600 }}>
                    {generating ? '生成中...' : '✨ 生成内容'}
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            {generating && (
              <Card className="fade-in" style={{ borderRadius: 16, border: 'none', textAlign: 'center', padding: '40px 0' }}>
                <Spin indicator={<LoadingOutlined style={{ fontSize: 36, color: '#ff2442' }} spin />} />
                <div style={{ marginTop: 16, color: '#ff2442', fontWeight: 500 }}>AI 正在创作中，请稍候...</div>
              </Card>
            )}

            {result && !generating && (
              <div ref={resultRef} className="fade-in-up" style={{ animationDelay: '.1s' }}>
                <Card style={{ borderRadius: 16, boxShadow: '0 4px 24px rgba(0,0,0,.06)', border: 'none' }}
                  styles={{ body: { padding: 28 } }}>
                  <Space style={{ marginBottom: 20 }}>
                    <PictureOutlined style={{ color: '#ff2442', fontSize: 18 }} />
                    <Title level={5} style={{ margin: 0 }}>生成结果</Title>
                  </Space>
                  <Title level={3} className="gradient-title" style={{ marginBottom: 12 }}>{result.content.title}</Title>
                  <Paragraph style={{ fontSize: 15, lineHeight: 1.9, color: '#444', whiteSpace: 'pre-wrap' }}>
                    {result.content.body}
                  </Paragraph>
                  <Space wrap style={{ marginTop: 12, marginBottom: 20 }}>
                    {result.content.hashtags.map(tag => (
                      <Tag key={tag} className="tag-item"
                        style={{ background: '#fff0f3', color: '#ff2442', border: '1px solid #ffb3c1', borderRadius: 20, padding: '4px 14px', fontSize: 13 }}>
                        #{tag}
                      </Tag>
                    ))}
                  </Space>
                  <Image.PreviewGroup>
                    <Row gutter={[12, 12]}>
                      {result.images.map((img, i) => {
                        const src = imgSrc(img)
                        return src ? (
                          <Col key={i} xs={12} sm={8} md={6}>
                            <div className="image-card">
                              <Image src={src} alt={`图片${i+1}`}
                                style={{ width: '100%', aspectRatio: '3/4', objectFit: 'cover', borderRadius: 12 }} />
                            </div>
                          </Col>
                        ) : null
                      })}
                    </Row>
                  </Image.PreviewGroup>
                  <Divider style={{ margin: '24px 0' }} />
                  <div style={{ textAlign: 'center' }}>
                    <Button size="large" onClick={openPublish} className="publish-float" icon={<RocketOutlined />}
                      style={{ ...primaryBtnStyle, color: '#fff', height: 48, padding: '0 40px', fontSize: 16, fontWeight: 600, borderRadius: 24 }}>
                      发布到小红书
                    </Button>
                  </div>
                </Card>
              </div>
            )}
          </>
        )}

        {/* ── 运营管理 Tab ── */}
        {activeTab === 'operation' && (
          <div className="fade-in-up">
            <Card style={{ borderRadius: 16, boxShadow: '0 4px 24px rgba(0,0,0,.06)', border: 'none', marginBottom: 24 }}
              styles={{ body: { padding: 28 } }}
              title={<Space><BarChartOutlined style={{ color: '#ff2442' }} /><span>运营目标</span></Space>}
              extra={<Button type="primary" icon={<PlusOutlined />} onClick={openGoalManager} style={primaryBtnStyle}>新建目标</Button>}
            >
              {goals.length === 0
                ? <Empty description="暂无运营目标，点击右上角新建" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                : (
                  <List dataSource={goals} renderItem={goal => (
                    <List.Item
                      style={{ borderRadius: 12, padding: '14px 16px', marginBottom: 10, border: '1px solid #f0f0f0', background: '#fafafa' }}
                      actions={[
                        <Button key="posts" size="small" icon={<CalendarOutlined />} onClick={() => openPosts(goal)}>排期</Button>,
                        <Button key="plan" size="small" type="primary" icon={<ThunderboltOutlined />}
                          loading={planningGoalId === goal.id} onClick={() => openPlanModal(goal)}
                          style={primaryBtnStyle}>AI 规划</Button>,
                        <Popconfirm key="del" title="确认删除？" onConfirm={() => onDeleteGoal(goal.id)} okText="删除" okButtonProps={{ danger: true }}>
                          <Button danger size="small" icon={<DeleteOutlined />} />
                        </Popconfirm>,
                      ]}
                    >
                      <List.Item.Meta
                        avatar={<Avatar style={{ background: '#ff2442' }}>{goal.title[0]}</Avatar>}
                        title={<Space><Text strong>{goal.title}</Text><Tag color="pink">{goal.style}</Tag><Tag>{goal.post_freq}篇/天</Tag></Space>}
                        description={<Text type="secondary" style={{ fontSize: 13 }}>{goal.description}</Text>}
                      />
                    </List.Item>
                  )} />
                )
              }
            </Card>
          </div>
        )}
      </Content>

      {/* 发布 Modal */}
      <Modal title={<Space><RocketOutlined style={{ color: '#ff2442' }} /><span>发布到小红书</span></Space>}
        open={publishOpen} onCancel={() => setPublishOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setPublishOpen(false)}>取消</Button>,
          <Button key="confirm" type="primary" loading={publishing} onClick={onPublish} style={primaryBtnStyle}>确认发布</Button>,
        ]} width={520}>
        <Tabs activeKey={publishTab} onChange={setPublishTab} items={[
          {
            key: 'saved', label: '已保存账号',
            children: accounts.length === 0
              ? <Empty description="暂无账号" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              : <List dataSource={accounts} renderItem={acc => (
                  <List.Item className={`account-card ${selectedId === acc.id ? 'selected' : ''}`}
                    onClick={() => setSelectedId(acc.id)}
                    style={{ borderRadius: 10, padding: '10px 14px', marginBottom: 8, border: '1.5px solid #f0f0f0' }}
                    actions={[selectedId === acc.id ? <CheckCircleFilled style={{ color: '#ff2442', fontSize: 18 }} /> : null]}>
                    <List.Item.Meta
                      avatar={<Avatar icon={<UserOutlined />} style={{ background: '#ff2442' }} />}
                      title={<Text strong>{acc.name}</Text>}
                      description={<Text type="secondary" style={{ fontSize: 12 }}>{acc.created_at} · {acc.cookie_preview}</Text>}
                    />
                  </List.Item>
                )} />,
          },
          {
            key: 'temp', label: '临时 Cookie',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <TextArea rows={4} value={tempCookie} onChange={e => setTempCookie(e.target.value)} placeholder="粘贴你的小红书 Cookie..." />
                <Alert type="info" showIcon message="获取方式"
                  description="打开 xiaohongshu.com → F12 → Network → 任意请求 → Request Headers → 复制 cookie 字段值" style={{ fontSize: 12 }} />
                <Checkbox checked={saveCookie} onChange={e => setSaveCookie(e.target.checked)}>保存此 Cookie 为账号</Checkbox>
                {saveCookie && <Input value={saveName} onChange={e => setSaveName(e.target.value)} placeholder="账号备注名称" />}
              </Space>
            ),
          },
        ]} />
      </Modal>

      {/* 账号管理 Modal */}
      <Modal title={<Space><TeamOutlined style={{ color: '#ff2442' }} /><span>账号管理</span></Space>}
        open={accountOpen} onCancel={() => setAccountOpen(false)} footer={null} width={520}>
        {accounts.length === 0
          ? <Empty description="暂无账号" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginBottom: 16 }} />
          : <List dataSource={accounts} renderItem={acc => (
              <List.Item style={{ borderRadius: 10, padding: '10px 14px', marginBottom: 8, border: '1px solid #f0f0f0', background: '#fafafa' }}
                actions={[
                  <Popconfirm key="del" title="确认删除？" onConfirm={() => onDeleteAccount(acc.id)} okText="删除" okButtonProps={{ danger: true }}>
                    <Button danger size="small" icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>,
                ]}>
                <List.Item.Meta
                  avatar={<Avatar icon={<UserOutlined />} style={{ background: '#ff2442' }} />}
                  title={<Text strong>{acc.name}</Text>}
                  description={<Text type="secondary" style={{ fontSize: 12 }}>{acc.created_at} · {acc.cookie_preview}</Text>}
                />
              </List.Item>
            )} />
        }
        <Divider>添加账号</Divider>
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="账号名称" prefix={<UserOutlined style={{ color: '#ccc' }} />} />
          <TextArea rows={3} value={newCookie} onChange={e => setNewCookie(e.target.value)} placeholder="粘贴小红书 Cookie..." />
          <Button type="primary" block icon={<PlusOutlined />} loading={addingAccount} onClick={onAddAccount} style={primaryBtnStyle}>保存账号</Button>
        </Space>
      </Modal>

      {/* 新建运营目标 Modal */}
      <Modal title={<Space><BarChartOutlined style={{ color: '#ff2442' }} /><span>新建运营目标</span></Space>}
        open={goalOpen} onCancel={() => setGoalOpen(false)} footer={null} width={540}>
        <Form form={goalForm} onFinish={onAddGoal} layout="vertical"
          initialValues={{ style: '生活方式', post_freq: 1 }}>
          <Form.Item name="title" label="目标名称" rules={[{ required: true }]}>
            <Input placeholder="例如：咖啡品牌推广、个人IP打造" />
          </Form.Item>
          <Form.Item name="description" label="运营目标描述" rules={[{ required: true }]}>
            <TextArea rows={3} placeholder="详细描述你的运营目标、目标受众、核心卖点等，AI 将据此制定内容策略..." />
          </Form.Item>
          <Row gutter={16}>
            <Col span={14}>
              <Form.Item name="style" label="主要内容风格">
                <Select options={STYLES.map(s => ({ label: s, value: s }))} />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="post_freq" label="每日发布频率">
                <InputNumber min={1} max={3} style={{ width: '100%' }} addonAfter="篇/天" />
              </Form.Item>
            </Col>
          </Row>
          <Button type="primary" htmlType="submit" block loading={addingGoal} style={primaryBtnStyle}>创建目标</Button>
        </Form>
      </Modal>

      {/* AI 规划 Modal */}
      <Modal title={<Space><ThunderboltOutlined style={{ color: '#ff2442' }} /><span>AI 智能规划</span></Space>}
        open={planOpen} onCancel={() => setPlanOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setPlanOpen(false)}>取消</Button>,
          <Button key="plan" type="primary" loading={planningGoalId !== null} onClick={onPlan} style={primaryBtnStyle}>
            开始规划
          </Button>,
        ]} width={480}>
        {planGoalTarget && (
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Alert type="info" showIcon
              message={`目标：${planGoalTarget.title}`}
              description="AI 将分析运营目标，结合小红书平台规律，自动生成未来7天的内容发布计划并加入定时队列。" />
            <div>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>选择发布账号</Text>
              <Select style={{ width: '100%' }} placeholder="选择用于发布的账号"
                value={planAccountId || undefined} onChange={setPlanAccountId}
                options={accounts.map(a => ({ label: a.name, value: a.id }))} />
            </div>
          </Space>
        )}
      </Modal>

      {/* 排期查看 Modal */}
      <Modal title={<Space><CalendarOutlined style={{ color: '#ff2442' }} /><span>发布排期</span></Space>}
        open={postsOpen} onCancel={() => setPostsOpen(false)} footer={null} width={720}>
        {planAnalysis && (
          <Alert type="success" showIcon message="AI 运营策略分析" description={planAnalysis}
            style={{ marginBottom: 16 }} closable onClose={() => setPlanAnalysis('')} />
        )}
        <Table
          dataSource={posts} rowKey="id" size="small" pagination={false}
          columns={[
            { title: '发布时间', dataIndex: 'scheduled_at', width: 140 },
            { title: '主题', dataIndex: 'topic', ellipsis: true },
            { title: '风格', dataIndex: 'style', width: 90 },
            { title: '图片', dataIndex: 'image_count', width: 60, render: (n: number) => `${n}张` },
            {
              title: '状态', dataIndex: 'status', width: 80,
              render: (s: string) => <Badge color={STATUS_MAP[s]?.color} text={STATUS_MAP[s]?.text} />,
            },
            { title: '笔记ID', dataIndex: 'note_id', width: 120, render: (v: string) => v || '-' },
          ]}
        />
      </Modal>
    </Layout>
  )
}
