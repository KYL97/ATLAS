"""ATLAS Intelligence Office —— 后端服务

技术栈: FastAPI + SQLModel + Uvicorn + APScheduler
职责:
  - 每天 10:00 调用 DeepSeek 接口生成「今日简报」并写入数据库
  - 对前端提供简报与市场快照数据

启动:
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

安全提示:
    DeepSeek 密钥请通过环境变量 DEEPSEEK_API_KEY 注入，不要提交到代码仓库。
"""

from __future__ import annotations

import json
import logging
import os
from asyncio import to_thread
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Literal, Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from volcenginesdkarkruntime import Ark

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas")

# --------------------------------------------------------------------------- #
# 配置（密钥从 backend/.env 读取，源码不再内置）
# --------------------------------------------------------------------------- #

load_dotenv()  # 自动加载同目录下的 .env

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-evolving")

if not DEEPSEEK_API_KEY:
    logger.warning(
        "未检测到 DEEPSEEK_API_KEY，简报生成将失败。"
        "请复制 .env.example 为 .env 并填入密钥。"
    )

DATABASE_URL = "sqlite:///./atlas.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


# --------------------------------------------------------------------------- #
# 数据模型
# --------------------------------------------------------------------------- #

class Brief(SQLModel, table=True):
    """今日简报（中英双语）"""

    id: Optional[int] = Field(default=None, primary_key=True)
    brief_date: date = Field(index=True)
    eyebrow: str
    # 双语字段
    headline_en: str = ""
    headline_zh: str = ""
    subtitle_en: str = ""
    subtitle_zh: str = ""
    feature_headline_en: str = ""
    feature_headline_zh: str = ""
    feature_text_en: str = ""
    feature_text_zh: str = ""
    feature_index: str = "01"
    kicker: str = "ORIGINAL-LANGUAGE EDITION"
    priority: str = "HIGH PRIORITY"
    updated: str = ""
    sources: int = 8


class MarketItem(SQLModel, table=True):
    """市场快照条目"""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    code: str = Field(index=True)
    value: str
    status: str
    tone: str = "up"  # up | down
    sort: int = 0


class AssistantExchange(SQLModel, table=True):
    """AI 助手的一轮用户提问与回答记录。"""

    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    created_at: datetime = Field(default_factory=datetime.now, index=True)


# --------------------------------------------------------------------------- #
# DeepSeek 简报生成
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = (
    "你是 ATLAS 情报办公室的首席分析师，为高管撰写每日双语情报简报。"
    "选题请重点关注：(1) 重大国际时事与地缘政治事件；"
    "(2) 流通性货币动向——美元、欧元、日元、人民币等主要货币及外汇/汇率、"
    "利率与央行政策；(3) 原油及能源类市场（布伦特/WTI 原油、天然气、OPEC+ 动向、"
    "供给冲击等）。围绕上述主题分析其对全球市场的影响，生成当日的执行级情报摘要。"
)

USER_PROMPT_TEMPLATE = (
    "请生成 {today} 的今日简报，中英文内容需语义一致，严格返回如下 JSON（不要包含多余文字）：\n"
    "{{\n"
    '  "headline_en": "一句英文标题，概括当日核心主题，简洁有力",\n'
    '  "headline_zh": "对应的中文标题",\n'
    '  "subtitle_en": "一句英文副标题，概括今日情报要点",\n'
    '  "subtitle_zh": "对应的中文副标题",\n'
    '  "feature_headline_en": "一句英文主标题，描述当日最重要的分析结论",\n'
    '  "feature_headline_zh": "对应的中文主标题",\n'
    '  "feature_text_en": "英文正文，以 \'Fact:\' 陈述事实、以 \'Assessment:\' 给出判断，200 字以内",\n'
    '  "feature_text_zh": "对应的中文正文，以\'事实：\'和\'研判：\'组织",\n'
    '  "priority": "HIGH PRIORITY 或 MEDIUM PRIORITY"\n'
    "}}"
)


