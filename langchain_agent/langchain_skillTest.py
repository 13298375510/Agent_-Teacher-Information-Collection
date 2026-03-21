"""
Personal Assistant Supervisor Example

This example demonstrates the tool calling pattern for multi-agent systems.
A supervisor agent coordinates specialized sub-agents (calendar and email)
that are wrapped as tools.
"""

import time
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
import os
import json
import re
from typing import List, Dict
# ============================================================================
# Step 1: Define low-level API tools (stubbed)
# ============================================================================
@tool
def search_universities(query: str, max_results: int = 20) -> str:
    """
    Search for universities in the local database by keywords (name, province, city).
    Automatic filtering:
    1. Only returns schools that match ALL keywords in the query.
    2. Automatically excludes schools that do not have a valid 'official_website'.
    
    Args:
        query: Search keywords separated by spaces (e.g., "Beijing 985" or "四川大学").
               If query is empty, returns the first batch of valid universities.
        max_results: Limit the number of returned items to save context window.
        
    Returns:
        JSON string containing 'count' and 'items'.
    """
    # 1. 确定文件路径 (使用之前生成的文件名)
    filename = "china_schools_full_info.json"
    if not os.path.isabs(filename):
        base = os.path.abspath(os.path.dirname(__file__))
        file_path = os.path.join(base, filename)
    else:
        file_path = filename

    # 2. 安全加载数据
    if not os.path.exists(file_path):
        return json.dumps({
            "error": f"Database file '{filename}' not found. Please run the crawler first.",
            "items": []
        }, ensure_ascii=False)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_schools = json.load(f)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON format in database.", "items": []})

    # 3. 预处理查询关键词
    # 将 "北京 科技" 拆分为 ["北京", "科技"]
    keywords = [k.lower() for k in re.split(r"[\s,，]+", query.strip()) if k]

    results = []
    
    for school in all_schools:
        # 提取关键字段
        s_name = school.get("school_name", "")
        s_prov = school.get("province", "")
        s_city = school.get("city", "")
        s_url = school.get("official_website", "")

        # 4. 核心过滤逻辑
        # 规则 A: 必须有官网 URL，且不是 "暂无官网数据"
        if not s_url or "暂无" in s_url or s_url == "":
            continue

        # 规则 B: 关键词匹配 (如果关键词列表为空，默认匹配所有有URL的学校)
        # 构造一个搜索文本池
        search_text = f"{s_name} {s_prov} {s_city}".lower()
        
        if not keywords or all(k in search_text for k in keywords):
            # 仅返回 Agent 需要的核心字段，减少 Token 消耗
            results.append({
                "name": s_name,
                "province": s_prov,
                "city": s_city,
                "url": s_url
            })

        if len(results) >= max_results:
            break

    # 5. 返回结果
    return json.dumps({
        "query": query,
        "total_found": len(results),
        "items": results
    }, ensure_ascii=False, indent=2)

@tool
def ensure_university_url(school_id: int) -> str:#用于检索没有url的学校信息，这里暂时不用
    """Fetch official site for a university by id via EOL API; returns {id, site}."""
    api = "https://api.eol.cn/web/api/"
    payload = {"access_token": "", "uri": "apidata/api/gk/school/info", "signsafe": "", "id": int(school_id)}
    try:
        import requests
        r = requests.post(api, json=payload, timeout=12)
        d = r.json()
        info = d.get("data") or {}
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except Exception:
                info = {}
        info = info.get("info") or info
        site = info.get("site") or info.get("school_site") or info.get("website")
        return json.dumps({"id": school_id, "site": site}, ensure_ascii=False)
    except Exception:
        return json.dumps({"id": school_id, "site": None}, ensure_ascii=False)


import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 模拟装饰器，实际使用时请替换为你所使用的框架（如 LangChain, LlamaIndex 等）的装饰器
def tool(func):
    return func

