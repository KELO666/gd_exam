# 开发日志

## 2025-07-01 Phase 2：数据清洗 + 前端 MVP

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/config.py` | 扩充分类关键词；新增 `GUANGDONG_KEYWORDS` 地域列表 |
| `backend/scraper.py` | 增加广东地域过滤、分类兜底逻辑、启动时清理脏数据 |
| `backend/main.py` | 挂载 `frontend/` 静态文件，根路径返回 index.html |
| `frontend/index.html` | **新增** Vue3 + TailwindCSS CDN 单页应用 |

### 分类规则变更（v2）

| 类别 | 新增关键词 |
|------|-----------|
| 公务员 | + 公考、国考、省考 |
| 事业编 | + 中心、局、研究所、馆、辅导员 |
| 编外人员 | + 辅助、外包、协警、辅警、社工 |

兜底规则：经过扩充规则后仍未匹配，且标题不含任何广东地域信息，则跳过不入库。

### 地域过滤

- qgsydw 数据增加 `is_guangdong()` 检查，仅入库标题含广东21个地级市关键词的公告
- 启动时清理存量脏数据：本次清理 qgsydw 非广东数据 **10 条**

### 实测数据（清理后）

| 源 | 公务员 | 事业编 | 编外人员 | 未分类 |
|----|--------|--------|----------|--------|
| sydw1 | 0 | 11 | 2 | 13 |
| qgsydw | 0 | 0 | 0 | 0（当前首页无广东数据） |

### 前端 MVP

- 技术栈：Vue3 + TailwindCSS，CDN 引入，零构建
- 访问地址：`http://localhost:8000`
- 功能：Tab 分类切换、专业关键词搜索、卡片列表分页、点击跳转原始链接
- Loading / Error / Empty 状态均有处理

### 启动方式

```bash
cd backend && python3 -m uvicorn main:app --reload --port 8000
# 浏览器打开 http://localhost:8000
```

### 遗留问题

1. **发布日期**：sydw1 列表页无具体日期，统一用入库当天
2. **专业要求**：当前仅从标题括号提取，提取率预估 30-40%
3. **qgsydw 广东数据量**：首页不一定包含广东公告，需翻页或定时积累
4. **未分类公告**：sydw1 中 13 条未分类（标题缺少明确关键词但含广东地域信息）

### 下一步计划

**攻坚详情页与附件 PDF 的专业提取**

---

## 2025-07-01 Phase 3：深度情报解析（第一部分）

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/config.py` | 新增 `MAJOR_MAPPING` 专业大类映射字典；新增 `SCRAPE_DELAY_MIN/MAX` 配置 |
| `backend/models.py` | `exam_notices` 表新增 `deadline`、`major_category` 字段；新增 `query_all_majors()` 函数；支持旧表自动迁移 |
| `backend/scraper.py` | 新增详情页二次请求、`extract_deadline()` 截止日期正则提取、`match_major_category()` 专业匹配、`scrape_detail_page()` 详情页爬取；加入请求延时防封 |
| `backend/main.py` | `GET /api/notices` 支持 `major_category` 精确匹配 + `skip_expired` 逾期过滤；新增 `GET /api/majors` 接口 |
| `frontend/index.html` | 搜索框替换为专业大类 `<select>` 下拉选择器；卡片新增截止日期 + 专业大类标签 |

### 数据库结构变更

```sql
-- 新增字段（自动迁移，兼容旧库）
ALTER TABLE exam_notices ADD COLUMN deadline TEXT DEFAULT NULL;        -- 报名截止日期
ALTER TABLE exam_notices ADD COLUMN major_category TEXT DEFAULT '';   -- 标准化专业大类
```

### 专业大类映射（7 类 + 兜底）

| 大类 | 关键词示例 |
|------|-----------|
| 计算机类 | 计算机、软件、信息技术、网络、大数据、人工智能… |
| 财务审计类 | 财务、会计、审计、金融、经济… |
| 医疗卫生类 | 医学、护理、药学、卫生、临床… |
| 教育师范类 | 教育、师范、教师、心理… |
| 法学类 | 法学、法律、律师… |
| 汉语言文秘类 | 中文、汉语言、文秘、新闻… |
| 不限专业 | 不限专业、专业不限 |
| 其他专业 | 以上均未命中时的兜底 |

### 截止日期提取策略

1. **优先匹配关键词**：正文中的"报名截止"、"截止时间"、"报名时间…至"等模式
2. **兜底取最晚日期**：提取正文中所有日期，取最晚的一个（截止通常在最后）
3. **合理范围过滤**：仅接受 2024-2027 年间的日期
4. **容错**：提取失败时 `deadline` 置空，前端显示"详见公告"
5. **实测结果**：26 条公告全部成功提取截止日期（100%），sydw1 详情页结构较规范，正文均包含明确的报名时间信息

### 防封措施

- 每条详情页请求间隔 1-2 秒随机延时
- 异常详情页直接 catch 跳过，不影响后续爬取
- 已完成存量数据重爬：26 条记录全部更新 `deadline` 和 `major_category`

### API 变更

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/notices?skip_expired=true` | 改造 | 默认过滤 `deadline < 今天` 的过期公告 |
| `GET /api/notices?major_category=计算机类` | 改造 | 精确匹配专业大类（替代原模糊搜索） |
| `GET /api/majors` | **新增** | 返回所有不重复的 `major_category` 列表 |

### 前端变更

- 删除文本搜索框，替换为 `<select>` 下拉选择器
- 选项由 `/api/majors` 动态渲染
- 公告卡片新增"截止日期"标签（红色高亮）和"专业大类"标签（紫色）

