import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

log = logging.getLogger(__name__)

# SMTP 配置（优先从环境变量读取，否则使用默认值）
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")


def _build_html(notices):
    """将公告列表格式化为美观的 HTML 邮件"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = ""
    for n in notices:
        deadline = n.get("deadline") or "详见公告"
        major = n.get("major_category") or "-"
        category = n.get("category") or "-"
        rows += f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:10px 8px;">
            <a href="{n['url']}" style="color:#1e40af;text-decoration:none;font-weight:500;">
              {n['title']}
            </a>
          </td>
          <td style="padding:10px 8px;white-space:nowrap;">{category}</td>
          <td style="padding:10px 8px;white-space:nowrap;">{major}</td>
          <td style="padding:10px 8px;white-space:nowrap;color:#dc2626;">{deadline}</td>
        </tr>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f3f4f6;padding:20px;">
      <div style="max-width:680px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <div style="background:linear-gradient(135deg,#1e40af,#2563eb);padding:24px 28px;">
          <h1 style="color:#fff;font-size:20px;margin:0;">广东考编情报站 · 每日推送</h1>
          <p style="color:#bfdbfe;font-size:13px;margin:6px 0 0;">{today} · 共 {len(notices)} 条新公告</p>
        </div>
        <div style="padding:20px 28px;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <thead>
              <tr style="border-bottom:2px solid #e5e7eb;">
                <th style="padding:8px;text-align:left;color:#6b7280;">公告标题</th>
                <th style="padding:8px;text-align:left;color:#6b7280;">分类</th>
                <th style="padding:8px;text-align:left;color:#6b7280;">专业</th>
                <th style="padding:8px;text-align:left;color:#6b7280;">截止日期</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        <div style="padding:16px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;">
          <p style="font-size:12px;color:#9ca3af;margin:0;">
            数据来源于公开招聘信息 · 仅供参考 · 如需退订请联系管理员
          </p>
        </div>
      </div>
    </body>
    </html>"""


def send_daily_digest(new_notices):
    """
    发送每日新公告推送邮件。
    new_notices: 本次新入库且未过期的公告列表。
    """
    if not new_notices:
        log.info("无新公告，跳过邮件推送")
        return True

    if not SMTP_USER or not ADMIN_EMAIL:
        log.warning("SMTP 配置不完整（SMTP_USER/ADMIN_EMAIL 未设置），跳过邮件推送")
        return False

    subject = f"广东考编情报站 · {len(new_notices)} 条新公告 · {datetime.now().strftime('%m-%d')}"
    html_body = _build_html(new_notices)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ADMIN_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [ADMIN_EMAIL], msg.as_string())
        server.quit()
        log.info("邮件推送成功：%s -> %s（%d 条公告）", SMTP_USER, ADMIN_EMAIL, len(new_notices))
        return True
    except Exception as e:
        log.error("邮件推送失败: %s", e)
        return False
