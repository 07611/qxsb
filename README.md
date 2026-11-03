# Moodwave · 心绪声场

基于**本地人脸情绪识别**的歌曲推荐系统：浏览器读取图片 / 摄像头 / 视频，本地服务完成表情推理，再用曲调特征与个人反馈推荐本地曲目和在线试听。

前端 Vue 3 + Vite + Element Plus，后端 FastAPI + SQLAlchemy + SQLite，全部算法、模型与演示音频/人脸随仓库离线交付。

```
表情（YuNet + FER+ + 几何校准） → 六维情绪 → 音乐特征（Krumhansl + Thayer） → 加权推荐 + MMR
```

---

## 1. 快速启动

### 环境要求

- Python **3.11+**（本项目在 3.14 上开发验证）
- Node.js **20+** 与 npm
- 无系统级数据库 / Redis 要求；SQLite 与进程内缓存开箱即用

### 1.1 配置

```bash
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
# 将上面生成的随机串填入 .env 的 JWT_SECRET
```

> `.env` 已被 `.gitignore` 忽略。不要提交任何真实密钥。

### 1.2 安装依赖

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.txt

npm install
```

### 1.3 启动开发环境

后端（项目根目录执行）：

```bash
python -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

首次启动会自动建表、下载不依赖外网的演示数据（本地资源）、分析本地曲目并写入种子数据。也可以显式执行幂等种子：

```bash
python database/seeds/seed.py
# 或 cd backend && python -m app.seed
```

前端：

```bash
npm run dev
# http://localhost:5173
```

Vite 默认把 `/api`、`/media`、`/s` 代理到 `http://127.0.0.1:8000`，可用 `VITE_PROXY_TARGET` 修改。

### 1.4 生产构建 / 单端口运行

```bash
npm run build
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000，本服务同时提供 SPA、静态媒体和 API
```

### 1.5 演示账号

| 角色 | 邮箱 | 密码 |
|---|---|---|
| 管理员 | `admin@moodwave.app` | `Admin@12345` |
| 普通用户 | `demo@moodwave.app` | `Demo@12345` |

密码可通过 `.env` 的 `SEED_ADMIN_PASSWORD` / `SEED_USER_PASSWORD` 覆盖。**首次体验后请在个人中心修改密码。** 种子脚本只创建缺失账号，不会重置已修改的密码。

演示样本位于首页「六个可直接演示的情绪样本」，分别覆盖 happy / sad / angry / surprised / fear / neutral。

---

## 2. 技术架构

| 层 | 实现 |
|---|---|
| 前端 | Vue 3 `<script setup>` · Vite · Pinia · Vue Router · Element Plus · Vue I18n |
| 视觉 | 极简暖白 / Linear-Notion 取向；Space Grotesk + Manrope + JetBrains Mono；明暗两套 CSS 变量；移动端单列 |
| 后端 | FastAPI · Pydantic v2 · SQLAlchemy 2 · Uvicorn |
| 数据 | SQLite（WAL）· 进程内 TTL 缓存 · 本地磁盘静态服务 |
| 认证 | JWT Access 15min + 可撤销 Refresh 7d（HttpOnly Cookie）· bcrypt · RBAC |
| 识别 | OpenCV YuNet（人脸+5 关键点）· FER+ 8 类 ONNX · 几何先验校准 |
| 音乐 | wave + numpy 提取 BPM / RMS / chroma / spectral centroid / 调式；iTunes Search API 在线试听 |
| 推荐 | 情绪概率 + valence/arousal 距离 + 用户反馈 + 新鲜度 + 热度；同艺人最多 2 首 MMR 重排 |
| 交付 | Docker 多阶段构建 · Compose · Render · GitHub Actions |