# 通用请求头，防止被简单反爬
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def _fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get(url, timeout=12, allow_redirects=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        try:
            if url.startswith("https://"):
                u = "http://" + url[len("https://"):]
                r = requests.get(u, headers=HEADERS, timeout=12, allow_redirects=True)
                r.raise_for_status()
                r.encoding = r.apparent_encoding
                return BeautifulSoup(r.text, "html.parser")
        except Exception:
            return None
    return None

def _fetch_page_selenium(url: str) -> Optional[BeautifulSoup]:
    """
    Fetches a page using Selenium to handle JavaScript rendering.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        # Wait for the page to be fully loaded, you might need to adjust the condition
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        page_source = driver.page_source
        driver.quit()
        return BeautifulSoup(page_source, "html.parser")
    except Exception as e:
        print(f"Error fetching page with Selenium: {e}")
        return None

def _url_ok(url: str) -> bool:
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.head(url, timeout=8, allow_redirects=True)
        if r.status_code < 400:
            return True
    except Exception:
        pass
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if r.status_code < 400 and r.text:
            return True
    except Exception:
        try:
            if url.startswith("https://"):
                u = "http://" + url[len("https://"):]
                r = requests.get(u, headers=HEADERS, timeout=8, allow_redirects=True)
                if r.status_code < 400 and r.text:
                    return True
        except Exception:
            pass
    return False

def _canonicalize(url: str) -> str:
    from urllib.parse import urlparse, urlunparse
    p = urlparse(url)
    path = p.path.rstrip('/') or '/'
    return urlunparse((p.scheme or 'http', (p.netloc or '').lower(), path, '', '', ''))

def _same_domain(url: str, base_netloc: str) -> bool:
    from urllib.parse import urlparse
    return (urlparse(url).netloc or '').lower().endswith(base_netloc.lower())


BUFFER_FILE = "data/buffer/data.json"

def _save_to_central_buffer(record: Dict):
    """
    Appends a single record to the central JSON list.
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(BUFFER_FILE), exist_ok=True)
    
    data = []
    # 读取现有数据
    if os.path.exists(BUFFER_FILE):
        try:
            with open(BUFFER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list): data = []
        except:
            data = []
            
    data.append(record)
    
    # 写入
    with open(BUFFER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def _is_url_in_buffer(target_url: str) -> bool:
    """
    Simple deduplication check.
    Reads the buffer file to see if the URL exists.
    """
    if not os.path.exists(BUFFER_FILE):
        return False
        
    try:
        with open(BUFFER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get("profile_url") == target_url:
                    return True
    except:
        return False
    return False

# 定义常量路径
BUFFER_FILE_PATH = r"F:\My_Project\skillCreator_System\data\buffer\data.json"
TEACHER_PROFILES_BUFFER_FILE_PATH = r"F:\My_Project\skillCreator_System\data\buffer\teacher_profiles.json"

'''def _fetch_page(url):
    # 简易的 fetch 函数，如果你外部已经定义了可以忽略这个
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding
        return BeautifulSoup(resp.text, 'html.parser')
    except:
        return None'''

def _append_to_json_buffer(data: dict,BUFFER_FILE_PATH=BUFFER_FILE_PATH):
    """内部辅助函数：将数据追加到指定的 JSON 文件中"""
    # 1. 确保目录存在
    os.makedirs(os.path.dirname(BUFFER_FILE_PATH), exist_ok=True)
    
    file_content = []
    
    # 2. 尝试读取现有文件
    if os.path.exists(BUFFER_FILE_PATH):
        try:
            with open(BUFFER_FILE_PATH, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, list):
                    file_content = content
        except json.JSONDecodeError:
            pass # 如果文件损坏，就覆盖重写
            
    # 3. 追加新数据
    file_content.append(data)
    
    # 4. 写入文件
    with open(BUFFER_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(file_content, f, ensure_ascii=False, indent=4)

def _append_to_teacher_buffer(data: dict):
    """内部辅助函数：将单个教师的数据追加到教师信息JSON 文件中"""
    # 1. 确保目录存在
    os.makedirs(os.path.dirname(TEACHER_PROFILES_BUFFER_FILE_PATH), exist_ok=True)
    
    file_content = []
    
    # 2. 尝试读取现有文件
    if os.path.exists(TEACHER_PROFILES_BUFFER_FILE_PATH):
        try:
            with open(TEACHER_PROFILES_BUFFER_FILE_PATH, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, list):
                    file_content = content
        except json.JSONDecodeError:
            pass # 如果文件损坏，就覆盖重写
            
    # 3. 追加新数据
    file_content.append(data)
    
    # 4. 写入文件
    with open(TEACHER_PROFILES_BUFFER_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(file_content, f, ensure_ascii=False, indent=4)
# ============================================================================
# Create specialized tools
# ============================================================================
@tool
def find_department_list_page(university_url: str) -> str:
    """
    Access the university homepage to find the list of schools/departments.
    Returns a list of departments with their names and URLs.
    
    Args:
        university_url: The official URL of the university.
    """
    print(f"LOG: Searching for departments in {university_url}...")
    soup = _fetch_page(university_url)
    if not soup:
        return json.dumps([], ensure_ascii=False)

    departments = []
    # 常见的院系设置关键词
    keywords = ["院系", "机构", "教学", "学院", "Schools", "Departments", "Academics"]
    
    # 1. 尝试寻找包含关键词的导航入口链接
    target_link = None
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        if any(k in text for k in keywords):
            target_link = urljoin(university_url, a['href'])
            break
    
    # 如果找到了“院系设置”的总入口，进去爬取所有学院
    if target_link:
        print(f"LOG: Found department index page: {target_link}")
        sub_soup = _fetch_page(target_link)
        if sub_soup:
            # 这里的逻辑比较宽泛，通常学院列表会在一个特定的 div 或 list 中
            # 简单策略：抓取页面上所有含有“学院”、“系”、“School”字样的链接
            for a in sub_soup.find_all('a', href=True):
                name = a.get_text(strip=True)
                if len(name) > 2 and ("学院" in name or "系" in name or "School" in name):
                    full_url = urljoin(target_link, a['href'])
                    departments.append({"name": name, "url": full_url})
    
    # 去重
    seen = set()
    unique_depts = []
    for d in departments:
        if d['url'] not in seen:
            seen.add(d['url'])
            unique_depts.append(d)
            
    return json.dumps(unique_depts, ensure_ascii=False)

@tool
def discover_all_departments(university_url: str) -> str:
    """
    Discover and return all department/college URLs from a university homepage.
    It scans navigation links, follows candidate "院系设置/学院" entries,
    aggregates names+urls for pages containing 学院/系/School/College keywords, and deduplicates.
    Returns a JSON string: {"count": N, "items": [{"name": "...", "url": "..."}]}.
    """
    soup = _fetch_page(university_url)
    if not soup:
        return json.dumps({"count": 0, "items": []}, ensure_ascii=False)
    keywords = ["院系设置", "机构设置", "教学单位", "学院"]
    from urllib.parse import urlparse
    base_netloc = (urlparse(university_url).netloc or '').lower()
    seeds = []
    for a in soup.find_all('a', href=True):
        t = a.get_text(strip=True)
        h = urljoin(university_url, a['href'])
        if any(k in t for k in keywords):
            seeds.append(h)
        if any(s in a['href'] for s in ["/xy", "xueyuan", "college", "/xueyuan"]):
            seeds.append(h)
    departments = []
    
    # 直接遍历种子入口，不再进行广度优先搜索
    for seed_url in set(seeds): # 使用set去重
        if not _same_domain(seed_url, base_netloc):
            continue
        
        sub = _fetch_page(seed_url)
        if not sub:
            continue
        
        # 在入口页面内查找所有学院链接
        for a in sub.find_all('a', href=True):
            name = a.get_text(strip=True)
            href = urljoin(seed_url, a['href'])
            if not _same_domain(href, base_netloc):
                continue
            if len(name) > 1 and (name.endswith("学院") or name.endswith("系") or name.endswith("School") or name.endswith("College")):
                if _url_ok(href):
                    departments.append({"name": name, "url": href})
    
    dedup = []
    ds = set()
    for d in departments:
        u = d.get('url')
        if u and u not in ds:
            ds.add(u)
            dedup.append(d)
    return json.dumps({"count": len(dedup), "items": dedup}, ensure_ascii=False)

@tool
def find_faculty_column(department_url: str) -> str:
    """
    Finds the faculty/staff list URL using a multi-strategy approach.

    Strategies:
    1.  **Explicit Link Search**: Scans the page for `<a>` tags with keywords like '师资队伍', 'Faculty', etc.
    2.  **URL Guessing (Peer-Level)**: If no link is found, it tries replacing the last part of the URL
        (e.g., `about.html`) with common faculty page names (`szdw.htm`, `faculty.html`).
    3.  **URL Guessing (Sub-Directory)**: It also tries appending common faculty page names to the current URL.
    4.  **Validation**: Every guessed URL is actively checked with a HEAD request to ensure it exists before returning.

    Args:
        department_url: The URL of the department's main page.

    Returns:
        The validated URL of the faculty list page, or an empty string if all strategies fail.
    """
    print(f"LOG: Smart-searching for faculty column in {department_url}...")
    
    # --- Strategy 1: Explicit Link Search ---
    soup = _fetch_page(department_url)
    if soup:
        keywords = ["师资队伍", "教师名录", "专任教师", "全职教师", "教授", "Faculty", "People", "Staff", "师资", "导师"]
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if any(k == text for k in keywords) or any(k in text for k in keywords):
                href = a['href'].strip()
                
                # Normalize and validate the found URL
                if href.startswith('http://') or href.startswith('https://'):
                    full_url = href
                else:
                    cleaned_href = href.lstrip('/')
                    cleaned_href = re.sub(r'^(?:(?:\.\.|\.)[\\\\/]+)+', '', cleaned_href)
                    full_url = urljoin(department_url, cleaned_href)

                if _url_ok(full_url):
                    print(f"LOG: Strategy 1 (Explicit Link) found and validated: {full_url}")
                    # --- Save to buffer ---
                    log_data = {
                        "type": "faculty_column_found",
                        "strategy": "Explicit Link",
                        "source_department_url": department_url,
                        "found_faculty_url": full_url,
                        "link_text": text,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    try:
                        _append_to_json_buffer(log_data)
                    except Exception as e:
                        print(f"LOG: Warning - Failed to save buffer: {e}")
                    return full_url

        print("LOG: Strategy 1 failed. Proceeding to URL guessing strategies.")

        # --- Strategies 2 & 3: URL Guessing ---
        common_filenames = ["szdw.htm", "faculty.html", "teachers.html", "szdw.html", "faculty.htm", "list.html"]
        
        # Strategy 2: Peer-level replacement (e.g., .../about.html -> .../szdw.htm)
        base_url_parts = department_url.split('/')
        if '.' in base_url_parts[-1]: # Check if the last part is a file
            base_url_peer = '/'.join(base_url_parts[:-1]) + '/'
            for filename in common_filenames:
                guess_url = urljoin(base_url_peer, filename)
                if _url_ok(guess_url):
                    print(f"LOG: Strategy 2 (Peer-Level Guess) found and validated: {guess_url}")
                    # --- Save to buffer ---
                    log_data = {
                        "type": "faculty_column_found",
                        "strategy": "Peer-Level Guess",
                        "source_department_url": department_url,
                        "found_faculty_url": guess_url,
                        "link_text": f"Guessed: {filename}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    try:
                        _append_to_json_buffer(log_data)
                    except Exception as e:
                        print(f"LOG: Warning - Failed to save buffer: {e}")
                    return guess_url

        # Strategy 3: Sub-directory append (e.g., .../department/ -> .../department/szdw.htm)
        for filename in common_filenames:
            guess_url = urljoin(department_url + ('/' if not department_url.endswith('/') else ''), filename)
            if _url_ok(guess_url):
                print(f"LOG: Strategy 3 (Sub-Directory Guess) found and validated: {guess_url}")
                # --- Save to buffer ---
                log_data = {
                    "type": "faculty_column_found",
                    "strategy": "Sub-Directory Guess",
                    "source_department_url": department_url,
                    "found_faculty_url": guess_url,
                    "link_text": f"Guessed: {filename}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                try:
                    _append_to_json_buffer(log_data)
                except Exception as e:
                    print(f"LOG: Warning - Failed to save buffer: {e}")
                return guess_url
                
        print(f"LOG: All strategies failed for {department_url}.")
    return ""


@tool
def extract_all_teacher_profiles(faculty_list_url: str, query: str) -> str:
    '''
    Extracts all teacher profiles from a given faculty list URL.

    This tool scrapes the provided URL, calls a selector function to determine if a 
    link is a valid teacher profile, and if so, saves the returned information.

    Args:
        faculty_list_url: The URL of the faculty list page to scrape.
        query: The query string to filter teacher profiles.
    Returns:
        A JSON string representing a list of extracted teacher information.
    '''
    print(f"LOG: Starting to extract teacher profiles from {faculty_list_url}...")
    soup = _fetch_page(faculty_list_url)
    if not soup:
        print("LOG: Failed to fetch the page.")
        return json.dumps([], ensure_ascii=False)

    profiles = []
    main_content = soup.find('div', class_=['content', 'main', 'container', 'list']) or soup
    exclude_words = ["更多", "首页", "下一页", "上一页", "Next", "Prev", "Home", "关于", "联系"]
    
    # 使用集合来避免重复处理同一个URL
    processed_urls = set()

    for a in main_content.find_all('a', href=True):
        href = a['href']
        if not href or href.startswith('#'):
            continue
        
        detail_url = urljoin(faculty_list_url, href)
        if detail_url in processed_urls:
            continue
        processed_urls.add(detail_url)

        name = a.get_text(strip=True)
        if not name or any(w in name for w in exclude_words) or len(name) <= 1 or len(name) >= 30:
            continue

        # 调用 select_teacher_profiles 进行判断
        r = select_teacher_profiles(detail_url,query)
        # 核心逻辑：根据您的最新要求，只要 "keep" 为 true，就保存除 "keep" 之外的所有信息
        if r.get("keep") is True:
            # 复制字典，准备保存
            data_to_save = r.copy()
            
            # 移除 'keep' 键
            del data_to_save['keep']
            
            # 确保 profile_url 存在
            data_to_save['profile_url'] = detail_url

            # 追加到结果列表和缓冲区
            if data_to_save not in profiles:
                profiles.append(data_to_save)
                try:
                    _append_to_teacher_buffer(data_to_save)
                except Exception as e:
                    print(f"LOG: Warning - Failed to save buffer: {e}")

    print(f"LOG: Extracted {len(profiles)} structured teacher profiles.")
    return json.dumps(profiles, ensure_ascii=False, indent=2)


@tool
def process_faculty_pages_and_extract_teachers(buffer_file_path: str = BUFFER_FILE_PATH, max_pages: int = 0) -> str:
    """
    Processes all faculty list pages found in the buffer and extracts teacher profiles.

    This tool reads the specified buffer file (defaulting to data/buffer/data.json),
    filters for entries where a faculty column URL was successfully found, and then
    invokes the `extract_all_teacher_profiles` tool for each of those URLs.

    Args:
        buffer_file_path: The absolute path to the buffer JSON file.

    Returns:
        A summary string indicating how many pages were processed and the total number
        of teacher profiles that were extracted and saved.
    """
    print(f"LOG: Starting batch processing of faculty pages from {buffer_file_path}...")
    
    if not os.path.exists(buffer_file_path):
        return "Error: Buffer file not found."

    try:
        with open(buffer_file_path, 'r', encoding='utf-8') as f:
            buffer_data = json.load(f)
    except json.JSONDecodeError:
        return "Error: Could not decode JSON from buffer file."

    faculty_pages = [item for item in buffer_data if item.get("type") == "faculty_column_found"]
    
    if not faculty_pages:
        return "No faculty pages found in the buffer to process."

    # Limit the number of pages to process if max_pages is set
    pages_to_process = faculty_pages
    if max_pages > 0:
        pages_to_process = faculty_pages[:max_pages]

    total_profiles_extracted = 0
    pages_processed = 0

    for entry in pages_to_process:
        faculty_url = entry.get("found_faculty_url")
        if not faculty_url:
            continue

        print(f"Processing page: {faculty_url}")
        # Call the extraction tool
        extracted_profiles_json = extract_all_teacher_profiles(faculty_url)
        
        try:
            extracted_profiles = json.loads(extracted_profiles_json)
            total_profiles_extracted += len(extracted_profiles)
            pages_processed += 1
        except json.JSONDecodeError:
            print(f"Warning: Failed to decode JSON response for {faculty_url}")
            continue

    summary = f"Batch processing complete. Processed {pages_processed} faculty pages and extracted a total of {total_profiles_extracted} teacher profiles."
    print(f"LOG: {summary}")
    return summary

@tool
def extract_teacher_links(faculty_list_url: str) -> str:
    """
    Extracts a list of teachers from the faculty list page. 
    Returns a list of dictionaries containing 'name' and 'detail_url'.
    Use this when you are on the list page (Level 3).
    """
    print(f"LOG: Extracting teacher links from {faculty_list_url}...")
    soup = _fetch_page(faculty_list_url)
    if not soup:
        return json.dumps([], ensure_ascii=False)

    teachers = []
    # 策略：寻找列表中的链接。通常老师的名字是2-4个汉字，或者英文名。
    # 这是一个启发式规则，实际中可能需要根据页面结构调整。
    
    main_content = soup.find('div', class_=['content', 'main', 'container', 'list']) or soup
    
    for a in main_content.find_all('a', href=True):
        name = a.get_text(strip=True)
        url = a['href']
        
        # 简单的过滤器：名字长度合适，且不包含常见的导航词
        exclude_words = ["更多", "首页", "Next", "Prev", "Home", "关于", "联系"]
        if 1 < len(name) < 20 and not any(w in name for w in exclude_words):
            full_url = urljoin(faculty_list_url, url)
            teachers.append({"name": name, "detail_url": full_url})

    return json.dumps(teachers, ensure_ascii=False)

@tool
def parse_teacher_detail(teacher_url: str) -> str:
    """
    Visits a specific teacher's profile page and scrapes detailed information.
    Returns a dictionary with keys: name, title, email, bio, research_area.
    If detailed parsing fails, it returns the raw text for the LLM to process.
    """
    # 注意：这个函数最适合配合 LLM 使用。
    # 这里为了演示，返回清洗后的文本，让 Agent (LLM) 自己去提取 JSON 结构。
    
    print(f"LOG: Parsing detail for {teacher_url}...")
    soup = _fetch_page(teacher_url)
    if not soup:
        return json.dumps({"error": "Page load failed"}, ensure_ascii=False)

    # 尝试提取正文区域，去除头部导航和底部版权
    # 如果找不到明确的 content div，就取 body
    content_div = soup.find('div', class_=['article', 'content', 'entry', 'main-content']) 
    if not content_div:
        content_div = soup.body

    # 移除 script 和 style
    for script in content_div(["script", "style"]):
        script.decompose()

    raw_text = content_div.get_text(separator="\n", strip=True)
    
    # 简单提取邮箱 (正则)
    import re
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    email = emails[0] if emails else "Not Found"

    # 返回结构化数据给 Agent，Bio 部分由 Agent 进一步总结
    return json.dumps({
        "url": teacher_url,
        "email_extracted": email,
        "raw_text_content": raw_text[:2000]
    }, ensure_ascii=False)


@tool
def get_page_info(url: str) -> str:
    print(f"LOG: Fetching page info: {url}")
    soup = _fetch_page(url)
    if not soup:
        return json.dumps({"url": url, "ok": False, "reason": "page_fetch_failed"}, ensure_ascii=False)
    content_div = soup.find('div', class_=['article', 'content', 'entry', 'main-content'])
    if not content_div:
        content_div = soup.body or soup
    for tag in content_div(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = content_div.get_text(separator="\n", strip=True)
    title_text = (soup.title.get_text(strip=True) if soup.title else "")
    return json.dumps({
        "url": url,
        "ok": True,
        "title_text": title_text,
        "text": text,
        "text_len": len(text)
    }, ensure_ascii=False)

@tool
def judge_teacher_profile_from_info(page_info_json: str) -> str:
    try:
        info = json.loads(page_info_json) if isinstance(page_info_json, str) else page_info_json
        url = info.get("url") or info.get("profile_url") or ""
        title_text = info.get("title_text") or ""
        text = info.get("text") or ""
        text_len = info.get("text_len") or 0
        indicators = [
            "研究方向", "个人简介", "个人简历", "教授", "副教授", "讲师", "博士生导师", "博导", "硕士生导师", "硕导", "导师",
            "Email", "E-mail", "@", "Research Interests", "Research Area", "Biography", "Profile", "Curriculum Vitae", "CV", "Contact",
            "Professor", "Associate Professor", "Assistant Professor", "Lecturer", "Supervisor", "PhD Supervisor", "Master Supervisor"
        ]
        section_indicators = [
            "教育经历", "工作经历", "科研项目", "研究项目", "科研成果", "学术成果", "代表性论文", "论文", "出版物", "著作", "讲授课程", "教学", "获奖", "荣誉", "承担项目",
            "Education", "Work Experience", "Research Projects", "Publications", "Selected Publications", "Teaching", "Awards", "Grants"
        ]
        negative_indicators = [
            "新闻", "动态", "公告", "活动", "招生", "培养特色", "课程设置", "专业介绍", "学术活动", "学术会议", "竞赛", "院系简介", "人才培养",
            "就业前景", "培养方案", "教学通知", "通知公告", "合作交流", "中心简介", "机构设置", "部门", "办公室"
        ]
        text_l = (text or "").lower()
        title_l = (title_text or "").lower()
        inds_l = [k.lower() for k in indicators]
        secs_l = [k.lower() for k in section_indicators]
        negs_l = [k.lower() for k in negative_indicators]
        matched_inds = {k for k in inds_l if k in text_l or k in title_l}
        matched_secs = {k for k in secs_l if k in text_l or k in title_l}
        matched_negs = {k for k in negs_l if k in text_l or k in title_l}
        import re
        email_found = bool(re.search(r"[\w\.-]+@[\w\.-]+\.[A-Za-z]{2,}", text))
        title_words = ["教授", "副教授", "讲师", "Professor", "Associate Professor", "Assistant Professor", "Lecturer"]
        title_lw = [w.lower() for w in title_words]
        title_hits = {w for w in title_lw if w in text_l or w in title_l}
        url_l = (url or "").lower()
        looks_like_list = any(x in url_l for x in ["/list", "szdw", "index", "/news", "/article/"])
        url_negative = any(x in url_l for x in ["/xwdt", "/hzjl", "/xshd", "/xkzy", "/pyts", "/zyjs", "/kcsz", "/yxjj", "/zxjj", "/jgsz"]) 
        score = len(matched_inds) + len(matched_secs) + len(title_hits) + (1 if email_found else 0) - len(matched_negs) - (1 if url_negative else 0)
        keep = bool((not looks_like_list) and text_len >= 200 and score >= 2)
        reason = "ok" if keep else f"rejected:list={looks_like_list},len={text_len},score={score}"
        return json.dumps({"url": url, "keep": keep, "reason": reason}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"keep": False, "reason": f"error:{e}"}, ensure_ascii=False)

# 占位：judge_llm 代理在模型初始化后创建

@tool
def judge_teacher_profile_from_info_llm(page_info_json: str, query: str = "") -> str:
    try:
        info = json.loads(page_info_json) if isinstance(page_info_json, str) else page_info_json
        url = info.get("url") or info.get("profile_url") or ""
        title_text = info.get("title_text") or ""
        text = info.get("text") or ""
        qp = (query or "").strip()
        user_prompt = f"URL: {url}\nTitle: {title_text}\nContent:\n{text}" + (f"\nQuery: {qp}" if qp else "")
        try:
            result = judge_llm.invoke({
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            })
            content = result.get("messages", [])[-1].text if result.get("messages") else ""
            res = json.loads(content) if content else {}
            keep = bool(res.get("keep"))
            reason = res.get("reason") or ""
            out = {"url": url, "keep": keep, "reason": reason}
            if isinstance(res.get("data"), dict):
                data = res.get("data")
                nm = (data.get("name") or "").strip()
                if keep and (query or "").strip() and (not nm or len(nm) < 2):
                    out["keep"] = False
                    out["reason"] = "missing_truename"
                else:
                    out["data"] = data
            return json.dumps(out, ensure_ascii=False)
        except Exception:
            fallback = judge_teacher_profile_from_info(info)
            return fallback if isinstance(fallback, str) else json.dumps(fallback, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"keep": False, "reason": f"error:{e}"}, ensure_ascii=False)

@tool
def clean_teacher_profiles(buffer_path: str = TEACHER_PROFILES_BUFFER_FILE_PATH, dry_run: bool = False, use_llm: bool = True, query: str = "") -> str:
    """
    Cleans the teacher_profiles.json by retaining only true mentor detail pages.
    Reads list, judges each entry via judge_teacher_profile, writes filtered list back.
    Returns a summary string.
    """
    print(f"LOG: Cleaning teacher profiles from {TEACHER_PROFILES_BUFFER_FILE_PATH}...")
    if not os.path.exists(buffer_path):
        return json.dumps({"error": "buffer_not_found"}, ensure_ascii=False)
    try:
        with open(buffer_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid_json"}, ensure_ascii=False)
    if not isinstance(data, list):
        return json.dumps({"error": "not_list"}, ensure_ascii=False)
    retained = []
    removed = []
    for item in data:
        if not isinstance(item, dict):
            removed.append({"item": item, "reason": "not_dict"})
            continue
        url = item.get("profile_url")
        if not url:
            removed.append({"item": item, "reason": "no_url"})
            continue
        try:
            page_info = get_page_info(url)
            if use_llm:
                rj = judge_teacher_profile_from_info_llm(page_info, query)
            else:
                rj = judge_teacher_profile_from_info(page_info)
            r = json.loads(rj) if isinstance(rj, str) else rj
            if r.get("keep"):
                retained.append(item)
            else:
                removed.append({"url": url, "reason": r.get("reason")})
        except Exception as e:
            removed.append({"url": url, "reason": f"judge_error:{e}"})
    if not dry_run:
        os.makedirs(os.path.dirname(buffer_path), exist_ok=True)
        with open(buffer_path, 'w', encoding='utf-8') as f:
            json.dump(retained, f, ensure_ascii=False, indent=4)
    summary = {
        "buffer_path": buffer_path,
        "retained_count": len(retained),
        "removed_count": len(removed),
        "dry_run": dry_run
    }
    print(f"LOG: Cleaned. Retained={len(retained)} Removed={len(removed)}")
    return json.dumps(summary, ensure_ascii=False, indent=2)

def select_teacher_profiles(detail_url: str, query: str = "") -> str:
    """
    Cleans the teacher_profiles.json by retaining only true mentor detail pages.
    Reads list, judges each entry via judge_teacher_profile, writes filtered list back.
    Returns a summary string.
    """
    use_llm = True
    page_info = get_page_info(detail_url)
    if use_llm:
        rj = judge_teacher_profile_from_info_llm(page_info, query)
    else:
        rj = judge_teacher_profile_from_info(page_info)
    r = json.loads(rj) if isinstance(rj, str) else rj
    return r


@tool
def judge_relevance_with_llm(page_info_json: str, query: str) -> str:
    try:
        info = json.loads(page_info_json) if isinstance(page_info_json, str) else page_info_json
        title = info.get("title_text") or ""
        text = info.get("text") or ""
        prompt_sys = (
            "你是一个页面相关性判定助手，只返回JSON。"
            "根据用户的query与页面内容，判断是否相关：相关返回 {\"keep\": true, \"reason\": \"简述相关点\"}"
            "不相关返回 {\"keep\": false, \"reason\": \"简述不相关原因\"}。"
        )
        prompt_user = f"query: {query}\nTitle: {title}\nContent:\n{text[:2000]}"
        try:
            resp = model.invoke([
                {"role": "system", "content": prompt_sys},
                {"role": "user", "content": prompt_user}
            ])
            content = getattr(resp, "content", None) or getattr(resp, "text", "")
        except Exception:
            content = ""
        if content:
            try:
                res = json.loads(content)
                keep = bool(res.get("keep"))
                reason = res.get("reason") or ""
                return json.dumps({"keep": keep, "reason": reason}, ensure_ascii=False)
            except Exception:
                pass
        q = (query or "").strip().lower()
        words = [w for w in re.split(r"[\s,，]+", q) if w]
        text_l = (title + "\n" + text).lower()
        hits = sum(1 for w in words if w in text_l)
        keep = hits >= 1
        reason = "keyword_match" if keep else "no_keyword_match"
        return json.dumps({"keep": keep, "reason": reason}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"keep": False, "reason": f"error:{e}"}, ensure_ascii=False)

@tool
def initialize_run_buffer() -> str:
    """
    Initializes the run by clearing the temporary buffer file 'data/buffer/data.json'.
    This should be called before starting a new scraping pipeline.
    """
    buffer_file = os.path.join('data', 'buffer', 'data.json')
    try:
        if os.path.exists(buffer_file):
            os.remove(buffer_file)
            return f"Success: Cleared buffer file at {buffer_file}"
        else:
            buffer_dir = os.path.dirname(buffer_file)
            if not os.path.exists(buffer_dir):
                os.makedirs(buffer_dir)
            return "Success: Buffer file did not exist. Ready for new run."
    except Exception as e:
        return f"Error: Failed to initialize buffer: {e}"


@tool
def save_to_school_json(
    school_name: str, 
    department_name: str, 
    teachers_data: List[Dict]
) -> str:
    """
    Saves the scraped teacher data into a JSON file structure.
    File path will be: ./data/{school_name}/{department_name}.json
    
    Args:
        school_name: Name of the university.
        department_name: Name of the college/department.
        teachers_data: List of teacher dictionaries.
    """
    base_dir = "./data"
    # 清洗文件名非法字符
    safe_school = "".join([c for c in school_name if c.isalnum() or c in (' ', '_')]).strip()
    safe_dept = "".join([c for c in department_name if c.isalnum() or c in (' ', '_')]).strip()
    
    school_dir = os.path.join(base_dir, safe_school)
    if not os.path.exists(school_dir):
        os.makedirs(school_dir)
        
    file_path = os.path.join(school_dir, f"{safe_dept}.json")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(teachers_data, f, ensure_ascii=False, indent=4)
        return f"Success: Saved {len(teachers_data)} teachers to {file_path}"
    except Exception as e:
        return f"Error saving file: {str(e)}"

@tool
def run_full_scraping_pipeline(
    school_name: str, 
    school_url: str, 
    max_departments: int = 3, 
    max_teachers_per_dept: int = 5
) -> str:
    """
    Executes the complete scraping pipeline with Robust JSON Parsing.
    """
    print(f"\n🚀 STARTING PIPELINE FOR: {school_name} ({school_url})")
    
    # 1. 获取学院列表
    raw_departments = find_department_list_page(school_url)
    
    # --- 🛠️ 修复核心：数据类型自动纠正 ---
    departments = []
    try:
        if isinstance(raw_departments, str):
            # 如果返回的是 JSON 字符串，解析它
            # 这里的 strip 是为了防止有一些多余的空格或换行
            cleaned_str = raw_departments.strip()
            # 有时候工具可能返回 "Found 0 departments"，这种非JSON字符串要过滤
            if cleaned_str.startswith("["):
                departments = json.loads(cleaned_str)
            else:
                print(f"Warning: Tool returned non-JSON string: {cleaned_str[:50]}...")
                return f"Error: find_department_list_page returned invalid format."
        elif isinstance(raw_departments, list):
            # 如果已经是列表，直接使用
            departments = raw_departments
        else:
            return f"Error: Unknown return type {type(raw_departments)}"
            
    except json.JSONDecodeError as e:
        return f"Error parsing department list JSON: {e}"
    # ---------------------------------------

    if not departments:
        return f"Failed: Could not find department list for {school_name}."
    
    # 再次检查列表内的元素是否为字典（防止 list of strings）
    if departments and isinstance(departments[0], str):
         return f"Error: Department list contains strings instead of dicts. Check the tool implementation."

    print(f"Found {len(departments)} departments. Processing top {max_departments}...")
    
    # 限制处理数量
    target_depts = departments[:max_departments] if max_departments else departments
    
    total_teachers_saved = 0
    errors = []

    for i, dept in enumerate(target_depts):
        # 安全获取字段
        if not isinstance(dept, dict):
            print(f"Skipping invalid item type: {type(dept)}")
            continue
            
        dept_name = dept.get('name', 'Unknown Dept')
        dept_url = dept.get('url', '')
        
        if not dept_url:
            continue

        print(f"\n--- Processing Dept [{i+1}/{len(target_depts)}]: {dept_name} ---")
        
        try:
            # 2. 寻找师资栏目
            faculty_col_url = find_faculty_column(dept_url)
            if not faculty_col_url:
                print(f"Skipping: No faculty column found for {dept_name}")
                continue
            
            # 3. 提取教师列表
            # 同样对这里进行类似的防错处理（可选，但建议加上）
            raw_teacher_links = extract_teacher_links(faculty_col_url)
            teacher_links = []
            if isinstance(raw_teacher_links, str):
                try:
                     if raw_teacher_links.strip().startswith("["):
                        teacher_links = json.loads(raw_teacher_links)
                except: pass
            elif isinstance(raw_teacher_links, list):
                teacher_links = raw_teacher_links
            
            if not teacher_links:
                print(f"Skipping: No teachers extracted from {faculty_col_url}")
                continue
                
            # 限制每个学院的老师数量
            target_teachers = teacher_links[:max_teachers_per_dept] if max_teachers_per_dept else teacher_links
            
            # 4. 详情抓取与保存
            for t_idx, teacher in enumerate(target_teachers):
                if not isinstance(teacher, dict): continue
                
                t_name = teacher.get('name', 'Unknown')
                t_url = teacher.get('detail_url', '')
                
                if not t_url: continue

                # 检查是否已存在
                if _is_url_in_buffer(t_url):
                    print(f"  [Skip] {t_name} already exists.")
                    continue

                # 抓取详情 (返回的是 dict)
                detail_data = parse_teacher_detail(t_url)
                # 如果 parse_teacher_detail 也返回了 string，也需要 json.loads，但通常它返回 dict
                if isinstance(detail_data, str):
                    try: detail_data = json.loads(detail_data)
                    except: detail_data = {}

                if "error" in detail_data:
                    print(f"  [Error] Failed to parse {t_name}")
                    continue
                
                record = {
                    "school_name": school_name,
                    "department_name": dept_name,
                    "name": t_name,
                    "title": teacher.get("raw_title", "N/A"),
                    "profile_url": t_url,
                    "email": detail_data.get("extracted_email", "N/A"),
                    "raw_bio_text": detail_data.get("clean_text_content", ""),
                    "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                _save_to_central_buffer(record)
                total_teachers_saved += 1
                print(f"  [Saved] {t_name}")
                
                time.sleep(0.5)
                
        except Exception as e:
            error_msg = f"Error in {dept_name}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
            
    return f"Pipeline Completed. Saved {total_teachers_saved} teachers from {len(target_depts)} departments."


@tool
def get_teachers_with_name_from_buffer(buffer_path: str = r"F:\My_Project\skillCreator_System\data\buffer\teacher_profiles.json") -> str:
    """
    从缓存文件中读取所有包含姓名的教师信息，并以JSON字符串形式返回。
    当所有师资页面都已通过 `extract_all_teacher_profiles` 处理完毕后，调用此工具来获取最终的、已筛选的数据，用于生成最终报告。
    """
    if not os.path.exists(buffer_path):
        return json.dumps({"error": f"Buffer file not found at {buffer_path}"})

    try:
        with open(buffer_path, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Could not decode JSON from {buffer_path}"})
    except Exception as e:
        return json.dumps({"error": f"An error occurred while reading the file: {e}"})

    teachers_with_name = []
    for profile in profiles:
        if isinstance(profile, dict) and isinstance(profile.get('data'), dict):
            if profile['data'].get('name'):
                teachers_with_name.append(profile)
    
    return json.dumps(teachers_with_name, ensure_ascii=False, indent=2)

# ============================================================================
# Step 2: Create specialized sub-agents
# ============================================================================
local_llm = True
if local_llm:
    model = ChatOpenAI(
        base_url="http://localhost:11434/v1",   # ← 所有平台都是这个地址
        api_key="",                            # 不能缺少
        model="qwen3:4b",                      # 模型名保持一致
        temperature=0.7,
    )


else:
    model = ChatOpenAI(
        api_key="sk-997037365aba487e97a21edb4d162b47",  # 请替换为你的实际 API 密钥
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat")

deepseek_model = ChatOpenAI(
        api_key="sk-997037365aba487e97a21edb4d162b47",  # 请替换为你的实际 API 密钥
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat")

# 用于页面类型独立判定的轻量代理（无上下文记忆）
# judge_llm = create_agent(
#     model,
#     tools=[ensure_university_url],
#     system_prompt=(
#         "你是页面类型判定助手。只基于当前页面信息独立判断并严格返回JSON，无任何多余文本。不需要使用工具"
#         "输入包含：URL、Title、Content，可选包含 Query。"
#         "输出规则，请严格按照以下格式输出,不要有其他："
#         "1) 若不是教师/导师个人介绍页：返回 {\"keep\": false, \"reason\": \"...\"}"
#         "2) 若是教师/导师个人介绍页："
#         "   - 若未提供 Query：返回 {\"keep\": true, \"reason\": \"...\"}"
#         "   - 若提供了 Query：若相关，返回 {\"keep\": true, \"reason\": \"...\", \"data\": {\"name\": \"...\", \"title\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"research_interests\": \"...\", \"department\": \"...\", \"school\": \"...\", \"hats\": [\"...\"]}}；若不相关，返回 {\"keep\": false, \"reason\": \"irrelevant\"}"
#         "   - 若提供了 Query：若相关但 data.name 为空或非真实姓名（中文2-20字或英文姓名），返回 {\"keep\": false, \"reason\": \"missing_truename\"}"
#         "字段说明：name/title/email/phone/research_interests/department/hats 从页面可提取到的显式信息中获取；没有则置为空或空数组。"
#         "参数含义：name=教师姓名（真实人名）；title=职称/岗位；email=电子邮箱；phone=联系电话或手机号；research_interests=研究方向文本；department=所属学院/系/中心；school=学校名称；hats=荣誉/头衔列表。"
#     )
# )

judge_llm = create_agent(
    model,
    tools=[ensure_university_url],
    system_prompt=(
        "你是页面类型判定助手。只基于当前页面信息独立判断并严格返回JSON，无任何多余文本。不需要使用工具"
        "输入包含：URL、Title、Content，可选包含 Query。"
        "输出规则："
        "1) 若不是教师/导师个人介绍页：返回 {\"keep\": false, \"reason\": \"...\"}"
        "2) 若是教师/导师个人介绍页："
        "   - 若未提供 Query：返回 {\"keep\": true, \"reason\": \"...\"}"
        "   - 若提供了 Query：若相关，返回 {\"keep\": true, \"reason\": \"...\", \"data\": {\"name\": \"...\", \"title\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"research_interests\": \"...\", \"department\": \"...\", \"school\": \"...\", \"hats\": [\"...\"]}}；若不相关，返回 {\"keep\": false, \"reason\": \"irrelevant\"}"
        "   - 若提供了 Query：若相关但 data.name 为空或非真实姓名（中文2-20字或英文姓名），返回 {\"keep\": false, \"reason\": \"missing_truename\"}"
        "   - 字段说明：name/title/email/phone/research_interests/department/hats 从页面可提取到的显式信息中获取；没有则置为空或空数组。分析的结果放到reason中"
        "请严格按照输出规则格式输出，不要有其他输出格式"
    )
)

# deepseek
WebDiscovery_agent = create_agent(
    # model, # 本地model
    deepseek_model,
    tools=[search_universities],
    system_prompt=(
        "你是一名专业的学校网站检索助手。 "
        "根据用户请求获取符合要求的学校名称与学校官网URL。 "
        "将请求分解为适当的工具调用并协调结果；当请求涉及多个操作时，按顺序使用多个工具。 "
        "在需要时使用 load_universities_db 加载本地高校数据集。"
        "在需要加载本地高校数据集并按地域/学校/类型关键词筛选时,使用search_universities 返回名称与URL。"
        "如果学校没有提供URL，直接删除该学校"
        "在最终响应中列出选中的学校与其URL，并简要确认筛选条件。"
    )
)

@tool
def WebDiscovery(query: str) -> str:
    """Discovers web pages for a given query, like finding university websites.

    Use this when the user asks a general question that requires finding initial web pages,
    such as "Find universities in Shenzhen".

    Input: A natural language request (e.g., '深圳的学校').
    """
    result = WebDiscovery_agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    # The output of an agent invocation is typically in the 'output' key.
    return result.get("output", "")

WebScraping_agent = create_agent(
    deepseek_model, # deepseek
    # model, #本地
    # 这里定义了5个核心工具，赋予Agent像人一样的浏览和决策能力
    tools=[
        WebDiscovery,
        find_department_list_page,
        discover_all_departments,   
        find_faculty_column,  # 在学校主页找“院系设置”入口
        extract_all_teacher_profiles,
        get_teachers_with_name_from_buffer,
    ],
    system_prompt=(
        "你是一名专业数据采集专家。你的任务是根据用户给定任务，分步完成信息的搜集和整理。"
        "这是一个深度遍历任务，请严格按照以下层级逻辑执行，并使用正确的工具：\n"
        "1. **发现学校链接**: "
        "   - 使用 `WebDiscovery` 工具，根据用户query发现所有符合条件的学校主页URL。\n"
        "2. **发现院系链接**: "
        "   - 对于所有学校主页URL，逐个使用 `discover_all_departments` discover_all_departments函数的输入端口为学校主页URL，输出端口为所有院系主页URL的列表。\n"
        "   - 注意：如果有多个学校，请一个学校一个学校执行。\n"
        "3. **定位师资栏目**: "
        "   - 对每个院系URL，使用 `find_faculty_column` 工具找到对应的“师资队伍”或类似栏目的URL。"
        "   - 这个工具会自动将找到的URL存入 `data/buffer/data.json` 文件中。\n"
        "   - 注意：如果有多个相关院系，请对每个学校每一个院系使用 `find_faculty_column`，请一个学院一个学院执行不要并行使用。"   
        "4. **提取并筛选师资页面信息**: "
        "   - 调用 extract_all_teacher_profiles 工具，传入列表页参数 URL，并将筛选关键词（如‘院士’）作为 query 参数以过滤目标教师。"
        "   - 此工具会自动处理 `data.json` 中的所有URL，并将匹配的教师信息存入 `teacher_profiles.json`。\n"
        "5. **获取已筛选的教师数据**: "
        "   - 在上一步完成后，调用 `get_teachers_with_name_from_buffer` 工具。"
        "   - 这个工具会从 `teacher_profiles.json` 读取所有包含姓名的教师的完整信息，这是生成最终报告所需的数据。\n"
        "6. **汇总分析并生成报告**: "
        "   - 基于上一步获取的数据，对所有符合用户query条件的教师信息进行汇总和分析，然后生成最终的报告。"
    )
)

CleanTeacherProfiles_agent = create_agent(
    model,
    tools=[
        clean_teacher_profiles,
    ],
    system_prompt=(
        "你是一名专业数据筛选专家。你的任务是根据用户的要求，调用工具清洗教师信息。\n"
        "请遵循以下步骤：\n"
        "1. 分析用户的输入，例如用户可能要求'找具有院士头衔的老师信息'。\n"
        "2. 调用 `clean_teacher_profiles` 工具来完成这个任务。\n"
        "3. 在调用工具时，将用户的原始输入作为 `query` 参数传递给工具。\n"
        "4. 同时，将 `use_llm` 参数设置为 True，以确保使用更高精度的语言模型进行判断。\n"
    )
)


# if __name__ == "__main__":
#     # Example: User request requiring both calendar and email coordination
#     user_request = (
#         "Schedule a meeting with the design team next Tuesday at 2pm for 1 hour, "
#         "and send them an email reminder about reviewing the new mockups."
#     )

#     print("User Request:", user_request)
#     print("\n" + "="*80 + "\n")

#     for step in supervisor_agent.stream(
#         {"messages": [{"role": "user", "content": user_request}]}
#     ):
#         for update in step.values():
#             for message in update.get("messages", []):
#                 message.pretty_print()
