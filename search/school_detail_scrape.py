import requests
import json

def get_school_info(school_id):
    """
    爬取中国教育在线(gaokao.cn)指定学校ID的信息
    """
    
    # 经过抓包分析，学校的基础信息存储在这个 JSON 地址中
    # 这种直接请求 API 的方式比解析 HTML 更快、更稳定
    url = f"https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json"
    
    # 伪装成浏览器，防止被简单的反爬虫拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://www.gaokao.cn/school/{school_id}",
        "Origin": "https://www.gaokao.cn"
    }

    try:
        print(f"正在请求数据: {url} ...")
        response = requests.get(url, headers=headers)
        
        # 检查请求是否成功
        response.raise_for_status()
        
        # 解析 JSON 数据
        data = response.json()
        
        # 提取关键信息 (根据返回的 JSON 结构)
        # 注意：具体的字段名 key 可能会随网站更新而变化，以下是当前常见的字段
        info = data.get('data', {})
        
        if not info:
            print("未找到数据，可能学校ID不存在。")
            return

        print("-" * 30)
        print(f"学校名称: {info.get('name', 'N/A')}")
        print(f"学校ID:   {info.get('school_id', 'N/A')}")
        print(f"所在地区: {info.get('province_name', 'N/A')} - {info.get('city_name', 'N/A')}")
        print(f"层次:     {info.get('level_name', 'N/A')} ({info.get('type_name', 'N/A')})")
        print(f"性质:     {info.get('nature_name', 'N/A')}")
        
        # 处理标签 (如 985/211/双一流)
        tags = []
        if info.get('f985') == '1': tags.append("985")
        if info.get('f211') == '1': tags.append("211")
        if info.get('dual_class_name'): tags.append(info.get('dual_class_name'))
        print(f"标签:     {', '.join(tags)}")
        
        # 获取学校简介 (通常 content 字段包含 HTML 标签，这里简单截取)
        content = info.get('content', '')
        # 简单去除 HTML 标签以便预览 (可选)
        from xml.etree.ElementTree import fromstring
        clean_content = content.replace('<p>', '').replace('</p>', '\n').replace('&nbsp;', ' ')[:100]
        print(f"简介预览: {clean_content}...")
        
        print("-" * 30)
        print("原始数据已获取，可进行保存操作。")
        
        return info

    except requests.exceptions.HTTPError as e:
        print(f"HTTP 错误: {e}")
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
    except json.JSONDecodeError:
        print("数据解析失败，返回的可能不是JSON格式。")

if __name__ == "__main__":
    # 这里的 3783 是你 URL 中的 ID
    school_data = get_school_info("3783")