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

const weather = ref({
  location: '上海',
  temperature: null,
  temperature_max: null,
  temperature_min: null,
  weather_code: 0,
})
const weatherLoading = ref(true)

const weatherMeta = computed(() => {
  const code = weather.value.weather_code
  if (code === 0) return { label: '晴', icon: 'sun' }
  if ([1, 2].includes(code)) return { label: '晴间多云', icon: 'partly' }
  if (code === 3) return { label: '多云', icon: 'cloud' }
  if ([45, 48].includes(code)) return { label: '雾', icon: 'fog' }
  if ([51, 53, 55, 56, 57].includes(code)) return { label: '小雨', icon: 'rain' }
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return { label: '雨', icon: 'rain' }
  if ([71, 73, 75, 77, 85, 86].includes(code)) return { label: '雪', icon: 'snow' }
  if ([95, 96, 99].includes(code)) return { label: '雷雨', icon: 'storm' }
  return { label: '天气变化', icon: 'cloud' }
})

function getBrowserPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('浏览器不支持定位'))
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: 6000,
      maximumAge: 30 * 60 * 1000,
    })
  })
}

async function loadWeather() {
  weatherLoading.value = true
  const requestWeather = async (coordinates) => {
    const params = new URLSearchParams({
      lat: coordinates.latitude.toFixed(4),
      lon: coordinates.longitude.toFixed(4),
    })
    const res = await fetch(`/api/weather?${params}`)
    if (!res.ok) throw new Error(`天气请求失败（${res.status}）`)
    weather.value = await res.json()
  }

  try {
    // 先展示默认城市，定位结果到达后再更新，避免权限等待期间一直显示占位符。
    await requestWeather({ latitude: 31.2304, longitude: 121.4737 })
  } catch (err) {
    console.warn('天气数据加载失败', err)
  } finally {
    weatherLoading.value = false
  }

  try {
    const position = await getBrowserPosition()
    await requestWeather(position.coords)
  } catch (err) {
    console.info('定位不可用，天气使用上海作为回退位置')
  }
}

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
      loadWeather()
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
  { label: '今日简报', en: 'Daily Brief' },
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
const assistantThinking = ref(false)
const assistantError = ref('')
const assistantMessagesEl = ref(null)
let assistantAbortController = null
let assistantTimeoutTimer = null