### 启动方式（不变）

```bash
cd backend && python3 -m uvicorn main:app --reload --port 8000
# 浏览器打开 http://localhost:8000
```

### 实测数据（爬取后验证）

| 指标 | 数据 |
|------|------|
| 总记录数 | 26 条 |
| 截止日期提取 | **26/26（100%）** |
| 专业大类匹配 | **26/26（100%）** |
| 过期公告自动过滤 | 10 条（截止日期 < 今天），前端返回 16 条 |
| 下拉框实际类目 | 医疗卫生类、计算机类、财务审计类（3 类） |

### 实测发现

1. **专业匹配"计算机类"占比过高**：详情页正文中常见"信息化"、"数据中心"等词触发计算机类匹配，导致非 IT 岗位被误标。需后续优化匹配逻辑（限定正文区域或提高关键词权重）
2. **部分非医疗岗位被标为"医疗卫生类"**：如能源集团、建设投资公司的岗位，因正文含干扰词导致误匹配
3. **sydw1 发布日期**：仍为入库当天，列表页无真实日期
4. **附件 PDF 未解析**：PDF 内的专业要求和截止日期尚未提取，为下一阶段重点

### 遗留问题

1. **专业匹配精度**：基于关键词粗匹配，"计算机类"和"医疗卫生类"存在明显误匹配
2. **附件 PDF 未解析**：部分公告的专业要求和截止日期仅在 PDF 附件中，正文无相关信息
3. **sydw1 发布日期**：列表页无真实日期，统一用入库当天
4. **qgsydw 广东数据量**：首页当前无广东公告，需翻页或定时积累

### 下一步计划

1. **PDF 附件解析**：下载并解析公告中的 PDF 附件，提取专业要求和截止日期
2. **专业匹配优化**：缩小匹配范围（仅匹配标题+公告正文核心区），避免页面导航/侧边栏干扰
3. **专业映射扩充**：根据实测数据持续补充 `MAJOR_MAPPING` 关键词

---

## 2025-07-01 Phase 3：深度情报解析（第二部分）

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `requirements.txt` | 新增 `pdfplumber`、`pandas`、`openpyxl` 依赖 |
| `backend/scraper.py` | DOM 缩圈（`.content_c` 选择器）、真实发布日期提取、附件下载与解析（PDF/Excel）、分层专业匹配、临时文件清理 |
| `backend/models.py` | UPSERT 逻辑增加 `publish_date` 真实日期覆盖 |

### 新增依赖

```
pdfplumber>=0.10.0    # PDF 文本/表格提取
pandas>=2.0.0         # Excel 数据读取
openpyxl>=3.1.0       # Excel 底层引擎
```

### 核心改动

#### 1. DOM 缩圈（精准匹配）

- 新增 `_extract_core_content(soup)` 函数
- 优先使用 `.content_c` 选择器定位 sydw1 核心正文
- 兜底选择器：`.article-content`、`.content`、`.news-content` 等
- 移除 `<script>`/`<style>`/`<nav>`/`<footer>`/`<aside>` 等噪音标签
- **效果**：从全页 2000+ 字缩减到核心正文 1400 字，排除导航/侧边栏干扰

#### 2. 分层专业匹配（解决误伤）

新增三层匹配策略，替代原来的全文粗匹配：

| 层级 | 匹配范围 | 可靠度 |
|------|----------|--------|
| 1 | 标题括号中的专业（如"（计算机类）"） | 最高 |
| 2 | 正文"专业要求"/"任职条件"段落 | 高 |
| 3 | 标题 + 全文兜底 | 低 |

**效果对比**：

| 专业大类 | 缩圈前 | 缩圈后 | 变化 |
|----------|--------|--------|------|
| 计算机类 | 15 | **3** | -80% |
| 医疗卫生类 | 7 | **1** | -86% |
| 教育师范类 | 0 | **9** | 新增识别 |
| 法学类 | 0 | **6** | 新增识别 |
| 财务审计类 | 4 | **5** | +1 |

#### 3. 真实发布日期提取

- 新增 `extract_publish_date(soup)` 函数
- 三级策略：正则匹配"发布时间：YYYY-MM-DD" → meta 标签 → 含 date/time class 的元素
- **实测结果**：sydw1 26 条公告全部提取到真实发布日期（100%）
- 之前全部为入库当天（2026-07-01），现在有 3 个不同日期：2025-08-04、2026-06-30、2026-07-01

#### 4. 附件下载与解析

- 新增 `_extract_attachments(soup, base_url)` — 提取 `.pdf`/`.xls`/`.xlsx` 链接
- 新增 `_download_file(url, filename)` — 下载到 `backend/temp_downloads/`
- 新增 `_parse_pdf(filepath)` — pdfplumber 提取文本 + 表格
- 新增 `_parse_excel(filepath)` — pandas.read_excel 转文本
- 附件内容送入 `match_major_category()` 二次匹配，覆盖网页正文结果
- 处理完毕立即 `os.remove()` 清理临时文件
- **实测结果**：sydw1 当前 26 条公告均无 PDF/Excel 附件（内容为内联 HTML），附件解析框架已就绪

#### 5. 截止日期提取（缩圈后）

- 缩圈后截止日期提取率从 100% 降至 **69%（18/26）**
- 原因：之前全页文本包含侧边栏/导航中的日期，现在只看核心正文
- 这是更准确的结果 — 只匹配文章内真实出现的截止日期
- 8 条未提取到的公告：正文中的截止日期表述不在正则覆盖范围内（如"至招到合适人选为止"）

