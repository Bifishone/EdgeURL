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

# ======================  核心配置  ======================
MAX_PAGES = 999  # 最大爬取页数
SCROLL_PAUSE = 0.5  # 滚动等待时间
RETRY_LIMIT = 10  # 元素重试次数
VERIFICATION_TIME = 1.5  # 验证码处理时间（秒）
CONSECUTIVE_SAME_LIMIT = 999  # 连续相同页面阈值
CONTENT_TIMEOUT = 25  # 内容加载超时时间


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
    print(Fore.GREEN + "  EdgeURL 基于Edge浏览器的URL爬取器（v3版） - 辉小鱼")
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
        'github.com',
        'stackoverflow.com',
        # 可以在这里添加更多需要排除的域名
    ]

    # 检查 URL 是否包含目标域名
    if base_domain not in url:
        return False

    # 检查 URL 是否包含任何排除的域名
    for domain in excluded_domains:
        if domain in url:
            return False

    return True


def extract_bing_urls(driver, base_domain):
    """专门提取Bing搜索结果的URL"""
    urls = set()
    try:
        # 使用最直接的方法：查找所有链接
        elements = driver.find_elements(By.CSS_SELECTOR, 'a')
        for element in elements:
            try:
                link = element.get_attribute('href')
                if link and is_valid_url(link, base_domain):
                    urls.add(link)
            except Exception:
                continue
    except Exception as e:
        print(Fore.RED + f"[-] 检查 URL 提取失败: {e}")

    return list(urls)


def crawl_domain(driver, query, proxy=None):
    """使用已有的浏览器实例爬取单个域名相关的 URL"""
    base_domain = query.split(':')[1]
    all_urls = []  # 存储URL
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

        # 直接提取所有URL
        page_urls = extract_bing_urls(driver, base_domain)

        # 过滤并处理 URL
        valid_urls = [url for url in page_urls if is_valid_url(url, base_domain)]
        all_urls.extend(valid_urls)

        print(Fore.GREEN + f"[+] 第 {page_num} 页 | 新增 {len(valid_urls)} 个 URL")
        if valid_urls:
            print(Fore.CYAN + "[+] 新增 URL 列表：")
            for idx, url in enumerate(valid_urls, 1):
                print(Fore.CYAN + f"    {idx}. {url}")
        else:
            print(Fore.YELLOW + f"[!] 第 {page_num} 页没有有效URL")

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

    return all_urls, page_num - 1


def save_to_excel(url_list, base_domain):
    """将URL列表保存到Excel文件"""
    try:
        # 创建DataFrame
        df = pd.DataFrame({'URL': url_list})

        # 确保目录存在
        result_dir = os.path.join('results', base_domain)
        os.makedirs(result_dir, exist_ok=True)

        # 保存Excel文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_file = os.path.join(result_dir, f'Edge_results_{base_domain}_{timestamp}.xlsx')

        # 保存为Excel
        df.to_excel(excel_file, index=False)

        print(Fore.GREEN + f"[+] Excel 文件已保存: {excel_file}")
        return excel_file
    except Exception as e:
        print(Fore.RED + f"[-] 保存Excel文件失败: {e}")
        return None


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
    - 获取 URL 数量：{stat.get('urls', 0)}
    - 结果保存路径：results/{domain}/Edge_results_{domain}.xlsx
"""

    content += """
💡 说明：
- 所有结果显示已在Excel文件中
- 由于Bing的反爬机制，部分URL可能无法获取

🚀 祝您渗透测试顺利，必出高危漏洞！

EdgeURL 爬虫助手 🤖
"""
    return content


def send_email(sender_email, sender_password, receiver_email, subject, content):
    """发送邮件（简化版，优化错误捕获与反馈）"""
    try:
        print(Fore.YELLOW + "[+] 准备发送邮件...")

        # 创建邮件对象
        message = MIMEMultipart()
        message['From'] = formataddr((str(Header("EdgeURL 爬虫助手", 'utf-8')), sender_email))
        message['To'] = receiver_email
        message['Subject'] = Header(subject, 'utf-8')

        # 添加邮件正文
        message.attach(MIMEText(content, 'plain', 'utf-8'))

        # 尝试 SSL 连接
        print(Fore.YELLOW + "[+] 连接 SMTP 服务器...")
        with smtplib.SMTP_SSL('smtp.qq.com', 465) as server:
            # 开启 debug 详细日志（按需开启，排查问题时设为 1，正常使用设为 0）
            server.set_debuglevel(0)
            print(Fore.YELLOW + "[+] 正在进行身份验证...")
            server.login(sender_email, sender_password)
            print(Fore.YELLOW + "[+] 身份验证成功，正在发送邮件...")
            server.sendmail(sender_email, [receiver_email], message.as_string())
            print(Fore.GREEN + "[√] 邮件发送成功！")
            return True
    except smtplib.SMTPException as e:
        # 细分 SMTP 异常类型，更精准提示
        if "b'\\x00\\x00\\x00'" in str(e):
            print(Fore.YELLOW + "[!] 出现 SMTP 通信特殊异常（可能是服务器侧短暂握手问题），但邮件实际已发送成功")
            print(Fore.YELLOW + "[!] 可忽略此提示，或联系邮箱服务商确认是否有潜在通信限制")
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

    # 创建单个浏览器实例
    driver = setup_driver(args.proxy)
    if not driver:
        return

    # 统计信息
    domain_stats = {}
    total_domains = len(domains)
    total_urls = 0
    total_pages = 0
    start_time = time.time()
    all_data = []  # 存储所有域名的所有URL

    try:
        for domain in domains:
            domain_start_time = time.time()
            query = f'site:{domain}'

            # 爬取当前域名（复用浏览器）
            url_list, pages = crawl_domain(driver, query, args.proxy)
            url_count = len(url_list)
            total_urls += url_count
            total_pages += pages

            # 存储当前域名的统计信息
            domain_stats[domain] = {
                'pages': pages,
                'urls': url_count
            }

            # 收集所有数据以供后续处理
            all_data.extend(url_list)

            # 创建结果
            result_file = save_to_excel(url_list, domain)
            if result_file:
                print(
                    Fore.GREEN + f"\n[+] 爬取 {domain} 完成 | 页数: {pages} | URL: {url_count} | 耗时: {time.time() - domain_start_time:.2f} 秒")
                print(Fore.GREEN + f"[+] 结果Excel已保存至: {result_file}")

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

    # 计算总执行时间
    execution_time = time.time() - start_time

    # 生成详细的邮件内容
    email_content = generate_email_content(domain_stats, total_domains, total_urls, total_pages, execution_time)

    # ⚠️ 请修改以下配置信息 ⚠️
    config = {
        # 发件人QQ邮箱信息（必须修改）
        "sender_email": "1794686508@qq.com",  # 你的QQ邮箱地址
        "sender_password": "busnjcluyxtlejgc",  # 你的QQ邮箱SMTP授权码

        # 收件人邮箱信息（可修改）
        "receiver_email": "shenghui3301@163.com",  # 收件人邮箱地址

        # 邮件内容（自动生成）
        "subject": f"📧 EdgeURL 爬取完成！共获取 {total_urls} 个URL",
        "content": email_content
    }

    # 发送邮件
    email_sent = send_email(**config)

    if email_sent:
        print(Fore.GREEN + "\n[✓] 爬取和通知流程全部完成！")
    else:
        print(Fore.RED + "\n[-] 爬取完成，但邮件通知失败")
        print(Fore.YELLOW + "[*] 请检查邮箱配置和网络连接")

    input(Fore.YELLOW + "\n[*] 按回车退出...")


if __name__ == "__main__":
    main()