```
.
├── backend/
│   ├── app/
│   │   ├── routers/          auth / users / content / uploads / music / social / admin / analytics / reports
│   │   ├── services/         emotion / audio / recommendation / storage / mailer / notify / cache / ratelimit / analytics
│   │   ├── templates/email/  邮件模板（与业务代码分离）
│   │   ├── locales/          服务端 i18n 语言包
│   │   ├── data/             FER+ 与 YuNet ONNX 模型
│   │   └── main.py           应用入口、中间件、静态资源、生命周期
│   ├── media/                演示人脸、原创本地音频、SVG 封面、运营位
│   ├── tests/                API 集成测试
│   └── requirements.txt
├── src/                      Vue SPA
│   ├── pages/                22 个路由页面 + 5 个后台页面
│   ├── components/           layout / emotion / recommendation / content / settings / admin / ui
│   ├── services/             统一 axios 封装、自动刷新令牌、错误归一化
│   ├── stores/               auth / emotion / player / notifications / ui
│   ├── i18n/                 zh-CN / en-US 语言包
│   ├── styles/               tokens / base / element 覆写
│   └── utils/                图片压缩、直传、埋点、错误上报、格式化
├── database/
│   ├── migrations/001_init.sql
│   └── seeds/seed.py
├── docker/                   Dockerfile + compose
├── docs/                     架构、算法、任务书摘要、素材署名
├── tests/frontend/           Vitest
└── .github/workflows/ci.yml
```

**API**：98 个操作，统一 `/api/v1` 前缀，Swagger 在 `/api/docs`。所有响应形如：

```json
{ "code": 0, "message": "ok", "data": {} }
```

错误：`4xx` / `5xx` 均带可读 `message`；参数校验 `data.errors[]` 含字段级信息；请求响应头返回 `X-Request-ID`。

---

## 3. 27 项功能与代码位置

| # | 功能 | 实现 / 页面 |
|---|---|---|
| 1 | 邮箱密码注册登录 | `routers/auth.py`、`/login`、`/register`；bcrypt、唯一邮箱、5 次锁定 15min、Access+Refresh、统一错误 |
| 2 | 个人资料与头像 | `routers/users.py`、`/settings/profile`；头像文件上传、昵称唯一 2–20、邮箱/手机号二次验证 |
| 3 | RBAC | `security.py`、`routers/admin.py`；服务端权限即时读取数据库，401/403 分离 |
| 4 | 图片/多媒体上传 | `services/storage.py`、`/api/v1/upload/presign`；前端压缩、magic number、400/1200 缩略图、固定宽高 |
| 5 | 分类与标签 | `routers/content.py`、`/categories/:slug`、`/tags/:slug`；两级分类、冗余计数、热门标签 |
| 6 | 全文搜索 | `/search`；LIKE 转义、分页、60 字上下文高亮、搜索日志、热门词 |
| 7 | 通知中心 | `routers/social.py`、`/notifications`；冗余未读数、类型筛选、一键已读、90 天归档 |
| 8 | 管理后台 | `/admin` 及 5 个子页；同 JWT 独立入口、统一 `/admin` 前缀、搜索筛选排序分页、删除/导出审计 |
| 9 | 文件预签名直传 | `POST /upload/presign` → 浏览器 PUT → `POST /attachments`；签名 10min、MIME/大小限制、登记时回查 |
| 10 | 限流与防刷 | `services/ratelimit.py`；Redis（配置后）/ SQLite 原子计数，429 + Retry-After，幂等键 10s |
| 11 | 日志与错误监控 | `logging_config.py`、`/logs/client`；JSON 结构化日志、requestId、全局异常、前端错误捕获、可选 Sentry/告警 |
| 12 | 种子与演示账号 | `app/seed.py`；幂等、两个账号、各业务状态、本地稳定图片 |
| 13 | 验证码 | `/auth/code/send`、`/auth/code/verify`；6 位、5min、60s 重发、HMAC 哈希、一次性、IP 日限 |
| 14 | 第三方登录 | `/auth/oauth/:provider`；GitHub / Google / 微信适配，state 一次性、独立账号、不按邮箱静默合并 |
| 15 | 找回密码 | `/forgot-password`；15min 一次性令牌、成功后撤销全部刷新令牌、不泄露账号是否存在 |
| 16 | 会话管理 | `/settings/security`；设备/IP/活跃时间、单会话撤销、IP 打码 |
| 17 | 国际化 | `src/i18n/*`、`/api/v1/i18n/:locale`；界面语言持久化，日期数字 `Intl` 格式化 |
| 18 | 分享与外链卡片 | `POST /shares`、`GET /s/:code` 服务端 HTML + OG meta；短码、有效期、仅公开内容 |
| 19 | 邮件通知 | `services/mailer.py`；线程异步、3 次退避重试、模板与代码分离、频率限制、加密邮件模板变量 |
| 20 | 统计报表 | `/admin/reports`、`daily_metrics` 预聚合、CSV 导出 + 审计 |
| 21 | 反馈工单 | `/feedback`、`/admin/feedback`；截图、工单号、状态机、原始描述锁定、回复通知与邮件 |
| 22 | 缓存层 | `services/cache.py`；`业务:实体:标识:版本`、TTL、写后删缓存、未命中回源 |
| 23 | 埋点与行为分析 | `utils/track.js`、`routers/analytics.py`；异步批量、敏感字段过滤、HMAC 用户标识、事件定义、漏斗/留存、365 天归档 |
| 24 | 多端推送 | `/admin` 推送面板；用户级日限 5 条、渠道开关、夜间营销静默、模板化、失败重试/失败标记、可选 webhook |
| 25 | 注册审核与邀请码 | `/pending`、`/admin/users`；邀请码一次性、pending 用户只入待审页、审核审计 |
| 26 | 短信通知 | `/auth/code/send` 的 SMS 通道；单手机号日限 10 条、内容最小化、SmsLog 留痕 |
| 27 | 公告与运营位 | `/admin#banners`、`GET /banners`；定时上下线、位置数量上限、固定比例、链接白名单 |