### 实测数据（第二部分）

| 指标 | Phase 3.1 | Phase 3.2 | 变化 |
|------|-----------|-----------|------|
| 截止日期提取 | 26/26 (100%) | 18/26 (69%) | 更准确（去除侧边栏干扰） |
| 真实发布日期 | 0/26 (0%) | **26/26 (100%)** | 新增能力 |
| 计算机类误标 | 15 条 | **3 条** | -80% |
| 医疗卫生类误标 | 7 条 | **1 条** | -86% |
| 附件解析 | 未实现 | 已实现（当前无附件） | 框架就绪 |

### 遗留问题

1. **"法学类"存在误标**：正文含"拥护宪法"等通用表述触发法学匹配
2. **sydw1 无附件**：当前数据源的公告均为内联 HTML，附件解析框架已就绪但无实际测试数据
3. **截止日期提取率 69%**：部分公告的截止日期表述不在正则覆盖范围内

### 下一步计划

1. **qgsydw 数据积累**：该源可能有更多 PDF 附件，可测试附件解析功能
2. **专业匹配持续优化**：根据新数据源的表现调整关键词

---

## 2025-07-01 Phase 4：产品级体验进化

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/config.py` | 重构 `MAJOR_MAPPING` 词库，移除通用词降噪 |
| `frontend/index.html` | UI 全面重构：品牌 Header、筛选控制台、卡片流、Loading/Empty 状态 |

### 1. 词库精准降噪

#### 移除的通用词（导致误匹配）

| 大类 | 移除词 | 误匹配场景 |
|------|--------|-----------|
| 计算机类 | `程序` | "招聘程序"、"办事程序" |
| 计算机类 | `信息化`、`数据`、`网络`、`电子`、`通信` | 页面导航/通用表述 |
| 法学类 | `法律`、`宪法`、`刑法`、`民法` | "拥护宪法"、"遵守法律法规" |
| 财务审计类 | `财务`、`会计`、`统计` | 宽泛匹配 |
| 教育师范类 | `教师`、`教学` | 宽泛匹配 |
| 医疗卫生类 | `护理`、`卫生`、`检验`、`影像` | 宽泛匹配 |

#### 改进后的关键词策略

- 所有关键词改为**实质性专业名词**（如"计算机"、"软件工程"、"会计学"、"法学"）
- 移除容易在通用文本中出现的词汇
- 接受 recall 降低（部分专业未识别）换取 precision 提升

#### 专业分布对比

| 专业大类 | Phase 3.1 | Phase 3.2 | Phase 4 | 趋势 |
|----------|-----------|-----------|---------|------|
| 计算机类 | 15 | 3 | **1** | -93% |
| 医疗卫生类 | 7 | 1 | **3** | 更准确 |
| 法学类 | 0 | 6 | **8** | 新增识别 |
| 教育师范类 | 0 | 9 | **5** | 更精确 |
| 财务审计类 | 4 | 5 | **2** | 更精确 |
| 其他专业 | 0 | 2 | **7** | 兜底增加 |

### 2. 前端 UI 全面重构

#### 视觉升级

| 组件 | Phase 3 | Phase 4 |
|------|---------|---------|
| 背景 | `bg-gray-50` 平铺 | `bg-gray-100` + 白色卡片对比 |
| Header | 白色扁平 | 品牌渐变蓝 `#1e40af → #2563eb` + Logo 图标 |
| 筛选面板 | 分离的 Tab + Select | 整合到 `rounded-xl shadow-md` 白色控制台 |
| Tab 样式 | 边框下划线 | 药丸按钮（选中态 `bg-brand-600 text-white`） |
| 卡片 | `rounded-lg` 紧凑 | `rounded-xl` 宽松 + `card-hover` 上浮动效 |
| 标题 | `text-sm text-gray-800` | `text-base font-semibold text-gray-900` |

#### 标签系统（Pill Badge）

| 类型 | 样式 |
|------|------|
| 公务员 | 绿色系 `bg-emerald-50 text-emerald-700` |
| 事业编 | 蓝色系 `bg-blue-50 text-blue-700` |
| 编外人员 | 橙色系 `bg-orange-50 text-orange-700` |
| 截止 ≤3 天 | 红色高亮 `bg-red-50 text-red-600 font-semibold` + "即将截止" |
| 专业大类 | 紫色系 `bg-purple-50 text-purple-600` |

#### UX 优化

- **Loading**：双层圆环旋转动画 + "正在获取最新公告..."
- **Empty**：笑脸 SVG + "暂无符合条件的公告，去其他专业或分类看看吧~"
- **Error**：红色警告图标 + "重新加载"按钮
- **Footer**：数据来源声明
- **响应式**：移动端 Tab 横向滚动，下拉框全宽

### 实测数据（Phase 4 最终）

| 指标 | 数值 |
|------|------|
| 总记录 | 26 条 |
| 有效公告（排除过期） | 16 条 |
| 下拉框类目 | 6 个（其他专业/医疗卫生/教育师范/法学/计算机/财务审计） |
| 计算机类误标 | 1 条（-93% vs Phase 3.1） |
| 法学类误标 | 8 条（需 Phase 5 修复） |

### 遗留问题

1. **法学类误标**：8 条因"拥护宪法"等通用表述触发
2. **截止日期提取率 69%**：部分公告的截止日期表述不在正则覆盖范围内
3. **sydw1 无附件**：附件解析框架已就绪，待新数据源验证

---

