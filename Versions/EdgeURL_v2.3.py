import os
import time
import random
import hashlib
import argparse
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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
import pandas as pd
from datetime import datetime

init(autoreset=True)

# ====================== 核心配置 ======================
MAX_PAGES = 999  # 最大爬取页数
SCROLL_PAUSE = 1  # 滚动等待时间
RETRY_LIMIT = 10  # 元素重试次数
VERIFICATION_TIME = 1  # 延长验证码处理时间（秒）
CONSECUTIVE_SAME_LIMIT = 5  # 降低连续相同页面阈值，避免无效循环
CONTENT_TIMEOUT = 30  # 延长内容加载超时时间
# 文档类型扩展名
DOC_EXTENSIONS = ('.pdf', '.docx', '.doc', '.rar', '.inc', '.txt', '.sql',
                  '.conf', '.xlsx', '.xls', '.csv', '.ppt', '.pptx')
# 需过滤的扩展名
FILTER_EXTENSIONS = ('.apk',)


# ====================== 新增配置 ======================

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
               |.·´¯`·..·|
               |`·._.·´`·.| 
               |.·´¯`·..·|
               `·.      .·´ 
            . · ´¯¯¯¯` · . 
          ,' ,'  .·´¯`·.   ', ' 
          ', ',  `·._.·´  ,' , ' 
            '  ,_____,  ' 
                 `·..·´ 
    """
    print(Fore.CYAN + banner)
    print(Fore.GREEN + "=" * 60)
    print(Fore.GREEN + "  EdgeURL 基于Edge浏览器的URL爬取器（v2.3版） - 辉小鱼")
    print(Fore.GREEN + "=" * 60)
    print(Style.RESET_ALL)


def setup_driver(proxy=None):
    """设置并返回 Edge 浏览器驱动，修复潜在的SSL和SmartScreen问题"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        driver_path = os.path.join(current_dir, "msedgedriver.exe")

        if not os.path.exists(driver_path):
            print(Fore.RED + f"[-] 未找到 Edge 驱动: {driver_path}")
            print(Fore.YELLOW + "[!] 请确保 msedgedriver.exe 在脚本同一目录下")
            return None

        try:
            from selenium.webdriver.edge.options import Options
            options = Options()
        except ImportError:
            options = webdriver.EdgeOptions()

        # 新增：禁用SmartScreen以解决相关错误
        options.add_argument("--disable-features=EdgeSmartScreen")
        # 新增：忽略SSL错误
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")

        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )

        if proxy:
            options.add_argument(f'--proxy-server={proxy}')

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
        time.sleep(1)
    except Exception as e:
        print(Fore.RED + f"[-] 自动滚动失败: {e}")


def get_page_content_hash(driver):
    """获取页面主体内容的哈希值（用于判断内容是否变化）"""
    try:
        content_elements = driver.find_elements(By.CSS_SELECTOR, 'li.b_algo')
        content_text = " ".join([el.text for el in content_elements])
        return hashlib.md5(content_text.encode('utf-8')).hexdigest()
    except Exception as e:
        print(Fore.RED + f"[-] 获取页面内容哈希失败: {e}")
        return hashlib.md5(driver.page_source.encode('utf-8')).hexdigest()


def find_next_page(driver):
    """查找下一页按钮（兼容多种形态）"""
    selectors = [
        'a[title="Next page"]',
        'a[aria-label="Next page"]',
        'a.sb_pagN',
    ]
    xpath_selectors = [
        '//a[contains(text(), "下一页")]',
        '//a[contains(text(), "Next")]',
    ]

    for selector in selectors:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, selector)
            if btns:
                return btns[0]
        except InvalidSelectorException:
            print(Fore.RED + f"[-] 无效的 CSS 选择器: {selector}")
            continue

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
    """判断 URL 是否有效，新增过滤逻辑"""
    # 过滤.apk结尾的URL
    if url.endswith(FILTER_EXTENSIONS):
        return False

    # 过滤路径中包含/jpg的URL
    if '/jpg' in url:
        return False

    excluded_domains = [
        'cn.bing.com', 'microsoft.com', 'bing.com', 'baidu.com',
        'google.com', 'wikipedia.org', 'github.com', 'stackoverflow.com'
    ]

    if base_domain not in url:
        return False

    for domain in excluded_domains:
        if domain in url:
            return False

    return True


def classify_urls(url_list):
    """分类URL为普通URL和文档URL"""
    normal_urls = []
    doc_urls = []

    for url in url_list:
        # 检查是否为文档类型
        if url.lower().endswith(DOC_EXTENSIONS):
            doc_urls.append(url)
        else:
            normal_urls.append(url)

    return normal_urls, doc_urls


def extract_bing_urls(driver, base_domain):
    """提取Bing搜索结果的URL和标题，并进行初步过滤"""
    urls = []  # 存储格式：[(url, title), ...]
    try:
        # 定位所有搜索结果项
        result_items = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#b_results > li.b_algo'))
        )

        for item in result_items:
            try:
                # 提取URL
                link_element = item.find_element(By.CSS_SELECTOR, 'h2 a')
                link = link_element.get_attribute('href')

                # 提取标题
                title = link_element.text.strip()

                if link and is_valid_url(link, base_domain):
                    urls.append((link, title))
            except Exception as e:
                print(Fore.RED + f"[-] 提取单个URL/标题失败: {e}")
                continue
    except Exception as e:
        print(Fore.RED + f"[-] 提取搜索结果失败: {e}")
    return urls


def save_to_excel(url_list, base_domain, is_document=False):
    """保存URL和标题到Excel，支持普通URL和文档URL的不同路径"""
    try:
        # 转换为DataFrame
        df = pd.DataFrame(url_list, columns=['URL', '标题'])

        # 构建保存路径
        if is_document:
            result_dir = os.path.join('results', base_domain, '爬取的文档')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(result_dir, f'{base_domain}_文档_{timestamp}.xlsx')
        else:
            result_dir = os.path.join('results', base_domain)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(result_dir, f'Edge_results_{base_domain}_{timestamp}.xlsx')

        os.makedirs(result_dir, exist_ok=True)
        df.to_excel(excel_file, index=False)
        print(Fore.GREEN + f"[+] Excel 文件已保存: {excel_file}")
        return excel_file
    except Exception as e:
        print(Fore.RED + f"[-] 保存Excel文件失败: {e}")
        return None


def crawl_domain(driver, query, proxy=None):
    """爬取单个域名相关的 URL 和标题"""
    base_domain = query.split(':')[1]
    all_normal_urls = []  # 普通URL [(url, title), ...]
    all_doc_urls = []  # 文档URL [(url, title), ...]
    page_num = 1
    consecutive_same_count = 0

    print(Fore.YELLOW + f"[+] 正在爬取 {base_domain} 的相关 URL...")
    driver.get(f"https://www.bing.com/search?q={query}")
    print(Fore.YELLOW + f"[+] 手动处理验证码（若有），{VERIFICATION_TIME} 秒后继续...")
    time.sleep(VERIFICATION_TIME)

    prev_url = driver.current_url
    prev_content_hash = get_page_content_hash(driver)

    while page_num <= MAX_PAGES:
        print(Fore.YELLOW + f"\n[+] 第 {page_num} 页 | 开始爬取")
        auto_scroll(driver)

        page_urls = extract_bing_urls(driver, base_domain)
        # 分类URL和标题
        normal_urls = []
        doc_urls = []
        for url, title in page_urls:
            if url.lower().endswith(DOC_EXTENSIONS):
                doc_urls.append((url, title))
            else:
                normal_urls.append((url, title))

        all_normal_urls.extend(normal_urls)
        all_doc_urls.extend(doc_urls)

        # 有有效URL才打印统计
        has_new_urls = len(normal_urls) + len(doc_urls) > 0
        if has_new_urls:
            print(
                Fore.GREEN + f"[+] 第 {page_num} 页 | 新增普通 URL: {len(normal_urls)} 个 | 新增文档 URL: {len(doc_urls)} 个")
            # 普通URL（蓝色）
            if normal_urls:
                print(Fore.CYAN + "[+] 新增普通 URL 列表：")
                for idx, (url, title) in enumerate(normal_urls, 1):
                    print(Fore.CYAN + f"    {idx}. {url}")
                    print(Fore.WHITE + f"       标题: {title}")
            # 文档URL（紫色）
            if doc_urls:
                print(Fore.MAGENTA + "[+] 新增文档 URL 列表：")
                for idx, (url, title) in enumerate(doc_urls, 1):
                    print(Fore.MAGENTA + f"    {idx}. {url}")
                    print(Fore.WHITE + f"       标题: {title}")

        # 查找下一页（原逻辑不变）
        next_btn = find_next_page(driver)
        if not next_btn:
            print(Fore.RED + "[-] 未找到下一页按钮，终止爬取")
            break

        try:
            current_url = driver.current_url
            current_content_hash = get_page_content_hash(driver)
            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            next_btn.click()

            WebDriverWait(driver, CONTENT_TIMEOUT).until(
                lambda d: d.current_url != current_url or
                          get_page_content_hash(d) != current_content_hash
            )

            new_url = driver.current_url
            new_content_hash = get_page_content_hash(driver)

            if new_url == current_url and new_content_hash == current_content_hash:
                consecutive_same_count += 1
                print(Fore.RED + f"[!] 页面未刷新！连续 {consecutive_same_count} 次")
            else:
                consecutive_same_count = 0

            prev_url = new_url
            prev_content_hash = new_content_hash

            if consecutive_same_count >= CONSECUTIVE_SAME_LIMIT:
                print(Fore.RED + f"[!] 连续 {CONSECUTIVE_SAME_LIMIT} 次页面未刷新，终止爬取")
                break

            page_num += 1
            time.sleep(random.uniform(2, 5))

        except TimeoutException:
            print(Fore.RED + "[-] 页面加载超时，终止爬取")
            break
        except Exception as e:
            print(Fore.RED + f"[-] 翻页过程中发生错误: {e}")
            break

    return all_normal_urls, all_doc_urls, page_num - 1


def generate_email_content(domain_stats, total_domains, total_urls, total_pages, execution_time):
    """生成详细的邮件内容"""
    content = f"""
📊 EdgeURL 爬取任务完成报告 📊
尊敬的辉小鱼先生：
EdgeURL 爬虫已完成所有域名的爬取工作！以下是详细报告：
📋 总体统计：
  • 处理域名总数：{total_domains} 个
  • 总爬取页数：{total_pages} 页
  • 总获取 URL：{total_urls} 个
  • 执行时间：{execution_time:.2f} 秒
🔍 各域名详细结果：
"""
    for domain, stat in domain_stats.items():
        content += f"""
  • {domain}:
    - 爬取页数：{stat.get('pages', 0)}
    - 获取普通 URL 数量：{stat.get('normal_urls', 0)}
    - 获取文档 URL 数量：{stat.get('doc_urls', 0)}
    - 普通结果保存路径：results/{domain}/
    - 文档结果保存路径：results/{domain}/爬取的文档/
"""
    content += """
💡 说明：
- 文档类型URL已单独保存
- 由于Bing的反爬机制，部分URL可能无法获取
🚀 祝您渗透测试顺利，必出高危漏洞！
EdgeURL 爬虫助手 🤖
"""
    return content


def send_email(sender_email, sender_password, receiver_email, subject, content):
    """发送邮件（简化版，优化错误捕获与反馈）"""
    try:
        print(Fore.YELLOW + "[+] 准备发送邮件...")
        message = MIMEMultipart()
        message['From'] = formataddr((str(Header("EdgeURL 爬虫助手", 'utf-8')), sender_email))
        message['To'] = receiver_email
        message['Subject'] = Header(subject, 'utf-8')
        message.attach(MIMEText(content, 'plain', 'utf-8'))

        print(Fore.YELLOW + "[+] 连接 SMTP 服务器...")
        with smtplib.SMTP_SSL('smtp.qq.com', 465) as server:
            server.set_debuglevel(0)
            print(Fore.YELLOW + "[+] 正在进行身份验证...")
            server.login(sender_email, sender_password)
            print(Fore.YELLOW + "[+] 身份验证成功，正在发送邮件...")
            server.sendmail(sender_email, [receiver_email], message.as_string())
            print(Fore.GREEN + "[√] 邮件发送成功！")
            return True
    except smtplib.SMTPException as e:
        if "b'\\x00\\x00\\x00'" in str(e):
            print(Fore.YELLOW + "[!] 出现 SMTP 通信特殊异常，邮件可能已发送成功")
            return True
        else:
            print(Fore.RED + f"[-] SMTP 错误: {str(e)}")
            print(Fore.YELLOW + "[!] 请检查邮箱账号、授权码和网络连接")
    except Exception as e:
        print(Fore.RED + f"[-] 发送邮件时发生未知错误: {str(e)}")
    return False


def main():
    print_banner()
    parser = argparse.ArgumentParser(description='Bing 相关 URL 爬取（优化版）')
    parser.add_argument('-f', '--file', type=str, default='domain.txt', help='域名列表文件，默认为 domain.txt')
    parser.add_argument('--proxy', type=str, default=None, help='代理，如 127.0.0.1:7890')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(Fore.RED + f"[-] 未找到文件: {args.file}")
        return

    with open(args.file, 'r', encoding='utf-8') as f:
        domains = [line.strip() for line in f.readlines() if line.strip()]

    if not domains:
        print(Fore.RED + f"[-] 文件 {args.file} 为空或全部为空行")
        return

    driver = setup_driver(args.proxy)
    if not driver:
        return

    domain_stats = {}
    total_domains = len(domains)
    total_normal_urls = 0
    total_doc_urls = 0
    total_pages = 0
    start_time = time.time()

    try:
        for domain in domains:
            domain_start_time = time.time()
            query = f'site:{domain}'
            # 爬取并获取分类后的URL
            normal_urls, doc_urls, pages = crawl_domain(driver, query, args.proxy)

            normal_count = len(normal_urls)
            doc_count = len(doc_urls)

            total_normal_urls += normal_count
            total_doc_urls += doc_count
            total_pages += pages

            domain_stats[domain] = {
                'pages': pages,
                'normal_urls': normal_count,
                'doc_urls': doc_count
            }

            # 保存普通URL
            normal_file = save_to_excel(normal_urls, domain, is_document=False)
            # 保存文档URL
            doc_file = save_to_excel(doc_urls, domain, is_document=True) if doc_urls else None

            if normal_file or doc_file:
                print(Fore.GREEN + f"\n[+] 爬取 {domain} 完成 | 页数: {pages} | "
                                   f"普通URL: {normal_count} | 文档URL: {doc_count} | "
                                   f"耗时: {time.time() - domain_start_time:.2f} 秒")

            delay = random.uniform(3, 7)
            print(Fore.YELLOW + f"[+] 准备爬取下一个域名，{delay:.1f} 秒后继续...")
            time.sleep(delay)

    except Exception as e:
        print(Fore.RED + f"[-] 爬取过程中发生错误: {e}")
    finally:
        if driver:
            print(Fore.YELLOW + "\n[+] 所有域名爬取完成，关闭浏览器...")
            driver.quit()

    execution_time = time.time() - start_time
    total_urls = total_normal_urls + total_doc_urls
    email_content = generate_email_content(domain_stats, total_domains, total_urls, total_pages, execution_time)

    config = {
        "sender_email": "1794686508@qq.com",
        "sender_password": "busnjcluyxtlejgc",
        "receiver_email": "shenghui3301@163.com",
        "subject": f"📧 EdgeURL 爬取完成！共获取 {total_urls} 个URL",
        "content": email_content
    }

    email_sent = send_email(**config)
    if email_sent:
        print(Fore.GREEN + "\n[✓] 爬取和通知流程全部完成！")
    else:
        print(Fore.RED + "\n[-] 爬取完成，但邮件通知失败")
        print(Fore.YELLOW + "[*] 请检查邮箱配置和网络连接")

    input(Fore.YELLOW + "\n[*] 按回车退出...")


if __name__ == "__main__":
    main()