<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const activeNav = ref('今日简报')
const search = ref('')
const showToast = ref(false)
const toastMsg = ref('')
const now = ref(new Date())

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  weekday: 'short',
})
const timeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const currentDate = computed(() => {
  const parts = Object.fromEntries(
    dateFormatter
      .formatToParts(now.value)
      .filter(({ type }) => ['year', 'month', 'day', 'weekday'].includes(type))
      .map(({ type, value }) => [type, value]),
  )
  return `${parts.year}年${parts.month}月${parts.day}日 · ${parts.weekday}`
})
const currentMarketTime = computed(() => `约 ${timeFormatter.format(now.value)} CST`)

function toast(msg) {
  toastMsg.value = msg
  showToast.value = true
  window.setTimeout(() => (showToast.value = false), 1800)
}
const lang = ref('en') // 'en' | 'zh'，控制简报标题与正文语言

// ------- 登录状态 -------
const authed = ref(!!localStorage.getItem('atlas_auth'))
const loginForm = ref({ username: '', password: '' })
const loginError = ref('')
const loginLoading = ref(false)

async function doLogin() {
  loginError.value = ''
  loginLoading.value = true
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginForm.value),
    })
    if (res.ok) {
      const data = await res.json()
      localStorage.setItem('atlas_auth', data.token)
      authed.value = true
      loginForm.value = { username: '', password: '' }
      loadBrief()
      loadMarkets()
      loadAssistantHistory()
    } else if (res.status === 401) {
      loginError.value = '用户名或密码错误'
    } else {
      loginError.value = `登录失败（服务器返回 ${res.status}），请确认后端已启动`
    }
  } catch (err) {
    loginError.value = '无法连接服务器，请确认后端已启动'
  } finally {
    loginLoading.value = false
  }
}

function logout() {
  localStorage.removeItem('atlas_auth')
  authed.value = false
}

const navItems = [
  { label: '今日简报', en: 'Daily Brief', icon: 'target' },
]

// 内置回退数据：后端不可用时仍能展示（中英双语）
const fallbackBrief = {
  eyebrow: 'DAILY EXECUTIVE INTELLIGENCE · 2026.09.07',
  headline_en: 'Energy shock meets industrial acceleration.',
  headline_zh: '能源冲击与产业加速并行',
  subtitle_en: "Today's brief: energy shock and industrial policy heat up together",
  subtitle_zh: '今日情报：能源冲击与产业政策同时升温',
  feature_index: '01',
  kicker: 'ORIGINAL-LANGUAGE EDITION',
  priority: 'HIGH PRIORITY',
  feature_headline_en:
    'Hormuz risk lifts the inflation tail while Asian AI and Chinese infrastructure investment keep accelerating',
  feature_headline_zh: '霍尔木兹风险推高通胀尾部，亚洲 AI 与中国基建投资持续加速',
  feature_text_en:
    'Fact: US–Iran maritime clashes kept Brent crude near a six-week high. At the same time, China began coordinating 109 major projects under the 15th Five-Year Plan and Beijing introduced a dedicated AI4Chip policy. Assessment: markets face an energy-supply shock alongside expanding technology investment—supportive for oil and gas, maritime security and semiconductor equipment, but difficult for energy importers, airlines and long-duration growth assets.',
  feature_text_zh:
    '事实：美伊海上冲突令布伦特原油维持在六周高位附近。与此同时，中国启动“十五五”规划下 109 个重大项目的统筹，北京出台专项 AI4Chip 政策。研判：市场同时面临能源供给冲击与科技投资扩张——利好油气、海上安全与半导体设备，但对能源进口国、航空公司及长久期成长资产不利。',
  updated: '更新于 20:30 CST · 8 个核心来源',
}

const fallbackMarkets = [
  { name: '布伦特原油', code: 'BRENT', value: '$96.19', status: '高位风险', tone: 'up' },
  { name: '美元指数', code: 'DXY', value: '99.09', status: '-0.07%', tone: 'down' },
  { name: '现货黄金', code: 'XAU', value: '$4,398', status: '-0.7%', tone: 'down' },
  { name: '比特币', code: 'BTC', value: '$80,146', status: '企稳', tone: 'up' },
]

const brief = ref(fallbackBrief)
const markets = ref(fallbackMarkets)
const assistantWelcomeMessage = { role: 'assistant', content: '我已读取今日简报和市场快照。' }
const assistantMessages = ref([assistantWelcomeMessage])
const assistantDraft = ref('')
const assistantLoading = ref(false)
const assistantError = ref('')
const assistantMessagesEl = ref(null)