> 支付金额未在本产品中使用；按照任务书约定，若扩展订单字段统一使用整数「分」，报表注明精度。

---

## 4. 算法说明

### 4.1 人脸情绪识别

1. **YuNet** 检测最大人脸及 5 个关键点（双眼、鼻尖、双嘴角），检测分数阈值 0.65。
2. 裁切灰度化到 **64×64**，输入 **FER+ 8 类表情 ONNX**：neutral / happiness / surprise / sadness / anger / disgust / fear / contempt。
3. 几何先验：关键点定位嘴部 → Otsu 暗区 + 二次曲线拟合嘴线；眼周对比度估计开合；眉间明暗估计紧张度。
4. CNN 高置信时 90% CNN + 10% 几何；置信度低时 70/30。disgust / contempt 合并映射到六类并归一化。

模型文件随仓库交付：`backend/data/emotion-ferplus-8.onnx`、`backend/data/face_detection_yunet_2023mar.onnx`。图片只在服务进程内解码推理，不落盘、不入库、不发第三方。

页面 `/algorithms` 与服务端 `GET /music/algorithm` 返回同一份算法说明；边界（遮挡、侧脸、低照度会显著降低准确率）也在页面明示。

### 4.2 曲调情绪识别

- 短时能量包络自相关估计 BPM；
- FFT 谱质心、动态范围、过零率；
- chroma 与 **Krumhansl** 大调/小调模板相关判断调式；
- 映射到 Thayer 二维平面：

```
valence  = f(调式, 明亮度, 过零率, 动态)
arousal  = f(BPM, 能量, 明亮度)
```

本地曲目由真实 WAV 计算（音频在 `backend/media/audio/`）；在线 iTunes 曲目无音频文件时使用情绪查询 + 曲风元数据回退，并在 UI 标注。为提升演示质量，本地曲库另有人工试听标签作为先验，与音频特征按 45%:55% 融合，原始分析结果保存在 `audio_features.analyzedMood` 中可查。