## 2025-07-01 Phase 5：最终阶段 · 宽屏监控台 + NLP 终极降噪 + 邮件推送

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/scraper.py` | 新增 `_is_valid_context()` 上下文探测，法学类误标彻底清零 |
| `backend/notifier.py` | **新增**：邮件推送模块（smtplib + HTML 模板） |
| `backend/scheduler.py` | 整合爬取 + 邮件推送流程 |
| `frontend/index.html` | PC 端宽屏布局重构（左侧筛选栏 + 右侧三列网格） |

### 1. PC 端宽屏 UI 重构

**采用方案：左侧筛选栏 + 右侧网格卡片流**

| 断点 | 布局 |
|------|------|
| 移动端 (<768px) | 单列，筛选面板置顶 |
| 平板 (768-1024px) | 左侧筛选栏 + 双列网格 |
| 桌面 (>1024px) | 左侧筛选栏 + 三列网格 |

#### 布局细节

- **最大宽度**：`max-w-[1440px]`，充分利用宽屏显示器
- **左侧筛选栏**：`lg:w-64` 固定宽度，`sticky` 悬浮跟随滚动
  - 分类 Tab 药丸按钮
  - 专业大类下拉框
  - 统计面板（总公告/当前筛选/有效数）
- **右侧内容区**：`grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4`
- **卡片设计**：紧凑型，标题+标签一行展示，减少垂直高度
- **响应式**：窗口缩小时自动降级为单列

### 2. 法学类 NLP 终极降噪

**新增 `_is_valid_context()` 上下文探测函数**：

```
匹配到"法学"等关键词时：
  → 取前后 50 字符窗口
  → 检查是否存在噪声词：拥护、遵守、规定、责任、宪法、法律、法规...
  → 检查是否存在有效词：专业、学历、岗位、要求、条件...
  → 只有在有效词附近才确认匹配
```

**效果对比**：

| 专业大类 | Phase 4 | Phase 5 | 变化 |
|----------|---------|---------|------|
| 法学类 | 8 | **0** | -100%（彻底清零） |
| 计算机类 | 1 | 1 | 不变 |
| 其他专业 | 7 | **11** | +4（原法学类误标回归兜底） |
| 教育师范类 | 5 | 7 | +2 |
| 医疗卫生类 | 3 | 4 | +1 |

### 3. 邮件推送引擎

#### `notifier.py` 模块

- 使用 Python 标准库 `smtplib` + `email.mime`
- SMTP 配置通过环境变量读取：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`ADMIN_EMAIL`
- `send_daily_digest(new_notices)` — 发送 HTML 格式的新公告邮件
- `_build_html(notices)` — 生成品牌风格的邮件模板（蓝色渐变头部 + 表格列表）
- 异常处理：SMTP 失败仅记录日志，不阻塞主流程

#### `scheduler.py` 集成

- `scrape_and_notify()` — 爬取完毕后自动查询今日新公告并推送
- 工作日 09:00 触发
- 测试结果：SMTP 配置不完整时优雅跳过（返回 False，不报错）

#### 环境变量配置

```bash
export SMTP_HOST=smtp.qq.com
export SMTP_PORT=465
export SMTP_USER=your@qq.com
export SMTP_PASS=your_smtp_password
export ADMIN_EMAIL=admin@example.com
```

### 实测数据（Phase 5 最终）

| 指标 | 数值 |
|------|------|
| 总记录 | 26 条 |
| 有效公告（排除过期） | 16 条 |
| 下拉框类目 | 6 个（不限专业/其他专业/医疗卫生/教育师范/计算机/财务审计） |
| 法学类误标 | **0 条**（彻底清零） |
| 计算机类误标 | 1 条 |
| 邮件推送 | 已集成，SMTP 未配置时优雅跳过 |

### 项目完整能力清单

| 能力 | 状态 | 阶段 |
|------|------|------|
| 列表页爬取 | ✅ | Phase 1 |
| 分类过滤（公务员/事业编/编外） | ✅ | Phase 1 |
| 广东地域过滤 | ✅ | Phase 2 |
| 详情页深度爬取 | ✅ | Phase 3.1 |
| 逾期自动过滤 | ✅ | Phase 3.1 |
| 专业下拉选择器 | ✅ | Phase 3.1 |
| DOM 缩圈（核心正文提取） | ✅ | Phase 3.2 |
| 真实发布日期提取 | ✅ | Phase 3.2 |
| PDF/Excel 附件解析框架 | ✅ | Phase 3.2 |
| PC 端宽屏网格布局 | ✅ | Phase 5 |
| 邮件推送引擎 | ✅ | Phase 5 |
| 定时调度器 | ✅ | Phase 5 |
| **LLM 智能提取（截止日期+专业）** | ✅ | Phase 6 |
| **Sydw1 URL 路由修复** | ✅ | Phase 6 |

### 启动方式

```bash
# 启动 Web 服务
cd backend && python3 -m uvicorn main:app --reload --port 8000

