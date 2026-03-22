# Langchain Agent - 高校教师信息搜集系统

基于 LangChain 的多 Agent 协作系统，可自动化发现高校官网、定位师资栏目、爬取并清洗教师信息，支持本地 LLM（Ollama）和远程 API（DeepSeek）双后端。

## 📋 项目概览
- **核心能力**：从「学校搜索」到「教师信息清洗」全流程自动化
- **智能特性**：多策略定位师资栏目、LLM 驱动的教师页面识别与信息提取
- **数据存储**：结构化缓存 + 按学校/院系分类存储，便于后续分析

## 📂 项目结构

```
langchain_agent/
├── langchain_skillTest.py      # 核心 Agent 和工具定义
├── LangchainAgent_test.py      # 测试和运行脚本
└── README.md
```

## 🎯 核心组件

### 三大核心 Agent
| Agent | 功能描述 |
|-------|----------|
| `WebDiscovery_agent` | 学校网站发现 Agent - 根据关键词（地域/名称）从本地数据库搜索高校，返回带官网URL的结果 |
| `WebScraping_agent` | 网页爬取 Agent - 深度遍历学校官网，自动发现院系、定位师资栏目、提取教师个人页面信息 |
| `CleanTeacherProfiles_agent` | 教师信息清洗 Agent - 基于 LLM 筛选有效教师页面，提取姓名/职称/研究方向等结构化信息 |

### 核心工具函数
| 工具名称 | 功能描述 |
|----------|----------|
| `search_universities` | 从本地高校数据库筛选学校（支持关键词，自动过滤无官网的学校） |
| `discover_all_departments` | 从学校主页提取所有院系名称和URL（去重 + 域名校验） |
| `find_faculty_column` | 多策略定位院系「师资队伍」栏目（显式链接搜索 + URL 智能猜测） |
| `extract_all_teacher_profiles` | 从师资列表页提取教师个人页面链接，调用 LLM 识别有效信息 |
| `clean_teacher_profiles` | 清洗教师数据，保留有效信息并结构化存储 |

## 🔄 工作流程

```
用户输入查询（如："深圳的院士教师信息"）
    ↓
[WebDiscovery_agent] 搜索符合条件的学校及官网 URL
    ↓
[WebScraping_agent] 深度遍历学校官网
    ├── discover_all_departments → 获取所有院系链接
    ├── find_faculty_column → 定位各院系师资栏目
    ├── extract_all_teacher_profiles → 提取教师个人页面信息
    └── get_teachers_with_name_from_buffer → 筛选含姓名的原始数据
    ↓
[CleanTeacherProfiles_agent] 数据清洗与结构化
    ├── LLM 判定页面是否为教师个人页
    ├── 提取姓名/职称/邮箱/研究方向等字段
    ├── 过滤无效数据并保存
    ↓
生成最终结构化教师信息报告
```

## 🛠️ 环境准备

### 1. 基础环境
- Python 3.8+
- 依赖安装：
  ```bash
  pip install langchain langchain-openai beautifulsoup4 requests selenium
  ```