### 4.3 推荐策略

```
score = 0.42 × P(emotion)
      + 0.28 × (1 - valence/arousal 距离)
      + 0.12 × 用户品味相似度
      + 0.10 × 新鲜度
      + 0.08 × 热度归一化
```

先按当前情绪召回，融合收藏与喜欢/不喜欢反馈，剔除明确不喜欢；再按同艺人最多 2 首做 MMR 多样性重排。理由由曲目 BPM、调式、能量与目标情绪共同生成并展示。

---

## 5. 数据模型说明

完整的 39 张表、91 个索引定义在 `database/migrations/001_init.sql`，运行时由 SQLAlchemy `create_all` 保证一致。

任务书基础表的扩展（不改变已有字段名/类型）：

- `users`：`unread_count`（冗余未读）、登录失败计数/锁定、`email_verified`/`phone_verified`。
- `items`：`category_id`、`cover_url`、`cover_thumb_url`、`deleted_at`（软删除）。
- `attachments`：`detail_url`、`storage_key`。
- `notifications`：`message`（服务端组装文案）；新增 `notification_archive`。
- `email_logs`：`retry_count`、加密后的模板 `context`。
- `sms_logs`：移除原脚本中错误的 `phone UNIQUE`（同一号码必须可以留存多条发送记录），改为普通索引。
- `o_auth_accounts`：保留原 `provider_user_id`，新增字符串 `provider_uid` 存 openid（原 BIGINT 无法承载）。
- `banners`：新增 `position_code`（API 的 `position=home|discover|settings`），保留整数 position。
- 新增业务表：`tracks`、`emotion_logs`、`track_feedback`、`favorite_tracks`、`recommendation_logs`、`idempotency_keys`、`rate_limit_counters`、`client_logs`、`audit_logs`、`daily_metrics`、`event_archive`、`oauth_states`。
- 删除/更新分类或标签后通过后台任务重算 `post_count`，不在列表查询中实时 count。

---

## 6. 安全 / 可靠性

- 密码 bcrypt（rounds 由环境变量控制），账号锁 15 分钟；登录失败不区分用户不存在与密码错误。
- Refresh Token 仅存 SHA-256 哈希，刷新时轮换旧令牌；密码重置/修改、修改邮箱会撤销全部会话。
- 所有写接口（JSON）使用 10 秒幂等窗口；前端带 `X-Idempotency-Key`。文件直传按签名令牌限制。
- SQLAlchemy 参数化查询；上传 magic number + 尺寸限制 + 路径穿越校验；内容 HTML 清理。
- CORS 白名单、Secure/HttpOnly/SameSite Cookie、CSP、HSTS（HTTPS/生产）、X-Frame-Options、Permissions-Policy。
- 限流：登录 IP + 账号、验证码邮箱/手机、发帖、上传、事件等；429 携带 Retry-After。
- 全局异常统一结构 + requestId；4xx 记录 warn，5xx 记录 error，并触发可选告警 webhook/Sentry。
- 前端 ErrorBoundary、全局 Promise/渲染异常捕获；错误上报接口自身有限流，不会递归。
- 邮件模板变量加密落库（Fernet，密钥派生自 JWT_SECRET）；生产未配置 SMTP 时不会把邮件内容写成明文 outbox。
- 埋点自动剔除 password / token / email / phone 等敏感字段。

---

## 7. 环境变量

见 `.env.example`。关键项：

