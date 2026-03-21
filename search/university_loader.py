import requests
import time
import json

class GaokaoCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.gaokao.cn/school/search",
            "Origin": "https://www.gaokao.cn",
            "Content-Type": "application/json"
        }
        self.school_list_api = "https://api.eol.cn/web/api"

    def get_all_school_ids(self, max_pages=None):
        """
        第一步：获取所有学校的ID列表
        """
        all_schools = []
        page = 1
        size = 20 
        
        print(">>> 开始爬取学校列表 ID...")
        
        while True:
            payload = {
                "keyword": "",
                "page": page,
                "province_id": "",
                "school_type": "",
                "size": size,
                "uri": "apidata/api/gk/school/lists"
            }

            try:
                resp = requests.post(self.school_list_api, headers=self.headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                if 'data' in data and 'item' in data['data']:
                    items = data['data']['item']
                else:
                    items = []

                if not items:
                    print(f"第 {page} 页无数据，爬取结束。")
                    break
                
                print(f"正在处理列表第 {page} 页，获取 {len(items)} 所学校...")
                
                for item in items:
                    all_schools.append({
                        "school_id": item.get("school_id"),
                        "name": item.get("name")
                    })

                page += 1
                if max_pages and page > max_pages:
                    break
                
                time.sleep(0.2) 

            except Exception as e:
                print(f"列表页请求失败: {e}")
                break
                
        return all_schools

    def get_school_detail(self, school_id):
        """
        第二步：获取学校详情（官网 + 省份 + 城市）
        """
        url = f"https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json"
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                info = data.get("data", {})
                
                # --- 提取数据 ---
                result = {
                    "school_site": info.get("school_site", "") or "暂无官网数据", # 学校官网
                    "site": info.get("site", ""),               # 招生官网
                    "province": info.get("province_name", ""),  # 省份
                    "city": info.get("city_name", "")           # 城市
                }
                return result
            else:
                return None
        except Exception as e:
            print(f"ID {school_id} 请求异常: {e}")
            return None

    def run(self):
        # ⚠️ 注意：如需爬取全部，请将 max_pages=5 改为 max_pages=None
        schools = self.get_all_school_ids(max_pages=None) 
        
        results = []
        print(f"\n>>> 开始提取详细信息 (共 {len(schools)} 所)...")
        
        total = len(schools)
        for index, school in enumerate(schools):
            s_id = school['school_id']
            s_name = school['name']
            
            # 获取详情
            detail = self.get_school_detail(s_id)
            
            if detail:
                print(f"[{index+1}/{total}] {detail['province']}-{detail['city']} : {s_name}")
                
                results.append({
                    "school_name": s_name,
                    "school_id": s_id,
                    "province": detail['province'],           # 新增：省份
                    "city": detail['city'],                   # 新增：城市
                    "official_website": detail['school_site'],# 学校官网
                    "admission_website": detail['site'],      # 招生官网
                    "detail_page": f"https://www.gaokao.cn/school/{s_id}"
                })
            else:
                print(f"[{index+1}/{total}] {s_name} 获取详情失败")
            
            time.sleep(0.1)

        # 保存为 JSON
        self.save_to_json(results)

    def save_to_json(self, data):
        filename = "china_schools_full_info.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"\n>>> 数据已成功保存到 {filename}")
        except Exception as e:
            print(f"保存文件失败: {e}")

if __name__ == "__main__":
    crawler = GaokaoCrawler()
    crawler.run()