### 2. 可选依赖（按需安装）
- **Ollama**：本地运行 LLM（推荐），需安装 [Ollama](https://ollama.com/) 并拉取模型（如 `ollama pull qwen3:4b`）
- **Chrome WebDriver**：处理 JavaScript 渲染的页面（需与本地 Chrome 版本匹配）

## ⚙️ 核心配置

### 1. LLM 后端配置（二选一）
#### 本地模型（Ollama，推荐）
修改 `langchain_skillTest.py` 中模型配置：
```python
local_llm = True  # 启用本地模型
model = ChatOpenAI(
    base_url="http://localhost:11434/v1",  # Ollama 默认端口
    api_key="",                            # 本地模型无需填写
    model="qwen3:4b",                      # 替换为你拉取的模型名（如 qwen2:7b）
    temperature=0.7,
)
```

#### 远程 API（DeepSeek）
```python
local_llm = False  # 禁用本地模型
model = ChatOpenAI(
    api_key="your-deepseek-api-key",       # 替换为你的 DeepSeek API 密钥
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat"
)
```

### 2. 关键路径修改
代码中硬编码的绝对路径需改为**相对路径**（避免环境适配问题）：
```python
# 替换 langchain_skillTest.py 中的路径配置
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUFFER_FILE_PATH = os.path.join(BASE_DIR, "data", "buffer", "data.json")
TEACHER_PROFILES_BUFFER_FILE_PATH = os.path.join(BASE_DIR, "data", "buffer", "teacher_profiles.json")

# 替换 langchain_skillTest.py 中第263、264的缓存的路径
BUFFER_FILE_PATH = r"F:\My_Project\skillCreator_System\data\buffer\data.json"
TEACHER_PROFILES_BUFFER_FILE_PATH = r"F:\My_Project\skillCreator_System\data\buffer\teacher_profiles.json"
```

### 3. 高校数据库准备
将 `china_schools_full_info.json` 放到项目根目录（包含学校名称/省份/城市/官网URL），否则 `search_universities` 工具无法正常工作。

## 🚀 使用方法

### 1. 命令行运行（推荐测试用）
```bash
# 1. 运行学校发现 Agent
python LangchainAgent_test.py --agent webdiscovery --query "深圳的985高校"

# 2. 运行网页爬取 Agent（核心）
python LangchainAgent_test.py --agent webscraping --query "深圳市具有院士头衔的老师信息"

# 3. 运行数据清洗 Agent
python LangchainAgent_test.py --agent cleanteacherprofiles --query "院士头衔"
```

### 2. 代码调用（灵活扩展）
```python
from langchain_skillTest import WebDiscovery_agent, WebScraping_agent, CleanTeacherProfiles_agent

# 1. 发现目标学校
discovery_result = WebDiscovery_agent.invoke({
    "messages": [{"role": "user", "content": "深圳的本科院校"}]
})
print("发现的学校：", discovery_result)

# 2. 爬取教师信息（流式输出，实时查看进度）
print("\n开始爬取教师信息...")
for chunk in WebScraping_agent.stream({
    "messages": [{"role": "user", "content": "深圳大学 计算机学院 教授信息"}]
}):
    print(chunk)

# 3. 清洗数据并提取结构化信息
clean_result = CleanTeacherProfiles_agent.invoke({
    "messages": [{"role": "user", "content": "筛选深圳大学计算机学院教授"}]
})
print("\n清洗后的教师信息：", clean_result)
```

## 💾 数据存储说明
| 文件路径 | 数据内容 | 用途 |
|----------|----------|------|
| `data/buffer/data.json` | 院系URL、师资栏目URL、爬取日志 | 中间缓存，便于断点续爬 |
| `data/buffer/teacher_profiles.json` | 清洗后的教师结构化信息 | 最终结果，可直接分析 |
| `data/{school_name}/{department_name}.json` | 按学校/院系分类的教师数据 | 分类存储，便于管理 |

## ✨ 智能特性

### 1. 师资栏目智能定位
`find_faculty_column` 工具采用4层策略，大幅提升定位成功率：
1. **显式链接搜索**：扫描含「师资队伍」「Faculty」等关键词的链接
2. **URL 同级猜测**：替换 URL 末尾文件名（如 `about.html` → `szdw.htm`）
3. **URL 子目录猜测**：在当前 URL 后追加常见师资页面名
4. **有效性验证**：对猜测的 URL 进行 HTTP 验证，确保可访问

### 2. 教师页面智能识别
基于 LLM 精准判断页面类型，提取核心字段：
- 自动过滤非教师页面（如新闻、公告、院系简介）
- 提取姓名/职称/邮箱/电话/研究方向/所属院系/荣誉头衔
- 支持关键词筛选（如「院士」「教授」「博导」）

## ⚠️ 注意事项
1. 爬取前请检查目标网站的 `robots.txt` 规则，遵守爬虫礼仪
2. 建议在代码中添加请求延迟（如 `time.sleep(1)`），避免给目标服务器造成压力
3. Selenium 仅用于处理 JavaScript 渲染的页面，普通页面无需启用
4. API Key/敏感配置请勿提交到版本控制系统（可使用 `.env` 文件管理）
5. 本地高校数据库 `china_schools_full_info.json` 需确保包含「school_name」「official_website」等核心字段

## ❓ 常见问题
### Q1: 运行时提示「文件找不到」？
A1: 检查路径配置是否改为相对路径，确保 `data/buffer` 目录已创建（代码会自动创建，若失败可手动创建）。

### Q2: LLM 调用失败？
A2: 
- 本地 Ollama：确认 Ollama 服务已启动（`ollama serve`），模型已拉取
- DeepSeek API：确认 API Key 有效，网络可访问 DeepSeek 接口

### Q3: 爬取不到教师信息？
A3: 
- 检查目标学校官网是否有公开的师资栏目
- 确认 `find_faculty_column` 工具的关键词是否覆盖目标网站的栏目名称（可自定义补充）

## 🌟 支持项目
如果这个项目对你有帮助，欢迎点击仓库右上角的 Star ⭐ 支持一下！你的鼓励是我持续优化和维护项目的最大动力～

## 📄 免责声明
1. 本项目仅用于**学习和研究目的**，请勿用于商业或非法用途
2. 使用本项目爬取数据时，需遵守目标网站的用户协议和相关法律法规
3. 开发者不对因使用本项目产生的任何法律责任负责

## 🤝 贡献指南
1. Fork 本仓库
2. 创建特性分支（`git checkout -b feature/AmazingFeature`）
3. 提交修改（`git commit -m 'Add some AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 打开 Pull Request

## 📧 联系作者
如有问题或交流需求，可通过 GitHub Issues 留言，我会尽快回复。