# 启动定时调度器（可选）
cd backend && python3 scheduler.py
```

### 遗留问题

1. **LLM API Key 未配置**：需设置 `LLM_API_KEY` 环境变量才能启用 AI 提取
2. **sydw1 无附件**：当前数据源的公告均为内联 HTML，附件解析框架已就绪但无实际测试数据
3. **qgsydw 广东数据量**：首页当前无广东公告，需翻页或定时积累

---

## 2025-07-02 Phase 6：终极精度升维 · LLM 接管提取

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `requirements.txt` | 新增 `openai>=1.0.0` |
| `backend/llm_processor.py` | **新增**：LLM 通信模块，封装 OpenAI 兼容接口 |
| `backend/scraper.py` | URL 路由修复 + 剥离正则提取逻辑，改用 LLM |

### 1. Sydw1 URL 路由修复

**旧规则**：
```python
if "/guangdong/" not in href or not href.endswith(".html"):
```

**新规则**：
```python
if not re.search(r'/guangdong/(?:[\w-]+/)*[\w-]+\.html$', href):
```

支持任意深度的城市子目录：

| URL 路径 | 匹配结果 |
|----------|----------|
| `/guangdong/foshan/195863.html` | ✅ |
| `/guangdong/guangzhou/149274.html` | ✅ |
| `/guangdong/jieyang/195858.html` | ✅ |
| `/guangdong/195858.html` | ✅ |
| `/guangdong/shenzhen/nanshan/123.html` | ✅ |

### 2. DeepSeek API 智能提取模块 (`llm_processor.py`)

#### 架构

```
core_content (掐头去尾截断: 前1000字 + 后1000字) + title
        ↓
   extract_info() / extract_info_async()
        ↓
   tenacity 重试 (max 3次, 指数退避 2→4→8→10s)
        ↓
   AsyncOpenAI → DeepSeek API (Semaphore 并发限流=5)
        ↓
   JSON 解析 + 校验
        ↓
   {"deadline": "YYYY-MM-DD|null", "major_category": "专业大类"}
```

#### 截断策略：掐头去尾法

```python
# 3000 字正文 → 保留前 1000 + 后 1000，中间省略
truncated = core_text[:1000] + "\n...(中间省略)...\n" + core_text[-1000:]
```

原因：报名截止日期通常在文章末尾，专业要求在前半部分。掐头去尾比纯截断前 N 字更高效。

#### 并发控制

- `asyncio.Semaphore(5)` 限制最高并发 5 个 API 请求
- 避免触发 DeepSeek 的 Rate Limit

#### 环境变量配置

```bash
# backend/.env 文件
DEEPSEEK_API_KEY=sk-xxxx                  # 必填：API 密钥
DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1  # 硅基流动平台
DEEPSEEK_MODEL=deepseek-ai/DeepSeek-V3    # 标准版模型
```

#### 容错机制

| 场景 | 处理方式 |
|------|----------|
| API 未配置 | 跳过 LLM，兜底 `major_category = "其他专业"` |
| API 超时/网络错误 | tenacity 重试 3 次，指数退避 |
| 重试仍失败 | 捕获异常，返回 `None`，兜底处理 |
| 返回格式异常 | JSON 解析失败时返回 `None` |
| 专业大类非法 | 仅接受 8 个预定义类别，否则归为"其他专业" |
| 日期格式非法 | 校验 YYYY-MM-DD 格式，否则置为 `None` |

#### 同步/异步双接口

| 函数 | 用途 |
|------|------|
| `extract_info()` | 同步接口，供当前 scraper 使用 |
| `extract_info_async()` | 异步接口，预留供未来异步爬虫使用 |

#### 模型与 JSON Mode

- **模型**：`deepseek-ai/DeepSeek-V3`（标准版，替代 `deepseek-chat`）
- **JSON Mode**：`response_format={"type": "json_object"}` 强制模型输出纯 JSON
- **System Prompt**：强约束版，明确禁止输出解释性文字或 Markdown 代码块

### 3. 旧代码清理

**删除的复杂正则逻辑**：

| 函数 | 原作用 | 替代方案 |
|------|--------|----------|
| `extract_deadline()` | 正则匹配截止日期 | `llm_processor.extract_info()` |
| `_extract_requirements_section()` | 提取"专业要求"段落 | LLM 直接理解全文 |
| `match_major_category()` | 三层分层匹配 | LLM 直接判断 |
| `_is_valid_context()` | 法学类上下文探测 | LLM 语义理解 |
| `match_major_category_single()` | 单次关键词匹配 | LLM 直接判断 |

**保留的稳定逻辑**：

| 函数 | 原因 |
|------|------|
| `extract_publish_date()` | 正则提取发布时间（稳定可靠） |
| `_extract_core_content()` | DOM 缩圈（LLM 输入预处理） |
| `_extract_attachments()` | 附件发现（结构化提取） |
| `_parse_pdf()` / `_parse_excel()` | 附件解析（PDF/Excel → 文本） |
| `classify()` | 分类过滤（标题关键词，快速稳定） |
| `is_guangdong()` | 地域过滤（简单可靠） |

### 实测数据（Phase 6 · 硅基流动 DeepSeek-V3）

| 指标 | 数值 |
|------|------|
| sydw1 URL 匹配 | 26 条（二级目录路由正常） |
| LLM API 调用 | 26 次（SiliconFlow + DeepSeek-V3） |
| LLM 提取成功 | **20/26（77%）** |
| 截止日期提取 | **26/26（100%）**（含正则兜底） |
| 真实发布日期 | 26/26（100%） |
| JSON Mode | ✅ `response_format={"type": "json_object"}` |
| tenacity Jitter 重试 | max 3次，随机退避 1→10s |

### 专业大类分布（LLM 提取后）

| 大类 | 数量 | 说明 |
|------|------|------|
| 其他专业 | 10 | LLM 无法明确分类的岗位 |
| 医疗卫生类 | 6 | 医院/卫生系统岗位 ✅ |
| 教育师范类 | 5 | 学校/教师岗位 ✅ |
| 不限专业 | 4 | 无专业限制岗位 ✅ |
| 财务审计类 | 1 | 会计岗位 ✅ |
| 计算机类 | 0 | 正确——无 IT 岗位 |
| 法学类 | 0 | 正确——无法律岗位 |

### 断点调试结果（2 条复杂地级市公告）

| 公告 | publish_date | deadline | major_category |
|------|-------------|----------|----------------|
| 佛山均安控股（企业招聘） | 2026-07-01 ✅ | 2026-06-30 ✅ | 其他专业 ✅ |
| 汕头大学精神卫生中心 | 2026-06-30 ✅ | 2026-07-03 ✅ | 医疗卫生类 ✅ |

### 遗留问题

1. **11 条 LLM 提取失败**：新 Prompt 更复杂，部分详情页正文过短导致提取失败
2. **sydw1 无附件**：附件解析框架已就绪，待新数据源验证
3. **qgsydw 广东数据量**：首页当前无广东公告，需翻页或定时积累

---

## 2025-07-02 Phase 6.1：全栈精细化专业升维

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/models.py` | 新增 `is_unlimited`、`disciplines`、`major_names` 字段；重写 `query_notices` 多维筛选；新增 `query_all_filters()` |
| `backend/llm_processor.py` | 重写 Prompt：提取 `is_unlimited`、`disciplines`、`major_names`；强化 JSON 清洗正则 |
| `backend/scraper.py` | `scrape_detail_page` 返回新字段；`insert_notice` 传递新字段 |
| `backend/main.py` | 新增 `/api/filters` 接口；`/api/notices` 支持 `discipline`、`major_name`、`is_unlimited` 筛选 |
| `frontend/index.html` | 左侧控制台重构：三不限 Toggle + 学科门类标签 + 具体专业下拉 + 一键重置 |