// 按当前语言取简报的标题与正文
const b = computed(() => {
  const s = brief.value
  const pick = (base) => s[`${base}_${lang.value}`] || s[`${base}_en`] || s[`${base}_zh`] || ''
  return {
    eyebrow: s.eyebrow,
    updated: s.updated,
    feature_index: s.feature_index,
    kicker: s.kicker,
    priority: s.priority,
    headline: pick('headline'),
    subtitle: pick('subtitle'),
    feature_headline: pick('feature_headline'),
    feature_text: pick('feature_text'),
  }
})

function setLang(value) {
  lang.value = value
}

const filteredMarkets = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return markets.value
  return markets.value.filter((item) => `${item.name}${item.code}${item.value}`.toLowerCase().includes(query))
})

async function loadBrief() {
  try {
    const res = await fetch('/api/brief/today')
    if (res.ok) brief.value = await res.json()
  } catch (err) {
    console.warn('简报加载失败，使用内置数据', err)
  }
}

async function loadMarkets() {
  try {
    const res = await fetch('/api/markets')
    if (res.ok) markets.value = await res.json()
  } catch (err) {
    console.warn('市场数据加载失败，使用内置数据', err)
  }
}

async function loadAssistantHistory() {
  try {
    const res = await fetch('/api/assistant/history')
    if (!res.ok) return
    const exchanges = await res.json()
    const messages = exchanges.flatMap(({ question, answer }) => [
      { role: 'user', content: question },
      { role: 'assistant', content: answer },
    ])
    assistantMessages.value = messages.length ? messages : [assistantWelcomeMessage]
    scrollAssistantToLatest()
  } catch (err) {
    console.warn('助手历史加载失败', err)
  }
}

// 「下一篇」：调用 DeepSeek 再生成一篇并展示
const nextLoading = ref(false)
async function nextBrief() {
  if (nextLoading.value) return
  nextLoading.value = true
  try {
    const res = await fetch('/api/brief/next', { method: 'POST' })
    if (res.ok) {
      brief.value = await res.json()
      toast('已生成新的一篇')
    } else if (res.status === 404) {
      toast('接口不存在，请重启后端')
    } else {
      toast(`生成失败（${res.status}）`)
    }
  } catch (err) {
    console.warn('生成下一篇失败', err)
    toast('无法连接服务器')
  } finally {
    nextLoading.value = false
  }
}

async function scrollAssistantToLatest() {
  await new Promise((resolve) => requestAnimationFrame(resolve))
  assistantMessagesEl.value?.scrollTo({ top: assistantMessagesEl.value.scrollHeight, behavior: 'smooth' })
}

async function sendAssistantMessage() {
  const message = assistantDraft.value.trim()
  if (!message || assistantLoading.value) return

  const history = assistantMessages.value.slice(-8).map(({ role, content }) => ({ role, content }))
  assistantMessages.value.push({ role: 'user', content: message })
  assistantDraft.value = ''
  assistantError.value = ''
  assistantLoading.value = true
  scrollAssistantToLatest()

  try {
    const res = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || `请求失败（${res.status}）`)
    assistantMessages.value.push({ role: 'assistant', content: data.reply })
    scrollAssistantToLatest()
  } catch (err) {
    assistantError.value = err.message || 'AI 助手暂时无法响应，请稍后重试'
  } finally {
    assistantLoading.value = false
  }
}

let refreshTimer = null
let clockTimer = null

onMounted(() => {
  // 页面时钟每秒更新，确保日期跨天时也能及时切换
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
  if (authed.value) {
    loadBrief()
    loadMarkets()
    loadAssistantHistory()
  }
  // 每 60 秒刷新一次简报与市场快照，与后端定时任务同步
  refreshTimer = window.setInterval(() => {
    if (!authed.value) return
    loadBrief()
    loadMarkets()
  }, 60000)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (clockTimer) window.clearInterval(clockTimer)
})

function selectNav(label) {
  activeNav.value = label
  toast(`已切换至「${label}」`)
}
</script>

