# Langchain Agent - 高校教师信息搜集系统

基于 LangChain 的多 Agent 协作系统，用于高效搜集和整理高校教师信息。

## 项目结构

```
langchain_agent/
├── langchain_skillTest.py      # 核心 Agent 和工具定义
├── LangchainAgent_test.py      # 测试和运行脚本
└── README.md
```

## 核心组件

### 三大 Agent

| Agent | 功能描述 |
|-------|----------|
| `WebDiscovery_agent` | 学校网站发现 Agent - 根据关键词搜索学校及其官网 URL |
| `WebScraping_agent` | 网页爬取 Agent - 深度遍历学校网站，发现院系、师资栏目，提取教师信息 |
| `CleanTeacherProfiles_agent` | 教师信息清洗 Agent - 筛选和清洗教师数据 |

### 核心工具

| 工具名称 | 功能描述 |
|----------|----------|
| `search_universities` | 从本地数据库搜索高校信息（支持关键词筛选） |
| `discover_all_departments` | 发现学校所有院系链接 |
| `find_faculty_column` | 智能定位院系的师资队伍栏目 |
| `extract_all_teacher_profiles` | 提取并筛选教师个人页面信息 |
| `clean_teacher_profiles` | 清洗和过滤教师数据 |

## 工作流程

```
用户查询
    ↓
[WebDiscovery_agent] 发现目标学校及官网 URL
    ↓
[WebScraping_agent] 深度遍历
    ├── discover_all_departments → 获取所有院系链接
    ├── find_faculty_column → 定位师资栏目
    ├── extract_all_teacher_profiles → 提取教师信息
    └── get_teachers_with_name_from_buffer → 获取筛选后的数据
    ↓
[CleanTeacherProfiles_agent] 数据清洗与筛选
    ↓
最终报告
```

## 环境要求

- Python 3.8+
- LangChain
- LangChain OpenAI
- BeautifulSoup4
- Requests
- Selenium (可选，用于 JavaScript 渲染页面)
- Chrome WebDriver (配合 Selenium 使用)

## 配置

项目支持两种 LLM 后端：

### 本地模型 (Ollama)

```python
model = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="",
    model="qwen3:4b",
    temperature=0.7,
)
```

### 远程 API (DeepSeek)

```python
model = ChatOpenAI(
    api_key="your-api-key",
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat"
)
```

## 使用方法

### 命令行运行

```bash
# 运行 WebDiscovery Agent
python LangchainAgent_test.py --agent webdiscovery

# 运行 WebScraping Agent
python LangchainAgent_test.py --agent webscraping

# 运行 CleanTeacherProfiles Agent
python LangchainAgent_test.py --agent cleanteacherprofiles
```

### 代码调用

```python
from langchain_skillTest import WebDiscovery_agent, WebScraping_agent, CleanTeacherProfiles_agent

# 发现学校
result = WebDiscovery_agent.invoke({
    "messages": [{"role": "user", "content": "深圳的学校"}]
})

# 爬取教师信息 (流式输出)
for chunk in WebScraping_agent.stream({
    "messages": [{"role": "user", "content": "深圳市具有院士头衔的老师信息"}]
}):
    print(chunk)

# 清洗数据
result = CleanTeacherProfiles_agent.invoke({
    "messages": [{"role": "user", "content": "找具有院士头衔的老师信息"}]
})
```

## 数据存储

- `data/buffer/data.json` - 中间缓存数据
- `data/buffer/teacher_profiles.json` - 教师信息最终数据
- `data/{school_name}/{department_name}.json` - 按学校分类存储

## 智能特性

### 师资栏目智能定位

`find_faculty_column` 工具采用多策略定位：

1. **显式链接搜索** - 扫描页面中包含"师资队伍"、"Faculty"等关键词的链接
2. **URL 猜测 (同级)** - 尝试替换 URL 末尾文件名为常见师资页面名
3. **URL 猜测 (子目录)** - 尝试在当前 URL 后追加常见师资页面名
4. **有效性验证** - 对所有猜测的 URL 进行 HTTP 验证

### 教师页面智能识别

使用 LLM 判断页面是否为教师个人介绍页，并提取：
- 姓名 (name)
- 职称 (title)
- 邮箱 (email)
- 电话 (phone)
- 研究方向 (research_interests)
- 所属院系 (department)
- 荣誉头衔 (hats)

## 注意事项

1. 爬取前请确保遵守目标网站的 `robots.txt` 规则
2. 建议在请求间添加适当延迟，避免对目标服务器造成压力
3. 部分网站可能需要 Selenium 处理 JavaScript 渲染
4. API Key 请妥善保管，不要提交到版本控制系统

🌟 支持项目

如果这个项目对你有帮助，欢迎点击仓库右上角的 Star ⭐ 支持一下！你的鼓励是我持续优化和维护项目的最大动力～
📄 免责声明
本项目仅用于学习和研究目的，请勿用于商业或非法用途
使用本项目爬取数据时，需遵守目标网站的用户协议和相关法律法规
开发者不对因使用本项目产生的任何法律责任负责

🤝 贡献指南

如果你发现 Bug、有新功能建议，欢迎：
Fork 本仓库
创建特性分支 (git checkout -b feature/AmazingFeature)
提交修改 (git commit -m 'Add some AmazingFeature')
推送到分支 (git push origin feature/AmazingFeature)
打开 Pull Request

📧 联系作者

如有问题或交流需求，可通过 GitHub Issues 留言，我会尽快回复。