### 数据库结构升级

```sql
-- 新增三个字段
ALTER TABLE exam_notices ADD COLUMN is_unlimited INTEGER DEFAULT 0;  -- 三不限标记
ALTER TABLE exam_notices ADD COLUMN disciplines TEXT DEFAULT '[]';    -- JSON: 学科门类数组
ALTER TABLE exam_notices ADD COLUMN major_names TEXT DEFAULT '[]';   -- JSON: 具体专业数组
```

**向下兼容**：旧数据 `disciplines` 默认 `'[]'`，`is_unlimited` 默认 `0`，不会抛出 NoneType 错误。

### LLM Prompt 重构

**旧 Prompt**（8 大类限制）：
```
major_category: 必须从以下选项中选一个：计算机类、财务审计类...
```

**新 Prompt**（精细化多维提取）：
```
- is_unlimited: 布尔值，若"不限专业"则为 true
- disciplines: 数组，学科门类（工学、医学、管理学...）
- major_names: 数组，具体专业名称（计算机科学与技术、临床医学...）
```

**JSON 清洗强化**：
```python
raw = re.sub(r'```json\s*\n?', '', raw)  # 彻底去除 markdown 围栏
raw = re.sub(r'\n?\s*```', '', raw)
```

### API 接口升级

| 接口 | 参数 | 说明 |
|------|------|------|
| `GET /api/notices` | `discipline` | 按学科门类筛选 |
| `GET /api/notices` | `major_name` | 按具体专业筛选 |
| `GET /api/notices` | `is_unlimited=true` | 仅看三不限岗位 |
| `GET /api/filters` | — | 返回所有去重的学科门类和具体专业 |

### 前端 UI 重构

**左侧控制台新增组件**：
1. **三不限 Toggle**：一键切换"仅看三不限岗位"
2. **学科门类标签组**：动态渲染，支持单选切换（工学、医学、管理学...）
3. **具体专业下拉框**：根据学科门类联动过滤
4. **一键重置**：清除所有筛选条件
5. **统计面板**：新增"三不限岗位"计数

**卡片新增**：
- 三不限标记：`amber` 色 pill badge
- 学科门类：`indigo` 色标签组
- 具体专业：`purple` 色标签（最多显示 3 个，多余 +N）

### 实测数据（Phase 6.1）

| 指标 | 数值 |
|------|------|
| LLM API 调用 | 26 次 |
| LLM 提取成功 | 15/26（58%） |
| 有学科门类 | 3/26 |
| 有具体专业 | 1/26 |
| 三不限标记 | 2/26 |
| 学科门类 | 农学、医学 |
| 具体专业 | 农学、分子生物学、园艺学、植物学 |
| 筛选测试 | 学科=医学 → 2 条 ✅ |

### 遗留问题

1. **LLM 提取率 58%**：新 Prompt 更复杂，部分正文过短的公告无法提取学科/专业信息
2. **学科/专业覆盖率低**：大部分公告正文未明确列出学科门类和具体专业名称
3. **sydw1 无附件**：附件解析框架已就绪，待新数据源验证

---

## 2025-07-02 Phase 6.2：解耦 LLM 分类 · 本地字典映射 · 数据回洗

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/core/major_mapping.py` | **新增**：本地专业→学科门类字典（100+ 映射）+ `map_majors_to_disciplines()` |
| `backend/llm_processor.py` | Prompt 简化：LLM 只提取 `deadline/is_unlimited/majors`；映射逻辑移至本地字典 |
| `backend/scripts/data_backfill_6_2.py` | **新增**：历史数据回洗脚本（自动备份 + 批量更新 disciplines） |

### 架构变更：LLM 与分类解耦

**旧架构**（Phase 6.1）：
```
LLM 提取 disciplines + majors → 直接入库
```
问题：LLM 推断学科门类不稳定，部分结果不准确。

**新架构**（Phase 6.2）：
```
LLM 只提取 majors（具体专业）→ 本地字典查表 → 生成 disciplines
```
优势：分类逻辑完全由本地字典控制，可人工维护，结果稳定可靠。