function formatAssistantContent(content) {
  const escapeHtml = (value) => value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;')
    .replace(/'/g, '&#039;')
  const inline = (value) => value
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
  const lines = escapeHtml(String(content || '')).split(/\r?\n/)
  const html = []
  let listType = null

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`)
      listType = null
    }
  }

  for (const line of lines) {
    const heading = line.match(/^\s{0,3}#{1,3}\s+(.+)$/)
    const bullet = line.match(/^\s*[-*]\s+(.+)$/)
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (!line.trim()) {
      closeList()
    } else if (heading) {
      closeList()
      html.push(`<h4>${inline(heading[1])}</h4>`)
    } else if (bullet || numbered) {
      const nextType = bullet ? 'ul' : 'ol'
      if (listType !== nextType) {
        closeList()
        listType = nextType
        html.push(`<${listType}>`)
      }
      html.push(`<li>${inline((bullet || numbered)[1])}</li>`)
    } else {
      closeList()
      html.push(`<p>${inline(line)}</p>`)
    }
  }
  closeList()
  return html.join('')
}

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

function cancelAssistantMessage() {
  assistantAbortController?.abort()
}

async function sendAssistantMessage() {
  const message = assistantDraft.value.trim()
  if (!message || assistantLoading.value) return

  assistantMessages.value.push({ role: 'user', content: message })
  assistantDraft.value = ''
  assistantError.value = ''
  assistantLoading.value = true
  assistantThinking.value = true
  scrollAssistantToLatest()
  let stopStreamRenderer = null
  let requestTimedOut = false
  const requestController = new AbortController()
  assistantAbortController = requestController
  assistantTimeoutTimer = window.setTimeout(() => {
    requestTimedOut = true
    requestController.abort()
  }, 330 * 1000)

  try {
    const res = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal: requestController.signal,
    })
    if (!res.ok || !res.body) throw new Error(`请求失败（${res.status}）`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let replyIndex = -1
    let pendingText = ''
    let streamFinished = false
    let renderPromise = null
    stopStreamRenderer = () => { streamFinished = true }

    const renderQueuedText = async () => {
      while (!streamFinished || pendingText) {
        if (!pendingText) {
          await new Promise((resolve) => window.setTimeout(resolve, 16))
          continue
        }
        // 网络增量可能集中到达；按队列长度动态取字，保持可见且不过度拖慢的流式效果。
        const size = Math.min(16, Math.max(2, Math.ceil(pendingText.length / 40)))
        assistantMessages.value[replyIndex].content += pendingText.slice(0, size)
        pendingText = pendingText.slice(size)
        scrollAssistantToLatest()
        await new Promise((resolve) => window.setTimeout(resolve, 20))
      }
    }

    const handleLine = (line) => {
      if (!line.trim()) return
      const event = JSON.parse(line)
      if (event.type === 'delta') {
        if (replyIndex < 0) {
          assistantThinking.value = false
          assistantMessages.value.push({ role: 'assistant', content: '' })
          replyIndex = assistantMessages.value.length - 1
          renderPromise = renderQueuedText()
        }
        pendingText += event.content
      } else if (event.type === 'error') {
        throw new Error(event.message || 'AI 助手暂时无法响应，请稍后重试')
      }
    }

    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) handleLine(line)
      if (done) break
    }
    if (buffer) handleLine(buffer)
    streamFinished = true
    if (renderPromise) await renderPromise
    if (replyIndex < 0 || !assistantMessages.value[replyIndex]?.content) {
      throw new Error('AI 助手未返回内容，请稍后重试')
    }
  } catch (err) {
    if (err?.name === 'AbortError') {
      assistantError.value = requestTimedOut ? 'AI 助手回复超过 330 秒，已自动取消' : '已取消本次生成'
    } else {
      assistantError.value = err.message || 'AI 助手暂时无法响应，请稍后重试'
    }
  } finally {
    // 确保异常中止时，渲染循环不会继续等待新的网络增量。
    stopStreamRenderer?.()
    if (assistantTimeoutTimer) window.clearTimeout(assistantTimeoutTimer)
    if (assistantAbortController === requestController) assistantAbortController = null
    assistantTimeoutTimer = null
    assistantThinking.value = false
    assistantLoading.value = false
  }
}

let refreshTimer = null
let clockTimer = null
let weatherTimer = null

onMounted(() => {
  // 页面时钟每秒更新，确保日期跨天时也能及时切换
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
  if (authed.value) {
    loadBrief()
    loadMarkets()
    loadAssistantHistory()
    loadWeather()
  }
  // 每 60 秒刷新一次简报与市场快照，与后端定时任务同步
  refreshTimer = window.setInterval(() => {
    if (!authed.value) return
    loadBrief()
    loadMarkets()
  }, 60000)
  weatherTimer = window.setInterval(() => {
    if (authed.value) loadWeather()
  }, 30 * 60 * 1000)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (clockTimer) window.clearInterval(clockTimer)
  if (weatherTimer) window.clearInterval(weatherTimer)
  if (assistantTimeoutTimer) window.clearTimeout(assistantTimeoutTimer)
  assistantAbortController?.abort()
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

      <section class="weather-card" aria-label="所在地天气">
        <div class="weather-icon" :class="`weather-${weatherMeta.icon}`" aria-hidden="true">
          <svg v-if="weatherMeta.icon === 'sun'" viewBox="0 0 32 32"><circle cx="16" cy="16" r="5"/><path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.8 6.8l2.8 2.8M22.4 22.4l2.8 2.8M25.2 6.8l-2.8 2.8M9.6 22.4l-2.8 2.8"/></svg>
          <svg v-else-if="weatherMeta.icon === 'partly'" viewBox="0 0 32 32"><circle cx="12" cy="11" r="5"/><path d="M12 3v2M4 11h2M6.3 5.3l1.4 1.4M20 11h2M17.7 5.3l-1.4 1.4"/><path d="M9 24h15a5 5 0 0 0-1-9.9A7 7 0 0 0 9.5 16 4 4 0 0 0 9 24Z"/></svg>
          <svg v-else-if="weatherMeta.icon === 'rain'" viewBox="0 0 32 32"><path d="M7 21h17a5 5 0 0 0-1-9.9A8 8 0 0 0 7.8 13 4 4 0 0 0 7 21Z"/><path d="m11 24-1 3M17 24l-1 3M23 24l-1 3"/></svg>
          <svg v-else-if="weatherMeta.icon === 'snow'" viewBox="0 0 32 32"><path d="M7 19h17a5 5 0 0 0-1-9.9A8 8 0 0 0 7.8 11 4 4 0 0 0 7 19Z"/><path d="M11 24h.01M17 26h.01M23 24h.01"/></svg>
          <svg v-else-if="weatherMeta.icon === 'storm'" viewBox="0 0 32 32"><path d="M7 19h17a5 5 0 0 0-1-9.9A8 8 0 0 0 7.8 11 4 4 0 0 0 7 19Z"/><path d="m17 20-3 5h3l-2 4 6-7h-3l2-2"/></svg>
          <svg v-else-if="weatherMeta.icon === 'fog'" viewBox="0 0 32 32"><path d="M6 11h20M4 16h22M7 21h19"/></svg>
          <svg v-else viewBox="0 0 32 32"><path d="M7 23h17a5 5 0 0 0-1-9.9A8 8 0 0 0 7.8 15 4 4 0 0 0 7 23Z"/></svg>
        </div>
        <div class="weather-copy"><span class="weather-location">{{ weather.location }}</span><strong>{{ weatherLoading && weather.temperature === null ? '--' : weather.temperature }}°</strong><small>{{ weatherMeta.label }} · 最高 {{ weather.temperature_max ?? '--' }}° / 最低 {{ weather.temperature_min ?? '--' }}°</small></div>
      </section>

      <section class="assistant-panel" aria-label="ATLAS AI 助手">
        <div class="assistant-heading"><span class="assistant-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/><circle cx="12" cy="12" r="4"/></svg></span><div><strong>AI ASSISTANT</strong></div><span class="assistant-online" title="在线"></span></div>
        <div ref="assistantMessagesEl" class="assistant-messages" aria-live="polite"><div v-for="(item, index) in assistantMessages" :key="index" class="assistant-message" :class="item.role"><div v-if="item.role === 'assistant'" class="assistant-rich" v-html="formatAssistantContent(item.content)"></div><span v-else>{{ item.content }}</span></div><div v-if="assistantThinking" class="assistant-thinking" role="status" aria-label="AI 正在思考"><span class="thinking-orb"><i></i><i></i><i></i></span><span class="thinking-label">思考中<span class="thinking-ellipsis">...</span></span></div></div>
        <div v-if="assistantError" class="assistant-error">{{ assistantError }}</div>
        <form class="assistant-composer" @submit.prevent="sendAssistantMessage"><textarea v-model="assistantDraft" rows="2" maxlength="2000" placeholder="询问今日情报..." :disabled="assistantLoading" @keydown.enter.exact.prevent="sendAssistantMessage"></textarea><button v-if="assistantLoading" type="button" class="assistant-cancel" aria-label="取消生成" title="取消生成" @click="cancelAssistantMessage"><svg viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="1"/></svg></button><button v-else type="submit" :disabled="!assistantDraft.trim()" aria-label="发送" title="发送"><svg viewBox="0 0 24 24"><path d="m5 12 14-7-4 14-3.1-5.9L5 12Z"/><path d="m11.9 13.1 3.6-3.6"/></svg></button></form>
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

      <nav class="module-nav" aria-label="情报板块导航">
        <div class="module-nav-list">
          <button v-for="item in navItems" :key="item.label" class="module-nav-item" :class="{ active: activeNav === item.label }" @click="selectNav(item.label)">
            <span class="module-nav-copy"><strong>{{ item.label }}</strong><small>{{ item.en }}</small></span>
          </button>
        </div>
      </nav>

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