async def call_deepseek(today: str) -> dict:
    """调用 DeepSeek Chat 接口，返回解析后的简报字段。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在 backend/.env 中配置")

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(today=today)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def generate_brief(append: bool = False) -> Brief:
    """调用 DeepSeek 生成简报并写入数据库。

    append=False：按当天日期 upsert（每日定时/刷新用，覆盖当天正式版）。
    append=True ：总是新增一条（「下一篇」用，保留为历史，可回看）。
    """
    today = date.today()
    today_str = today.strftime("%Y.%m.%d")
    logger.info("开始生成 %s 的简报 (append=%s)", today_str, append)

    fields = await call_deepseek(today.isoformat())

    now = datetime.now().strftime("%H:%M")
    with Session(engine) as session:
        brief = None
        if not append:
            brief = session.exec(select(Brief).where(Brief.brief_date == today)).first()
        if brief is None:
            brief = Brief(brief_date=today, eyebrow="")
            session.add(brief)

        brief.eyebrow = f"DAILY EXECUTIVE INTELLIGENCE · {today_str}"
        brief.headline_en = fields.get("headline_en", "")
        brief.headline_zh = fields.get("headline_zh", "")
        brief.subtitle_en = fields.get("subtitle_en", "")
        brief.subtitle_zh = fields.get("subtitle_zh", "")
        brief.feature_headline_en = fields.get("feature_headline_en", "")
        brief.feature_headline_zh = fields.get("feature_headline_zh", "")
        brief.feature_text_en = fields.get("feature_text_en", "")
        brief.feature_text_zh = fields.get("feature_text_zh", "")
        brief.priority = fields.get("priority", "HIGH PRIORITY")
        brief.updated = f"更新于 {now} CST"

        session.commit()
        session.refresh(brief)
        logger.info("今日简报已更新: %s", brief.headline_en)
        return brief


async def generate_brief_safe() -> None:
    """定时任务包装：吞掉异常，避免调度器崩溃。"""
    try:
        await generate_brief()
    except Exception as exc:  # noqa: BLE001
        logger.exception("生成今日简报失败: %s", exc)


# --------------------------------------------------------------------------- #
# 市场快照刷新（每分钟）
# --------------------------------------------------------------------------- #

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


async def refresh_markets() -> list[MarketItem]:
    """刷新市场快照。

    目前 BTC 接入 CoinGecko 免费实时行情（无需密钥）；
    其余标的（原油/美元指数/黄金）暂为静态值，接入付费行情源后可一并实时化。
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            COINGECKO_URL,
            params={"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"},
        )
        resp.raise_for_status()
        data = resp.json()

    btc = data.get("bitcoin", {})
    price = btc.get("usd")
    change = btc.get("usd_24h_change")

    with Session(engine) as session:
        row = session.exec(select(MarketItem).where(MarketItem.code == "BTC")).first()
        if row and price is not None:
            row.value = f"${price:,.0f}"
            if change is not None:
                row.tone = "up" if change >= 0 else "down"
                row.status = f"{change:+.2f}%"
            session.add(row)
            session.commit()
            logger.info("BTC 已更新: %s (%s)", row.value, row.status)
        return session.exec(select(MarketItem).order_by(MarketItem.sort)).all()


async def refresh_markets_safe() -> None:
    """定时任务包装：吞掉异常，避免调度器崩溃。"""
    try:
        await refresh_markets()
    except Exception as exc:  # noqa: BLE001
        logger.warning("刷新市场快照失败: %s", exc)


# --------------------------------------------------------------------------- #
# 种子数据（后端首次启动 / DeepSeek 尚未返回时的兜底）
# --------------------------------------------------------------------------- #