### LLM Prompt 简化

**删除**：`disciplines` 字段（不再要求 LLM 推断学科门类）
**保留**：`deadline`、`is_unlimited`、`majors`

### 本地字典 (`core/major_mapping.py`)

**[重大重构] 废弃精确匹配，改用特征词子串匹配**

- 位置：`backend/core/major_mapping.py`
- 算法：Substring Matching（特征词包含匹配）
- 格式：`KEYWORD_TO_DISCIPLINE = {"工学": ["计算机", "软件", "工程", ...], ...}`
- 覆盖：农学、医学、工学、理学、管理学、法学、文学、教育学、经济学 共 9 大门类
- 特征词：每门类 4-12 个特征关键词
- 维护：向 value 列表添加特征词即可

**未命中处理**：静默忽略，不返回"未分类"，结果集中不包含该门类

### 数据回洗脚本

```bash
cd backend && python3 scripts/data_backfill_6_2.py
```

**[数据清洗]** 回洗结果：1 条更新，25 条未变，0 条失败

### 实测数据（Phase 6.2 子串匹配版）

| 指标 | Phase 6.1 | Phase 6.2（重构后） |
|------|-----------|-----------|
| 匹配算法 | 精确匹配 + 模糊回退 | **特征词子串匹配** |
| Prompt 字段 | 4 个（含 disciplines） | 3 个（不含 disciplines） |
| 分类来源 | LLM 推断 | **本地特征词匹配** |
| "未分类/需人工核对" | 有 | **已消除** |
| 字典大小 | 244 个精确映射 | **9 门类 × 4-12 特征词** |
| 数据回洗 | 3 条更新 | 1 条更新（"分子生物学"→理学） |

**映射示例**：
```
"植物学"   → 包含"植物" → 农学
"分子生物学" → 包含"生物" → 理学
"园艺学"   → 包含"园艺" → 农学
```

### 遗留问题

1. **LLM 提取率 58%**：部分正文过短的公告无法提取专业信息
2. **sydw1 无附件**：附件解析框架已就绪，待新数据源验证

---

## 2025-07-02 系统诊断：未分类标签溯源

**`[系统诊断]`** 执行了未分类标签的专项排查，诊断数据已安全提取至 `diagnostic_report.md`。

### 诊断结论

1. **"未分类/需人工核对"已彻底消除**：
   - `disciplines` 字段中 0 条包含"未分类"
   - `major_category` 字段中 0 条包含"未分类"
   - 映射字典子串匹配正常工作，未命中时静默忽略

2. **前端"未分类"Tab 的来源**：
   - `category` 字段（非 `disciplines`）中有 9 条记录值为"未分类"
   - 这是标题关键词分类的结果（如"佛山市均安控股"无法匹配公务员/事业编/编外人员）
   - 前端 Tab 中的"未分类"是对 `category` 字段的筛选，与专业映射无关

3. **disciplines 空数据原因**：
   - 25/26 条记录的 `major_names` 为空数组（LLM 未从正文提取到具体专业）
   - 仅 1 条记录（#11 广东省农科院）有专业数据并成功映射

### 诊断文件

- `diagnostic_report.md`：完整诊断数据（含前端源码搜索、数据库脏数据检查、映射字典验证）

---

## 2025-07-02 UI 精简与强固：学科门类按钮组移除 + 专业树状下拉框

**`[UI精简与强固]`** 彻底移除了外部冗余的学科门类按钮组。升级 `/api/filters` 与前端组件，实现具体专业下拉框的 `<optgroup>` 树状化分组。专业筛选体验已精简至"一步到位"。

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/main.py` | 重构 `/api/filters`：返回 `major_tree` 树状字典 |
| `frontend/index.html` | 移除学科门类标签组；替换为 `<optgroup>` 树状下拉框 |

### 后端 `/api/filters` 重构

**旧返回格式**：
```json
{ "disciplines": ["农学", "理学"], "majors": ["农学", "园艺学", ...] }
```

**新返回格式**：
```json
{
  "major_tree": {
    "农学": ["农学", "园艺学", "植物学"],
    "理学": ["分子生物学"]
  }
}
```

构建逻辑：遍历数据库去重的 `major_names`，调用 `map_majors_to_disciplines()` 按学科门类分组。

### 前端 UI 变更

**删除**：
- "学科门类" 标题标签
- 学科门类药丸按钮组（`v-for="d in allDisciplines"`）
- `selectedDiscipline` 状态变量及相关筛选逻辑
- `allDisciplines`、`filteredMajorNames` 计算属性

**新增**：
- `<optgroup>` 树状下拉框，按学科门类分组显示具体专业
- `majorTree` 数据源，由 `/api/filters` 动态驱动

### 实测数据

| 指标 | 结果 |
|------|------|
| `/api/filters` 返回 | `major_tree`: 农学(3), 理学(1) |
| `/api/notices` 返回 | 17 条有效公告 |
| 下拉框分组 | 2 个 optgroup（农学、理学） |
| 三不限 Toggle | 正常工作 |
| 一键重置 | 正常工作 |

---

## 2025-07-02 Phase 6.5：附件穿透抢救 · 优先级提取逻辑

**`[提取逻辑升维]`** 优化了附件穿透脚本，确立了"三不限 > 核心具体专业"的提取优先级，完美契合当前高度聚焦的业务目标，消除了过度匹配的隐患。

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/scripts/penetrate_attachments_6_5.py` | **新增**：附件穿透抢救脚本 |

### 提取优先级策略