| 变量 | 说明 |
|---|---|
| `JWT_SECRET` | ≥32 字符，生产必须随机 |
| `DATABASE_URL` | 默认 SQLite；相对路径会锚定到项目根 |
| `MEDIA_ROOT` | 本地媒体目录 |
| `FRONTEND_ORIGIN` | CORS 白名单，逗号分隔 |
| `PUBLIC_BASE_URL` | 分享短链与 OG 绝对 URL |
| `COOKIE_SECURE` | 生产 HTTPS 必开 |
| `REDIS_URL` | 可选；多实例生产限流使用，留空降级 SQLite 原子计数 |
| `SMTP_*` | 未配置时只在 DEBUG 写本地 outbox |
| `GITHUB_*` / `GOOGLE_*` / `WECHAT_*` | 未配置的第三方登录入口隐藏 |
| `ENABLE_ONLINE_MUSIC` | iTunes 在线试听 |
| `EXPOSE_DEV_RESET_LINK` | 仅 DEBUG 返回本地重置链接，生产必须 false |
| `PUSH_WEBHOOK_URL` / `SMS_WEBHOOK_URL` | 可选真实推送通道，未配置时模拟并写任务日志 |

---

## 8. 测试

```bash
# 后端（独立 SQLite，覆盖认证、RBAC、CRUD、搜索、六种情绪、推荐、通知、工单、直传、幂等、分享、报表）
python -m pytest backend/tests -q

# 前端
npm test -- --run
npm run build
```

当前结果：后端 **11 passed**；前端 **4 passed**；生产构建通过。浏览器端到端 QA 覆盖首页、识别、推荐、登录、个人中心、设置、通知、反馈、歌单详情/编辑、5 个后台页面与 390px 移动端。

---

## 9. 部署

### Docker Compose

```bash
cp .env.example .env   # 修改 JWT_SECRET / PUBLIC_BASE_URL
docker compose -f docker/docker-compose.yml up --build
# http://localhost:8000
```

容器内前端构建产物在 `/app/dist`，FastAPI 同端口提供 SPA + API；SQLite、上传、日志均挂载命名卷。

### Render

`render.yaml` 使用 Docker 运行时和免费 Web 服务。部署后必须设置：

```
JWT_SECRET=<随机值>
PUBLIC_BASE_URL=https://<your-service>.onrender.com
FRONTEND_ORIGIN=https://<your-service>.onrender.com
COOKIE_SECURE=true
APP_ENV=production
```

免费实例文件系统是临时的，重新部署会回到种子数据。需要持久化时，给 Render 服务挂载磁盘（付费）并将 `DATABASE_URL` 指向磁盘内 SQLite；或迁移到 Postgres。

### CI

`.github/workflows/ci.yml`：Python 3.12 编译 + pytest；Node 22 单测 + 生产构建。

---

## 10. 验收自检

- [x] 27 项功能全部实现，包含 P0 / P1 / P2
- [x] P0 完整链路可跑通
- [x] 业务规则：锁定、bcrypt、唯一性、归属校验、两级分类、软删除、冗余计数、未读、一次性验证码/重置、限流、幂等、审计
- [x] README 一键启动；依赖锁定
- [x] 注册 → 登录 → 内容 CRUD → 刷新数据仍在（SQLite 落库）
- [x] 未登录 401、越权 403、校验 422
- [x] 表单失败保留输入，字段高亮
- [x] 375–390px 单列布局，无横向滚动
- [x] 密钥均来自环境变量，`.env` 被忽略
- [x] 全局错误边界 + 请求 ID + 前端错误上报
- [x] 本地真实识别模型 + 真实音频特征 + 在线试听
- [x] 页面内明确展示三套算法、边界与推荐公式
- [x] 六张真实感演示人脸，识别结果与样本标签一致

---

## 11. 素材与许可

- FER+ ONNX 模型：ONNX Model Zoo / FER+ 数据集，MIT。
- YuNet：OpenCV Zoo，Apache-2.0。
- 字体：Space Grotesk / Manrope / JetBrains Mono（SIL OFL，经 npm @fontsource 本地打包）。
- 本地曲目与封面：本项目程序化合成的原创演示音频（CC0），生成脚本 `backend/scripts/generate_assets.py`。
- 演示人像来自公开免费图片站，详见 `docs/ATTRIBUTIONS.md`。

更多实现说明：`docs/architecture.json`、`docs/algorithms.md`、`docs/prompt.md`。
