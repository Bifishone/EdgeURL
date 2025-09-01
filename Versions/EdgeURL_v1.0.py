import os
import time
import random
import argparse
import hashlib
from colorama import init, Fore, Style
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    InvalidSelectorException
)

init(autoreset=True)

# ======================  核心配置  ======================
MAX_PAGES = 100  # 最大爬取页数
SCROLL_PAUSE = 2  # 滚动等待时间
RETRY_LIMIT = 3  # 元素重试次数
VERIFICATION_TIME = 3  # 验证码处理时间（秒）
CONSECUTIVE_SAME_LIMIT = 3  # 连续相同页面阈值
CONTENT_TIMEOUT = 10  # 内容加载超时时间


# =======================================================


def print_banner():
    """打印程序的横幅信息"""
    banner = r"""
                    /|\ 
                  /  |  \
                '/ ` |   '\ 
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |    |    |
                |'.·´|`·.'|
                |;::;|;::;|
                |;::;|;::;|
                |;::;|;::;|
                |;::;|;::;|
                |.·´¯`·.| 
                |;      ';|
                |`·._.·´|
                |;::;|;::;|
 |¯`·._.·´¯¯¯¯¯¯¯¯¯`·._.·´¯|
 |              Bifish                '| 
 |.·´¯`·.__________ '.·´¯`·.| 
 |.·´¯`·.___         '___.·´¯`·.| 
               .·´      `·. 
               |.·´¯`·..·´| 
               |`·._.·´`·.| 
               |.·´¯`·..·´| 
               |`·._.·´`·.| 
               |.·´¯`·..·´| 
               `·.      .·´ 
            . · ´¯¯¯¯` · . 
          ,' ,'  .·´¯`·.   ', ' 
          ', ',  `·._.·´  ,' , ' 
            '  ,_____,  ' 
                 `·..·´ 
    """
    print(Fore.CYAN + banner)
    print(Fore.GREEN + "=" * 60)
    print(Fore.GREEN + "  Selenium 真翻页爬取器（优化版） - 爬取 URL")
    print(Fore.GREEN + "=" * 60)
    print(Style.RESET_ALL)


