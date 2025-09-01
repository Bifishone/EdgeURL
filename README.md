# 🐟 EdgeURL 爬虫工具

<img width="2532" height="1430" alt="image" src="https://github.com/user-attachments/assets/c02f853e-b4a8-41c7-bce5-2d2dc317deed" />


> 基于 Edge 浏览器的高效 URL 爬取器，专为网络信息收集设计

## 📑 目录

- [简介](https://www.doubao.com/chat/18844951930585090#-简介)
- [功能特点](https://www.doubao.com/chat/18844951930585090#-功能特点)
- [安装指南](https://www.doubao.com/chat/18844951930585090#-安装指南)
- [使用方法](https://www.doubao.com/chat/18844951930585090#-使用方法)
- [核心功能详解](https://www.doubao.com/chat/18844951930585090#-核心功能详解)
- [配置说明](https://www.doubao.com/chat/18844951930585090#-配置说明)
- [输出说明](https://www.doubao.com/chat/18844951930585090#-输出说明)
- [注意事项](https://www.doubao.com/chat/18844951930585090#-注意事项)
- [更新日志](https://www.doubao.com/chat/18844951930585090#-更新日志)
- [作者信息](https://www.doubao.com/chat/18844951930585090#-作者信息)

## 🌟 简介

EdgeURL 是一款基于 Selenium 和 Edge 浏览器的 URL 爬取工具，能够自动从 Bing 搜索引擎爬取指定域名的相关链接，并智能分类普通网页和文档资源。工具设计初衷是为网络安全从业者提供高效的信息收集能力，也可用于网络内容分析等场景。

<img width="1718" height="1217" alt="image" src="https://github.com/user-attachments/assets/653542fa-62e3-4678-b711-f6cb4283537f" />


程序具有良好的反反爬机制、自动处理分页、智能内容识别和邮件通知等功能，让 URL 收集工作变得简单高效。

## ✨ 功能特点

- 🚀 **高效爬取**：自动翻页，最多可爬取 999 页搜索结果
- 🧠 **智能分类**：自动区分普通网页和文档（PDF、DOCX、XLS 等）
- 🛡️ **反反爬机制**：隐藏自动化特征，规避搜索引擎反爬策略
- 📊 **详细统计**：记录爬取进度、URL 数量等关键指标
- 📧 **邮件通知**：任务完成后自动发送详细报告到指定邮箱
- 📁 **结构化输出**：结果保存为 Excel 格式，按域名和类型分类存储
- 🔍 **精准过滤**：可自定义过滤规则，排除不需要的 URL
- 🌐 **代理支持**：可配置代理服务器，提高爬取灵活性

## 🛠️ 安装指南

### 前置条件

- Python 3.8 或更高版本
- Microsoft Edge 浏览器
- 对应版本的 [EdgeDriver](https://developer.microsoft.com/zh-cn/microsoft-edge/tools/webdriver/)（需放置在脚本同一目录）

### 安装步骤

1. **克隆仓库**

   ```bash
   git clone https://github.com/Bifishone/EdgeURL.git
   cd EdgeURL
   ```

2. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

   所需依赖包括：selenium、colorama、pandas、openpyxl、pycryptodome

3. **配置 EdgeDriver**

   - 下载与本地 Edge 浏览器版本匹配的 EdgeDriver
   - 将下载的 `msedgedriver.exe` 放置在脚本同一目录下

## 🚀 使用方法

### 基本用法

1. **准备域名列表**
   创建 `domain.txt` 文件，每行填写一个需要爬取的域名，例如：

   ```plaintext
   example.com
   test.com
   ```

2. **运行程序**

   ```bash
   python EdgeURL.py
   ```

### 高级选项

- **指定域名文件**

  ```bash
  python EdgeURL.py -f my_domains.txt
  ```

- **使用代理**

  ```bash
  python EdgeURL.py --proxy 127.0.0.1:7890
  ```

## 🔍 核心功能详解

### 自动爬取流程

1. 程序启动后会初始化 Edge 浏览器并隐藏自动化特征
2. 对每个域名构造 `site:domain` 格式的 Bing 搜索 query
3. 自动滚动页面加载所有结果，提取并过滤 URL
4. 智能识别下一页按钮，自动翻页继续爬取
5. 检测页面内容是否重复，避免无效循环
6. 将结果按普通 URL 和文档 URL 分类保存

### URL 过滤机制

- 排除指定域名（如 [bing.com](https://bing.com/)、[google.com](https://google.com/) 等）
- 过滤特定文件类型（如 .apk）
- 排除包含特定路径的 URL（如包含 /jpg 的路径）
- 确保只保留包含目标域名的 URL

### 邮件通知功能

任务完成后，程序会自动发送包含以下信息的邮件：

- 总体统计（域名数量、总页数、总 URL 数）
- 各域名详细结果
- 结果保存路径
- 执行时间统计

## ⚙️ 配置说明

核心配置参数可在代码中修改：

```python
MAX_PAGES = 999  # 最大爬取页数
SCROLL_PAUSE = 1  # 滚动等待时间
RETRY_LIMIT = 10  # 元素重试次数
VERIFICATION_TIME = 1  # 验证码处理时间（秒）
CONSECUTIVE_SAME_LIMIT = 99  # 连续相同页面阈值
CONTENT_TIMEOUT = 10  # 内容加载超时时间
```



文档类型和过滤扩展名配置：

```python
# 文档类型扩展名
DOC_EXTENSIONS = ('.pdf', '.docx', '.doc', '.rar', '.inc', '.txt', '.sql',
                  '.conf', '.xlsx', '.xls', '.csv', '.ppt', '.pptx')
# 需过滤的扩展名
FILTER_EXTENSIONS = ('.apk',)
```

## 📁 输出说明

爬取结果保存在 `results` 目录下，按域名组织：

```plaintext
results/
└── example.com/
    ├── Edge_results_example.com_20231010_153045.xlsx  # 普通URL
    └── 爬取的文档/
        └── example.com_文档_20231010_153045.xlsx     # 文档URL
```



Excel 文件包含两列：URL 和标题，便于后续分析和处理。

## ⚠️ 注意事项

1. 爬取速度不宜过快，程序已内置随机延迟，请勿随意修改
2. 部分网站可能会出现验证码，程序会暂停等待人工处理
3. 长时间爬取可能导致 IP 被临时限制，建议使用代理
4. 请遵守目标网站的 robots.txt 规则和相关法律法规
5. 大规模爬取可能会消耗较多网络流量和系统资源

## 📝 更新日志

### v1.0

- 初始版本发布
- 实现基本的 URL 爬取和分类功能
- 添加邮件通知和 Excel 导出功能
- 完善反反爬机制

## 👤 作者信息

- 作者：一只鱼（Bifishone）
- 项目地址：https://github.com/Bifishone/EdgeURL
- 联系方式：bifishone@163.com

![image](https://api.star-history.com/svg?repos=Bifishone/EdgeURL&type=Date)](https://star-history.com/#Bifishone/EdgeURL&Date)



*本工具仅用于合法的网络信息收集和安全研究，请勿用于非法用途*