def seed() -> None:
    with Session(engine) as session:
        if session.exec(select(Brief)).first() is None:
            session.add(
                Brief(
                    brief_date=date.today(),
                    eyebrow=f"DAILY EXECUTIVE INTELLIGENCE · {date.today().strftime('%Y.%m.%d')}",
                    headline_en="Energy shock meets industrial acceleration.",
                    headline_zh="能源冲击与产业加速并行",
                    subtitle_en="Today's brief: energy shock and industrial policy heat up together",
                    subtitle_zh="今日情报：能源冲击与产业政策同时升温（等待 DeepSeek 更新）",
                    feature_headline_en=(
                        "Hormuz risk lifts the inflation tail while Asian AI and Chinese "
                        "infrastructure investment keep accelerating"
                    ),
                    feature_headline_zh="霍尔木兹风险推高通胀尾部，亚洲 AI 与中国基建投资持续加速",
                    feature_text_en=(
                        "Fact: US–Iran maritime clashes kept Brent crude near a six-week high. "
                        "Assessment: markets face an energy-supply shock alongside expanding "
                        "technology investment."
                    ),
                    feature_text_zh=(
                        "事实：美伊海上冲突令布伦特原油维持在六周高位附近。"
                        "研判：市场同时面临能源供给冲击与科技投资扩张。"
                    ),
                    updated="等待 DeepSeek 首次生成",
                    sources=8,
                )
            )
        if session.exec(select(MarketItem)).first() is None:
            session.add_all(
                [
                    MarketItem(name="布伦特原油", code="BRENT", value="$96.19", status="高位风险", tone="up", sort=0),
                    MarketItem(name="美元指数", code="DXY", value="99.09", status="-0.07%", tone="down", sort=1),
                    MarketItem(name="现货黄金", code="XAU", value="$4,398", status="-0.7%", tone="down", sort=2),
                    MarketItem(name="比特币", code="BTC", value="$80,146", status="企稳", tone="up", sort=3),
                ]
            )
        session.commit()


# --------------------------------------------------------------------------- #
# 生命周期 + 调度器
# --------------------------------------------------------------------------- #

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    seed()

    # 每天 10:00（服务器本地时区）调用 DeepSeek 更新今日简报
    scheduler.add_job(generate_brief_safe, "cron", hour=10, minute=0, id="daily_brief")
    # 每 1 分钟刷新一次市场快照
    scheduler.add_job(refresh_markets_safe, "interval", minutes=1, id="markets", next_run_time=datetime.now())
    scheduler.start()
    logger.info("调度器已启动：每日 10:00 更新简报，每 1 分钟刷新市场快照")

    # 启动时若今天还没有 DeepSeek 版本，则立即在后台生成一次
    with Session(engine) as session:
        latest = session.exec(select(Brief).where(Brief.brief_date == date.today())).first()
    if latest is None or "DeepSeek" not in (latest.updated or ""):
        import asyncio

        asyncio.create_task(generate_brief_safe())

    yield
    scheduler.shutdown(wait=False)


# --------------------------------------------------------------------------- #
# 应用
# --------------------------------------------------------------------------- #

app = FastAPI(title="ATLAS Intelligence Office API", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# --------------------------------------------------------------------------- #
# 登录（演示：仅支持 admin / 123）
# --------------------------------------------------------------------------- #

# 演示账号，生产环境请改为数据库用户 + 密码哈希
DEMO_USERNAME = os.getenv("ATLAS_USER", "admin")
DEMO_PASSWORD = os.getenv("ATLAS_PASSWORD", "123")


class LoginRequest(BaseModel):
    username: str
    password: str


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=10)


@app.post("/api/login")
def login(req: LoginRequest) -> dict:
    """校验用户名密码，成功返回令牌。"""
    if req.username == DEMO_USERNAME and req.password == DEMO_PASSWORD:
        return {"token": "atlas-token-admin", "username": req.username}
    raise HTTPException(status_code=401, detail="用户名或密码错误")


# --------------------------------------------------------------------------- #
# ATLAS AI 助手（火山方舟）
# --------------------------------------------------------------------------- #

def get_assistant_context() -> str:
    """取当前简报和市场快照，作为助手回答的业务上下文。"""
    with Session(engine) as session:
        brief = session.exec(select(Brief).order_by(Brief.brief_date.desc())).first()
        market_items = session.exec(select(MarketItem).order_by(MarketItem.sort)).all()

    brief_context = "暂无今日简报"
    if brief:
        brief_context = (
            f"日期：{brief.brief_date}\n"
            f"标题：{brief.headline_zh or brief.headline_en}\n"
            f"副标题：{brief.subtitle_zh or brief.subtitle_en}\n"
            f"重点分析：{brief.feature_text_zh or brief.feature_text_en}"
        )
    markets_context = "；".join(
        f"{item.name}（{item.code}）{item.value}，{item.status}" for item in market_items
    ) or "暂无市场快照"
    return f"今日简报：\n{brief_context}\n\n市场快照：\n{markets_context}"