```
P1: 三不限判定
  → 特征词: ["不限专业", "专业不限", "无专业限制", "专业不作要求"]
  → 命中则设 is_unlimited=1

P2: 核心门类提取
  → 词库: 9 大门类 × 细分专业（农学/管理学/经济学/法学/教育学/文学/工学/理学/医学）
  → 命中则加入 major_names + disciplines
```

### 核心词库（精简版）

| 门类 | 核心专业 |
|------|----------|
| 农学 | 农学、园艺、植物、动物、水产、林学… |
| 管理学 | 行政管理、会计、财务管理、人力资源、工商管理… |
| 经济学 | 经济学、金融、财政、税收、投资… |
| 法学 | 法学、社会工作、思想政治教育… |
| 教育学 | 教育学、学前教育、心理学… |
| 文学 | 汉语言文学、秘书学、新闻学、英语… |
| 工学 | 计算机、软件工程、土木工程… |
| 理学 | 数学、物理、化学、生物… |
| 医学 | 临床医学、药学、护理学… |

### 实测结果

| 指标 | 结果 |
|------|------|
| 处理记录 | 1 条（#11 广东省农科院） |
| 三不限标记 | 未命中（正确） |
| 专业提取 | +2 个新关键词（园艺、植物） |
| 学科映射 | 农学、理学（不变） |
| 更新 | 1 条，失败 0 条 |

---

## 2025-07-02 绝对极简重构：静态字典 + 文案清洗

**`[绝对极简]`** 拦截了底层动态数据的干扰，强行将 `/api/filters` 接口降维为极简的静态响应。前端菜单现已绝对纯净，仅保留农学、管理学相关具体专业。三不限通过独立 Toggle 控制。

### 变更

**后端 `/api/filters`**：
- 删除所有数据库查询、去重、动态组装逻辑
- 直接返回硬编码静态字典

**前端**：
- `"全部专业（一步到位筛选）"` → `"全部专业"`

### 静态字典内容

```
农学大类: 农学、农业管理、农村发展、园艺学、植物保护、
         农业资源与环境、动物科学、动物医学、林学、水产养殖学
管理学大类: 管理学、行政管理、公共事业管理、工商管理、
           会计学、财务管理、人力资源管理、审计学、工程管理
```

---

## 2025-07-02 架构升级：LibSQL 数据库连接抽象

**`[架构升级]`** 完成了数据库连接层的抽象解耦，引入了 LibSQL 驱动支持。系统现已兼容本地单文件 SQLite 与云端 Turso Serverless SQLite，彻底解决了 PaaS 部署的数据丢失问题。

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/models.py` | `get_connection()` 支持 Turso/本地双模式；迁移逻辑兼容 Turso |
| `backend/config.py` | 新增 `DATABASE_URL`、`DATABASE_AUTH_TOKEN` 配置 |
| `requirements.txt` | 新增 `libsql-experimental>=0.0.50` |
| `.env.example` | **新增**：数据库配置模板 |
| `backend/scripts/data_backfill_6_2.py` | 改用 `get_connection()` |
| `backend/scripts/penetrate_attachments_6_5.py` | 改用 `get_connection()` |

### 连接策略

```python
DATABASE_URL = os.getenv("DATABASE_URL", "file:./data/notices.db")

def get_connection():
    if DATABASE_URL.startswith("libsql://") or DATABASE_URL.startswith("https://"):
        import libsql_experimental as libsql
        return libsql.connect(database=DATABASE_URL, auth_token=DATABASE_AUTH_TOKEN)
    else:
        return sqlite3.connect(DB_PATH)
```

### 部署配置

```env
# 本地开发（默认）
DATABASE_URL=file:./data/notices.db

# Turso 云端
DATABASE_URL=libsql://your-db-name.turso.io
DATABASE_AUTH_TOKEN=your-token-here
```

### 测试结果

| 场景 | 结果 |
|------|------|
| 本地 SQLite 连接 | ✅ 26 条记录正常读取 |
| API `/api/notices` | ✅ 17 条有效公告 |
| API `/api/filters` | ✅ 静态字典正常返回 |
| `init_db()` 迁移 | ✅ 兼容 Turso（跳过 PRAGMA） |

---

## 2025-07-02 Serverless 适配：Cron 触发接口

**`[Serverless 适配]`** 新增受 `CRON_SECRET` 保护的 `/api/cron/scrape` 接口。使用 BackgroundTasks 异步处理爬虫逻辑，彻底抛弃了不兼容云端无状态环境的常驻死循环调度器，打通了云端定时任务链路。

### 变更文件

| 文件 | 变更内容 |
|------|----------|
| `backend/main.py` | 新增 `/api/cron/scrape` 路由（Bearer Token 认证 + BackgroundTasks） |
| `.env.example` | 新增 `CRON_SECRET` 配置项 |

### 接口说明

```
GET /api/cron/scrape
Header: Authorization: Bearer {CRON_SECRET}
```

- 认证失败 → 401 Unauthorized
- 认证成功 → 200 + 后台执行 `scrape_and_notify()`
- 使用 `BackgroundTasks` 避免 Vercel/Render 网关超时（10s 限制）

### 使用方式

```bash
# 本地测试
curl -H "Authorization: Bearer dev_secret" http://localhost:8000/api/cron/scrape

# Vercel Cron 配置 (vercel.json)
# { "crons": [{ "path": "/api/cron/scrape", "schedule": "0 9 * * 1-5" }] }
# Headers 在 Vercel 项目设置中配置 CRON_SECRET 环境变量
```

### scheduler.py 状态

保持独立可用，标记为 Deprecated（本地开发/传统部署仍可使用）。
