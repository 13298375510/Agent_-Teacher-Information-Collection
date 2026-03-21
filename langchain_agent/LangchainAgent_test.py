import sys
from langchain_skillTest import WebDiscovery_agent, WebScraping_agent, CleanTeacherProfiles_agent

def invoke_agent(agent, prompt: str) -> None:
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        print(result["messages"][-1].text)
    except Exception as e:
        print(f"ERROR: {e}")

def stream_agent(agent, prompt: str) -> None:
    """以流式方式调用 Agent，实时打印思考过程和结果。"""
    print(f"--- 开始流式调用 Agent，输入: '{prompt}' ---")
    try:
        for chunk in agent.stream({"messages": [{"role": "user", "content": prompt}]}):
            # 流式输出的块结构可能不同，这里处理常见的几种情况
            content_to_print = ""
            if isinstance(chunk, dict):
                if "messages" in chunk and chunk["messages"]:
                    # 这是 AIMessageChunk 的常见结构
                    content_to_print = chunk["messages"][-1].content
                elif "output" in chunk:
                    content_to_print = chunk["output"]
            
            if content_to_print:
                print(content_to_print, end="", flush=True)

        print("\n--- 流式调用结束 ---")
    except Exception as e:
        print(f"\n流式调用出错: {e}")

def run_webdiscovery() -> None:
    print("== WebDiscovery_agent ==")
    invoke_agent(WebDiscovery_agent, "深圳的学校")

def run_webscraping() -> None:
    print("== WebScraping_agent (流式模式) ==")
    # 在这里可以在 invoke_agent 和 stream_agent 之间切换
    # invoke_agent(WebScraping_agent, "https://www.smbu.edu.cn/")
    # stream_agent(WebScraping_agent, "深圳北理莫斯科大学人工智能研究院具有院士头衔的老师信息")
    # stream_agent(WebScraping_agent, "深圳北理莫斯科大学具有院士头衔的老师信息")
    # stream_agent(WebScraping_agent, "河南理工大学大学具有教授头衔的老师信息")
    stream_agent(WebScraping_agent, "深圳市具有院士头衔的老师信息")

def run_cleanteacherprofiles() -> None:
    print("== CleanTeacherProfiles_agent ==")
    stream_agent(CleanTeacherProfiles_agent, "找具有院士头衔的老师信息")



if __name__ == "__main__":
    target = "webscraping"
    if len(sys.argv) > 2 and sys.argv[1] == "--agent":
        target = sys.argv[2].lower()
    
    if target == "webdiscovery":
        run_webdiscovery()
    elif target == "webscraping":
        run_webscraping()
    elif target == "cleanteacherprofiles":
        run_cleanteacherprofiles()
    elif target == "cleanteacherprofiles":
        run_cleanteacherprofiles()
    else:
        # 默认情况下，两个都运行
        run_webdiscovery()
        print("=" * 40)
        run_webscraping()