def extract_ark_text(response: object) -> str:
    """从 Responses API 返回结构中提取文本，兼容多段输出。"""
    text_parts: list[str] = []
    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue
        for content in getattr(output, "content", []):
            if getattr(content, "type", None) == "output_text" and getattr(content, "text", None):
                text_parts.append(content.text)
    return "\n".join(text_parts).strip()


async def ask_ark(req: AssistantRequest) -> str:
    """在线程中调用同步 Ark SDK，避免阻塞 FastAPI 事件循环。"""
    if not ARK_API_KEY:
        raise RuntimeError("缺少 ARK_API_KEY，请在 backend/.env 中配置")

    instructions = (
        "你是 ATLAS Intelligence Office 的 AI 情报助手。"
        "优先依据提供的今日简报和市场快照回答，用中文给出清晰、简洁、面向管理者的分析。"
        "直接给出最终答复，不要输出思考过程，也不要添加“说明”或“最终答案”等标签。"
        "当上下文没有足够信息时，请明确说明，不要编造实时数据。\n\n"
        f"{get_assistant_context()}"
    )
    messages = [
        {
            "role": item.role,
            "content": [{"type": "input_text", "text": item.content}],
        }
        for item in req.history
    ]
    messages.append(
        {"role": "user", "content": [{"type": "input_text", "text": req.message}]}
    )

    def create_response() -> object:
        client = Ark(base_url=ARK_BASE_URL, api_key=ARK_API_KEY)
        return client.responses.create(
            model=ARK_MODEL,
            instructions=instructions,
            input=messages,
            # 推理模型会先消耗一部分 token 进行内部分析，需保留足够预算生成答复。
            max_output_tokens=2000,
            store=False,
        )

    response = await to_thread(create_response)
    reply = extract_ark_text(response)
    if not reply:
        raise RuntimeError("Ark 未返回可展示的文本")
    return reply


@app.post("/api/assistant/chat")
async def assistant_chat(req: AssistantRequest) -> dict:
    """基于今日 ATLAS 情报上下文回答用户问题。"""
    try:
        reply = await ask_ark(req)
        with Session(engine) as session:
            session.add(AssistantExchange(question=req.message, answer=reply))
            session.commit()
        return {"reply": reply}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ark 助手调用失败: %s", exc)
        raise HTTPException(status_code=502, detail="AI 助手暂时无法响应，请稍后重试") from exc


@app.get("/api/assistant/history")
def assistant_history(limit: int = Query(default=30, ge=1, le=50)) -> list[AssistantExchange]:
    """返回最近的助手问答记录，按发生时间正序排列。"""
    with Session(engine) as session:
        exchanges = session.exec(
            select(AssistantExchange)
            .order_by(AssistantExchange.created_at.desc())
            .limit(limit)
        ).all()
    return list(reversed(exchanges))


@app.get("/api/brief/today")
def brief_today() -> Brief:
    """返回最新一期今日简报。"""
    with Session(engine) as session:
        brief = session.exec(select(Brief).order_by(Brief.brief_date.desc())).first()
        if brief is None:
            raise HTTPException(status_code=404, detail="暂无简报")
        return brief


@app.post("/api/brief/refresh")
async def brief_refresh() -> Brief:
    """手动触发 DeepSeek 立即生成今日简报（覆盖当天正式版，用于测试或临时刷新）。"""
    try:
        return await generate_brief()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"DeepSeek 生成失败: {exc}") from exc


@app.post("/api/brief/next")
async def brief_next() -> Brief:
    """「下一篇」：调用 DeepSeek 再生成一篇（换角度/话题），追加为新记录并返回。"""
    try:
        return await generate_brief(append=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"DeepSeek 生成失败: {exc}") from exc


@app.get("/api/markets")
def markets() -> list[MarketItem]:
    """返回市场快照列表。"""
    with Session(engine) as session:
        return session.exec(select(MarketItem).order_by(MarketItem.sort)).all()


@app.post("/api/markets/refresh")
async def markets_refresh() -> list[MarketItem]:
    """手动触发市场快照刷新。"""
    try:
        return await refresh_markets()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"刷新失败: {exc}") from exc