def setup_driver(proxy=None):
    """设置并返回 Edge 浏览器驱动"""
    try:
        # 动态查找驱动路径（当前目录）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        driver_path = os.path.join(current_dir, "msedgedriver.exe")

        # 检查驱动文件是否存在
        if not os.path.exists(driver_path):
            print(Fore.RED + f"[-] 未找到 Edge 驱动: {driver_path}")
            print(Fore.YELLOW + "[!] 请确保 msedgedriver.exe 在脚本同一目录下")
            return None

        # 兼容不同 Selenium 版本的导入方式
        try:
            # 尝试新的导入方式（Selenium 4+）
            from selenium.webdriver.edge.options import Options
            options = Options()
        except ImportError:
            # 回退到旧的导入方式
            options = webdriver.EdgeOptions()

        # 设置浏览器选项
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')

        # 创建驱动实例
        service = webdriver.edge.service.Service(driver_path)
        driver = webdriver.Edge(service=service, options=options)

        # 隐藏自动化特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}}; 
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
            """
        })
        return driver
    except Exception as e:
        print(Fore.RED + f"[-] 驱动设置失败: {e}")
        return None


def auto_scroll(driver):
    """自动滚动页面以确保内容完全加载"""
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        # 确保内容完全加载
        time.sleep(1)
    except Exception as e:
        print(Fore.RED + f"[-] 自动滚动失败: {e}")


def get_page_content_hash(driver):
    """获取页面主体内容的哈希值（用于判断内容是否变化）"""
    try:
        # 提取搜索结果区域的内容（排除导航、页脚等干扰）
        content_elements = driver.find_elements(By.CSS_SELECTOR, 'li.b_algo')
        content_text = " ".join([el.text for el in content_elements])
        # 生成哈希值
        content_hash = hashlib.md5(content_text.encode('utf-8')).hexdigest()
        return content_hash
    except Exception as e:
        print(Fore.RED + f"[-] 获取页面内容哈希失败: {e}")
        # 回退方案：使用整个页面源代码
        return hashlib.md5(driver.page_source.encode('utf-8')).hexdigest()


def find_next_page(driver):
    """查找下一页按钮（兼容多种形态）"""
    selectors = [
        'a[title="Next page"]',  # 国际版（带 title）
        'a[aria-label="Next page"]',  # 辅助标签
        'a.sb_pagN',  # 旧版 fallback
    ]

    # 使用 XPath 替代 CSS 的 :contains 选择器
    xpath_selectors = [
        '//a[contains(text(), "下一页")]',  # 中文"下一页"按钮
        '//a[contains(text(), "Next")]',  # 英文"Next"按钮
    ]

    # 尝试 CSS 选择器
    for selector in selectors:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, selector)
            if btns:
                return btns[0]
        except InvalidSelectorException:
            print(Fore.RED + f"[-] 无效的 CSS 选择器: {selector}")
            continue

    # 尝试 XPath 选择器
    for xpath in xpath_selectors:
        try:
            btns = driver.find_elements(By.XPATH, xpath)
            if btns:
                return btns[0]
        except Exception as e:
            print(Fore.RED + f"[-] 查找下一页按钮失败: {e}")
            continue

    return None


def is_valid_url(url, base_domain):
    """判断 URL 是否有效（包含目标域名且不包含排除的域名）"""
    # 排除的域名列表
    excluded_domains = [
        'cn.bing.com',
        'microsoft.com',
        'bing.com',
        'baidu.com',
        'google.com',
        'wikipedia.org',
        # 可以在这里添加更多需要排除的域名
    ]

    # 检查 URL 是否包含目标域名
    if base_domain not in url:
        return False

    # 检查 URL 是否包含任何排除的域名
    for domain in excluded_domains:
        if domain in url:
            return False

    # 过滤掉以 .apk 结尾的 URL
    if url.endswith('.apk'):
        return False

    # 检查 URL 是否包含特定文件扩展名（用于特殊处理）
    special_extensions = ['.pdf', '.docx', '.doc', '.rar', '.inc', '.txt', '.sql', '.conf', '.xlsx', '.xls', '.csv',
                          '.ppt', '.pptx']
    if any(url.endswith(ext) for ext in special_extensions):
        return "document"  # 标记为文档类型

    return True


def handle_document_urls(urls, base_domain):
    """处理爬取的文档类型 URL"""
    all_urls = set()

    # 收集文档类型 URL
    document_urls = {ext: [] for ext in
                     ['.pdf', '.docx', '.doc', '.rar', '.inc', '.txt', '.sql', '.conf', '.xlsx', '.xls', '.csv', '.ppt',
                      '.pptx']}

    for url in urls:
        if url.endswith('.apk'):
            continue  # 跳过 APK 文件

        for ext in ['.pdf', '.docx', '.doc', '.rar', '.inc', '.txt', '.sql', '.conf', '.xlsx', '.xls', '.csv', '.ppt',
                    '.pptx']:
            if url.endswith(ext):
                document_urls[ext].append(url)
                break

    # 创建文档分类目录
    base_dir = os.path.join('results', base_domain)
    os.makedirs(base_dir, exist_ok=True)

    # 处理文档类型的 URL
    for ext, ext_urls in document_urls.items():
        if ext_urls:
            # 创建子目录
            ext_dir = os.path.join(base_dir, ext[1:])  # 去掉开头的点
            os.makedirs(ext_dir, exist_ok=True)

            # 写入文档文件
            doc_file_path = os.path.join(ext_dir, f'{base_domain}{ext}.txt')
            with open(doc_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(ext_urls))
            print(Fore.GREEN + f"[+] 已保存 {len(ext_urls)} 个文档到: {doc_file_path}")

    # 返回非文档类型的 URL 集合
    return set(urls) - set(document_urls['.pdf']) - set(document_urls['.docx']) - set(document_urls['.doc']) - set(
        document_urls['.rar']) - set(document_urls['.inc']) - set(document_urls['.txt']) - set(
        document_urls['.sql']) - set(document_urls['.conf']) - set(document_urls['.xlsx']) - set(
        document_urls['.xls']) - set(document_urls['.csv']) - set(document_urls['.ppt']) - set(document_urls['.pptx'])


def crawl_domain(driver, query, proxy=None):
    """使用已有的浏览器实例爬取单个域名相关的 URL"""
    base_domain = query.split(':')[1]
    all_urls = set()
    page_num = 1
    consecutive_same_count = 0  # 连续相同页面计数器

    # 导航到新的搜索页面
    print(Fore.YELLOW + f"[+] 正在爬取 {base_domain} 的相关 URL...")
    driver.get(f"https://www.bing.com/search?q={query}")
    print(Fore.YELLOW + f"[+] 手动处理验证码（若有），{VERIFICATION_TIME} 秒后继续...")
    time.sleep(VERIFICATION_TIME)

    prev_url = driver.current_url
    prev_content_hash = get_page_content_hash(driver)

    while page_num <= MAX_PAGES:
        print(Fore.YELLOW + f"\n[+] 第 {page_num} 页 | 开始爬取")
        auto_scroll(driver)

        # 提取当前页面的所有 URL
        page_urls = extract_urls(driver, base_domain)

        # 过滤并处理 URL
        valid_urls = [url for url in page_urls if is_valid_url(url, base_domain)]
        all_urls.update(valid_urls)

        print(Fore.GREEN + f"[+] 第 {page_num} 页 | 新增 {len(valid_urls)} 个 | 累计 {len(all_urls)}")
        if valid_urls:
            print(Fore.CYAN + "[+] 新增 URL 列表：")
            for idx, url in enumerate(valid_urls, 1):
                print(Fore.CYAN + f"    {idx}. {url}")

        # 查找下一页按钮
        next_btn = find_next_page(driver)
        if not next_btn:
            print(Fore.RED + "[-] 未找到下一页按钮，终止爬取")
            break

        # 点击下一页
        try:
            current_url = driver.current_url
            current_content_hash = get_page_content_hash(driver)

            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            next_btn.click()

            # 等待页面加载（智能等待）
            WebDriverWait(driver, CONTENT_TIMEOUT).until(
                lambda d: d.current_url != current_url or
                          get_page_content_hash(d) != current_content_hash
            )

            # 验证页面是否真的变化
            new_url = driver.current_url
            new_content_hash = get_page_content_hash(driver)

            if new_url == current_url and new_content_hash == current_content_hash:
                consecutive_same_count += 1
                print(Fore.RED + f"[!] 页面未刷新！连续 {consecutive_same_count} 次")
            else:
                consecutive_same_count = 0  # 页面已刷新，重置计数器

            prev_url = new_url
            prev_content_hash = new_content_hash

            # 检查连续相同页面次数
            if consecutive_same_count >= CONSECUTIVE_SAME_LIMIT:
                print(Fore.RED + f"[!] 连续 {CONSECUTIVE_SAME_LIMIT} 次页面未刷新，终止爬取")
                break

            page_num += 1
            time.sleep(random.uniform(2, 5))  # 随机延迟
        except TimeoutException:
            print(Fore.RED + "[-] 页面加载超时，终止爬取")
            break
        except Exception as e:
            print(Fore.RED + f"[-] 翻页过程中发生错误: {e}")
            break

    # 处理文档类型的 URL
    filtered_urls = handle_document_urls(list(all_urls), base_domain)

    return filtered_urls


def extract_urls(driver, base_domain):
    """从页面中提取包含指定域名的 URL，并过滤无效链接"""
    urls = set()
    selectors = ['li.b_algo a', 'div.b_ans a', 'footer a', 'aside a']
    for selector in selectors:
        try:
            for a in driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    link = a.get_attribute('href')
                    if not link:
                        continue
                    if is_valid_url(link, base_domain):
                        urls.add(link)
                except Exception as e:
                    print(Fore.RED + f"[-] 提取 URL 失败: {e}")
        except Exception as e:
            print(Fore.RED + f"[-] 查找元素失败: {e}")
    return urls


if __name__ == "__main__":
    print_banner()
    parser = argparse.ArgumentParser(description='Bing 相关 URL 爬取（优化版）')
    parser.add_argument('-f', '--file', type=str, default='domain.txt', help='域名列表文件，默认为 domain.txt')
    parser.add_argument('--proxy', type=str, default=None, help='代理，如 127.0.0.1:7890')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(Fore.RED + f"[-] 未找到文件: {args.file}")
        exit(1)

    with open(args.file, 'r', encoding='utf-8') as f:
        domains = f.read().splitlines()

    if not domains:
        print(Fore.RED + f"[-] 文件 {args.file} 为空")
        exit(1)

    # 创建单个浏览器实例
    driver = setup_driver(args.proxy)
    if not driver:
        exit(1)

    try:
        for domain in domains:
            query = f'site:{domain}'
            start_time = time.time()

            # 爬取当前域名（复用浏览器）
            urls = crawl_domain(driver, query, args.proxy)

            # 创建结果目录
            results_dir = os.path.join('results', domain)
            os.makedirs(results_dir, exist_ok=True)

            # 保存结果（只保存非文档结果）
            result_file = os.path.join(results_dir, f'Edge_results_{domain}.txt')
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(urls))

            print(
                Fore.GREEN + f"\n[+] 爬取 {domain} 完成 | 总 URL: {len(urls)} | 耗时: {time.time() - start_time:.2f} 秒")
            print(Fore.GREEN + f"[+] 结果已保存至: {result_file}")

            # 为下一个域名做准备（随机延迟）
            delay = random.uniform(3, 7)
            print(Fore.YELLOW + f"[+] 准备爬取下一个域名，{delay:.1f} 秒后继续...")
            time.sleep(delay)

    except Exception as e:
        print(Fore.RED + f"[-] 爬取过程中发生错误: {e}")
    finally:
        # 所有域名爬取完成后才关闭浏览器
        if driver:
            print(Fore.YELLOW + "\n[+] 所有域名爬取完成，关闭浏览器...")
            driver.quit()

    input(Fore.YELLOW + "\n[*] 按回车退出...")