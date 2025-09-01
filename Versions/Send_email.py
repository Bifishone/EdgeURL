import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr


def send_email(sender_email, sender_password, receiver_email, subject, content):
    # 创建邮件对象
    message = MIMEMultipart()

    # 使用 formataddr 函数严格按照 RFC 标准格式化 From 字段
    # 发件人姓名（可自定义）
    sender_name = "Python 邮件发送"
    message['From'] = formataddr((str(Header(sender_name, 'utf-8')), sender_email))

    message['To'] = receiver_email  # 直接使用邮箱地址，QQ邮箱不接受 Header 包装
    message['Subject'] = Header(subject, 'utf-8')

    # 添加邮件正文
    message.attach(MIMEText(content, 'plain', 'utf-8'))

    try:
        # 连接QQ邮箱SMTP服务器（SSL加密）
        smtp_obj = smtplib.SMTP_SSL('smtp.qq.com', 465)
        smtp_obj.login(sender_email, sender_password)

        # 发送邮件
        smtp_obj.sendmail(sender_email, [receiver_email], message.as_string())
        print("邮件发送成功！")

    except smtplib.SMTPException as e:
        print(f"邮件发送失败: {e}")

    finally:
        # 关闭连接
        if 'smtp_obj' in locals():
            smtp_obj.quit()


if __name__ == "__main__":
    # ⚠️ 请修改以下配置信息 ⚠️
    config = {
        # 发件人QQ邮箱信息（必须修改）
        "sender_email": "1794686508@qq.com",  # 你的QQ邮箱地址
        "sender_password": "busnjcluyxtlejgc",  # 你的QQ邮箱SMTP授权码

        # 收件人邮箱信息（可修改）
        "receiver_email": "shenghui3301@163.com",  # 收件人邮箱地址

        # 邮件内容（可修改）
        "subject": "📧 Edge的URL信息收集工作已完成！",  # 邮件主题
        "content": """
        您好！尊敬的辉小鱼先生！

        关于Edge浏览器的URL收集工作已全面完成！
        如果你收到了这封邮件，说明EdgeURL.py脚本已运行完毕！

        祝您挖洞愉快，必出高危哦~~~
        EdgeURL 邮件助手
        """
    }

    # 发送邮件
    send_email(**config)