<template>
  <!-- 登录页 -->
  <div v-if="!authed" class="login-screen">
    <form class="login-card" @submit.prevent="doLogin">
      <div class="login-brand">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="17" stroke="currentColor" stroke-width="1.5"/><path d="M10 21c2.8-4.8 6.2-7.2 10-7.2 3.8 0 7.2 2.4 10 7.2-2.8 4.8-6.2 7.2-10 7.2-3.8 0-7.2-2.4-10-7.2Z" stroke="currentColor" stroke-width="1.5"/><path d="M20 12v16M14 15.5c2 2 3 3.8 3 5.5s-1 3.5-3 5.5M26 15.5c-2 2-3 3.8-3 5.5s1 3.5 3 5.5" stroke="currentColor" stroke-width="1.25"/></svg>
        </div>
        <div class="brand-title">ATLAS</div>
        <div class="brand-subtitle">INTELLIGENCE OFFICE</div>
      </div>
      <div class="login-field">
        <label>用户名 · Username</label>
        <input v-model="loginForm.username" type="text" autocomplete="username" placeholder="admin" />
      </div>
      <div class="login-field">
        <label>密码 · Password</label>
        <input v-model="loginForm.password" type="password" autocomplete="current-password" placeholder="••••" />
      </div>
      <div v-if="loginError" class="login-error">{{ loginError }}</div>
      <button class="login-submit" type="submit" :disabled="loginLoading">{{ loginLoading ? '登录中…' : '登录 · Sign in' }}</button>
      <div class="login-hint">演示账号 admin / 123</div>
    </form>
  </div>

  <!-- 主界面 -->
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="17" stroke="currentColor" stroke-width="1.5"/><path d="M10 21c2.8-4.8 6.2-7.2 10-7.2 3.8 0 7.2 2.4 10 7.2-2.8 4.8-6.2 7.2-10 7.2-3.8 0-7.2-2.4-10-7.2Z" stroke="currentColor" stroke-width="1.5"/><path d="M20 12v16M14 15.5c2 2 3 3.8 3 5.5s-1 3.5-3 5.5M26 15.5c-2 2-3 3.8-3 5.5s1 3.5 3 5.5" stroke="currentColor" stroke-width="1.25"/></svg>
        </div>
        <div><div class="brand-title">ATLAS</div><div class="brand-subtitle">INTELLIGENCE OFFICE</div></div>
      </div>

      <div class="eyebrow sidebar-label">INTELLIGENCE DESK</div>
      <nav class="nav-list">
        <button v-for="item in navItems" :key="item.label" class="nav-item" :class="{ active: activeNav === item.label }" @click="selectNav(item.label)">
          <span class="nav-icon" aria-hidden="true">
            <svg v-if="item.icon === 'target'" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><circle cx="11" cy="11" r="2"/><path d="m16 16 4 4M11 4v2M4 11h2"/></svg>
            <svg v-else-if="item.icon === 'globe'" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M3.8 9h16.4M3.8 15h16.4M12 3.5c2.2 2.3 3.3 5.1 3.3 8.5s-1.1 6.2-3.3 8.5c-2.2-2.3-3.3-5.1-3.3-8.5S9.8 5.8 12 3.5Z"/></svg>
            <svg v-else-if="item.icon === 'building'" viewBox="0 0 24 24"><path d="M4 20h16M6 20V8h12v12M4 8h16M8 5h8M10 11v2M14 11v2M10 16v2M14 16v2"/></svg>
            <svg v-else-if="item.icon === 'compass'" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="m15 9-2 5-5 2 2-5 5-2Z"/></svg>
            <svg v-else-if="item.icon === 'spark'" viewBox="0 0 24 24"><path d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3ZM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/></svg>
            <svg v-else-if="item.icon === 'shield'" viewBox="0 0 24 24"><path d="M12 3 19 6v5.2c0 4.6-2.8 7.9-7 9.8-4.2-1.9-7-5.2-7-9.8V6l7-3Z"/><path d="M12 8v4M12 15h.01"/></svg>
            <svg v-else viewBox="0 0 24 24"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/></svg>
          </span>
          <span class="nav-copy"><strong>{{ item.label }}</strong><small>{{ item.en }}</small></span><span class="nav-arrow">›</span>
        </button>
      </nav>

      <section class="assistant-panel" aria-label="ATLAS AI 助手">
        <div class="assistant-heading"><span class="assistant-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/><circle cx="12" cy="12" r="4"/></svg></span><div><strong>AI ASSISTANT</strong></div><span class="assistant-online" title="在线"></span></div>
        <div ref="assistantMessagesEl" class="assistant-messages" aria-live="polite"><div v-for="(item, index) in assistantMessages" :key="index" class="assistant-message" :class="item.role"><span>{{ item.content }}</span></div><div v-if="assistantLoading" class="assistant-typing"><i></i><i></i><i></i></div></div>
        <div v-if="assistantError" class="assistant-error">{{ assistantError }}</div>
        <form class="assistant-composer" @submit.prevent="sendAssistantMessage"><textarea v-model="assistantDraft" rows="2" maxlength="2000" placeholder="询问今日情报..." :disabled="assistantLoading" @keydown.enter.exact.prevent="sendAssistantMessage"></textarea><button type="submit" :disabled="!assistantDraft.trim() || assistantLoading" aria-label="发送" title="发送"><svg viewBox="0 0 24 24"><path d="m5 12 14-7-4 14-3.1-5.9L5 12Z"/><path d="m11.9 13.1 3.6-3.6"/></svg></button></form>
      </section>
      <div class="verified-card">
        <div class="verified-line"><span class="status-dot"></span><strong>今日报告已核验</strong></div>
        <div class="next-label">下一次生成</div><div class="next-time">明日 10:00 CST</div>
        <div class="card-rule"></div><div class="card-foot">双语版本 · 8 个核心来源</div>
      </div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div class="search-box"><svg viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/></svg><input v-model="search" placeholder="搜索主题、国家、行业或公司..."/><kbd>⌘ K</kbd></div>
        <div class="top-actions"><div class="lang-switch" role="group" aria-label="语言切换"><button :class="{ active: lang === 'zh' }" @click="setLang('zh')">中</button><button :class="{ active: lang === 'en' }" @click="setLang('en')">EN</button></div><span class="top-divider"></span><button class="icon-button" aria-label="通知"><svg viewBox="0 0 24 24"><path d="M6 17h12l-1.2-1.8V10a4.8 4.8 0 0 0-9.6 0v5.2L6 17ZM10 20h4"/></svg></button><span class="top-divider"></span><div class="date"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.3"/><path d="M12 7v5l3 2"/></svg><span>{{ currentDate }}</span></div><div class="avatar">SW</div><button class="logout-btn" @click="logout" aria-label="退出登录" title="退出登录"><svg viewBox="0 0 24 24"><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l-5-5 5-5M5 12h11"/></svg></button></div>
      </header>

      <div class="page-wrap">
        <section class="hero">
          <div>
            <button class="next-brief" :disabled="nextLoading" @click="nextBrief">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h14M13 6l6 6-6 6"/></svg>
              <span>{{ nextLoading ? '生成中…' : '下一篇' }}</span>
            </button>
            <div class="eyebrow">{{ b.eyebrow }}</div><h1>{{ b.headline }}</h1><p>{{ b.subtitle }}</p>
          </div>
          <div class="hero-meta"><div class="verified-pill"><span class="status-dot"></span>已核验 · VERIFIED</div><div class="updated">{{ b.updated }}</div></div>
        </section>

        <section class="dashboard-grid">
          <article class="feature-card">
            <div class="feature-top"><span class="feature-index">{{ b.feature_index }}</span><span class="feature-kicker">{{ b.kicker }}</span><span class="priority">{{ b.priority }}</span></div>
            <h2>{{ b.feature_headline }}</h2>
            <p class="feature-text">{{ b.feature_text }}</p>
            <div class="feature-bottom"><span>READ THE FULL BRIEF</span><span class="read-arrow">↗</span></div>
          </article>

          <aside class="market-card"><div class="market-heading"><div class="market-title"><span class="pulse-icon">⌁</span>市场快照</div><span class="market-time">{{ currentMarketTime }}</span></div><div class="market-rule"></div><div v-if="filteredMarkets.length" class="market-list"><div v-for="item in filteredMarkets" :key="item.code" class="market-row"><div><strong>{{ item.name }}</strong><small>{{ item.code }}</small></div><span class="market-value">{{ item.value }}</span><span class="market-status" :class="item.tone"><span>{{ item.tone === 'up' ? '↗' : '↘' }}</span>{{ item.status }}</span></div></div><div v-else class="empty-market">未找到匹配的市场项目</div><div class="market-note">Reuters 报道口径；价格会继续变动，不构成投资建议</div></aside>
        </section>
      </div>
    </main>
    <transition name="toast"><div v-if="showToast" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>
