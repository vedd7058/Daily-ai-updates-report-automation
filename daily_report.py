"""
daily_report.py
───────────────
Fetches live AI news via Tavily Search, generates a 360° report
using Groq (Llama 3.3 70B), and delivers it via Gmail + WhatsApp (Twilio).

Triggered daily at 7 PM IST by GitHub Actions.
Both APIs are 100% free. No credit card needed.
"""

import os
import smtplib
import pytz
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq
from tavily import TavilyClient
from twilio.rest import Client as TwilioClient

GROQ_API_KEY        = os.environ["GROQ_API_KEY"]
TAVILY_API_KEY      = os.environ["TAVILY_API_KEY"]
GMAIL_SENDER        = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD  = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_RECIPIENT     = os.environ["GMAIL_RECIPIENT"]
GMAIL_RECIPIENT_2   = os.environ["GMAIL_RECIPIENT_2"]
TWILIO_ACCOUNT_SID  = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN   = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM         = os.environ["TWILIO_FROM"]
TWILIO_TO           = os.environ["TWILIO_TO"]
TWILIO_TO_2         = os.environ["TWILIO_TO_2"]

GROQ_MODEL = "llama-3.3-70b-versatile"

SECTION_META = {
    "1": {"icon": "🚀", "color": "#FF6B6B", "bg": "#FFF5F5", "border": "#FF6B6B"},
    "2": {"icon": "🤖", "color": "#4ECDC4", "bg": "#F0FFFE", "border": "#4ECDC4"},
    "3": {"icon": "⚡", "color": "#45B7D1", "bg": "#F0F9FF", "border": "#45B7D1"},
    "4": {"icon": "💼", "color": "#96CEB4", "bg": "#F0FFF4", "border": "#96CEB4"},
    "5": {"icon": "🎨", "color": "#FFEAA7", "bg": "#FFFDF0", "border": "#F9CA24"},
    "6": {"icon": "🧠", "color": "#DDA0DD", "bg": "#FDF0FF", "border": "#DDA0DD"},
    "7": {"icon": "🔍", "color": "#F0A500", "bg": "#FFFBF0", "border": "#F0A500"},
    "8": {"icon": "💡", "color": "#6C5CE7", "bg": "#F5F0FF", "border": "#6C5CE7"},
}

SEARCH_QUERIES = [
    "AI model releases breakthroughs today 2026",
    "open source LLM Hugging Face leaderboard latest 2026",
    "AI agents autonomous workflows news 2026",
    "AI funding rounds acquisitions GPU policy 2026",
    "AI video audio image generation tools 2026",
    "prompt engineering chain of thought techniques 2026",
    "new AI developer tools libraries trending 2026",
]

REPORT_PROMPT = """
You are a world-class AI research analyst and strategy consultant.
Today's date is {today}.

Below is fresh news gathered from the web in the last 24 hours.
Use ONLY this news to write a 360-Degree AI Daily Intelligence Report.
Do not make anything up. If a section has no relevant news, say "Nothing significant today."

=== LIVE NEWS CONTEXT ===
{news_context}
=== END OF CONTEXT ===

Now write the full report using this exact structure:

## 1. The Big Three Breakthroughs
The most significant papers, model releases, or hardware advancements.

## 2. The LLM and Open-Source Frontier
Developments in small language models, fine-tuning techniques, and top Hugging Face models.

## 3. Agents and Autonomy
Progress in autonomous agents, multi-agent workflows, and AI-to-software integration.

## 4. AI Business and Geopolitics
Major funding rounds, M&A activity, GPU supply chain shifts, and regulatory changes.

## 5. Multi-Modal and Creative Tech
Advancements in Video, Audio, 3D, and Image generation ready for production use.

## 6. Prompt Engineering Updates
New discoveries in prompting logic that improve model output quality.

## 7. The Under-the-Radar Tool
One specific niche AI tool or library gaining traction among developers.

## 8. Opportunity Synthesis
- Arbitrage Opportunity: Where can I use new tools to do something faster or cheaper than others?
- Skill Pivot: What should I learn tonight to stay relevant based on today's news?
- Product/Service Idea: A gap in the market created by today's specific tech release.

Tone: Concise, technical but accessible, hyper-focused on utility.
"""

def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M IST")

def today_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%A, %d %B %Y")

def fetch_news():
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    all_results = []
    for query in SEARCH_QUERIES:
        print(f"[{now_ist()}] Searching: {query}")
        try:
            response = tavily.search(query=query, search_depth="basic", max_results=3, include_answer=True)
            if response.get("answer"):
                all_results.append(f"TOPIC: {query}\nSUMMARY: {response['answer']}")
            for r in response.get("results", []):
                all_results.append(f"- {r.get('title','')}: {r.get('content','')[:300]} ({r.get('url','')})")
            all_results.append("")
        except Exception as e:
            print(f"[{now_ist()}] Search failed for '{query}': {e}")
    return "\n".join(all_results)

def generate_report(news_context, today):
    client = Groq(api_key=GROQ_API_KEY)
    prompt = REPORT_PROMPT.format(today=today, news_context=news_context)
    print(f"[{now_ist()}] Generating report with Groq Llama 3.3 70B...")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
    )
    report = response.choices[0].message.content
    print(f"[{now_ist()}] Report generated ({len(report)} chars).")
    return report

def build_html_email(report_text, today):
    sections = []
    current_num, current_title, current_lines = None, "", []
    for line in report_text.splitlines():
        if line.startswith("## "):
            if current_num:
                sections.append((current_num, current_title, "\n".join(current_lines).strip()))
            heading = line[3:].strip()
            parts = heading.split(".", 1)
            current_num   = parts[0].strip() if len(parts) > 1 else "•"
            current_title = parts[1].strip() if len(parts) > 1 else heading
            current_lines = []
        else:
            current_lines.append(line)
    if current_num:
        sections.append((current_num, current_title, "\n".join(current_lines).strip()))

    def render_lines(text):
        html, in_ul = [], False
        for line in text.splitlines():
            s = line.strip()
            if not s:
                if in_ul: html.append("</ul>"); in_ul = False
                continue
            if s.startswith("- ") or s.startswith("* "):
                if not in_ul: html.append("<ul style='margin:8px 0;padding-left:20px;'>"); in_ul = True
                item = s[2:].replace("**", "<strong>", 1).replace("**", "</strong>", 1)
                html.append(f"<li style='margin:6px 0;color:#444;line-height:1.6;'>{item}</li>")
            else:
                if in_ul: html.append("</ul>"); in_ul = False
                para = s.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
                html.append(f"<p style='margin:8px 0;color:#333;line-height:1.7;'>{para}</p>")
        if in_ul: html.append("</ul>")
        return "\n".join(html)

    cards_html = ""
    for num, title, body in sections:
        meta = SECTION_META.get(num, {"icon": "📌", "color": "#888", "bg": "#F9F9F9", "border": "#ccc"})
        cards_html += f"""
        <div style="margin-bottom:20px;border-radius:12px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);border:1px solid {meta['border']}22;">
          <div style="background:{meta['color']};padding:12px 20px;">
            <span style="font-size:22px;margin-right:12px;">{meta['icon']}</span>
            <span style="font-size:10px;color:rgba(255,255,255,0.8);text-transform:uppercase;
                         letter-spacing:1px;font-weight:600;">Section {num}</span>
            <div style="font-size:15px;font-weight:700;color:#fff;margin-top:2px;">{title}</div>
          </div>
          <div style="background:{meta['bg']};padding:16px 20px;">{render_lines(body)}</div>
        </div>"""

    now = now_ist()
    pills = "".join([
        f'<span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:20px;'
        f'font-size:11px;font-weight:600;background:{SECTION_META[k]["color"]}22;'
        f'color:{SECTION_META[k]["color"]};border:1px solid {SECTION_META[k]["color"]}44;">'
        f'{SECTION_META[k]["icon"]} {label}</span>'
        for k, label in zip(
            ["1","2","3","4","5","6","7","8"],
            ["Breakthroughs","LLM Frontier","Agents","Business","Multi-Modal","Prompting","Hidden Tool","Opportunities"]
        )
    ])

    return f"""<!DOCTYPE html><html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#EAECF0;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#EAECF0;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">
  <tr><td>
    <div style="background:linear-gradient(135deg,#0F0C29,#302B63,#24243E);
                border-radius:16px 16px 0 0;padding:36px 32px 28px;text-align:center;">
      <div style="font-size:42px;margin-bottom:8px;">🛸</div>
      <h1 style="margin:0;font-size:26px;font-weight:800;color:#fff;letter-spacing:-0.5px;">
        360° AI Daily Intelligence Report
      </h1>
      <div style="margin:14px auto 0;display:inline-block;">
        <span style="display:inline-block;padding:5px 18px;
                     background:linear-gradient(90deg,#FF6B6B,#6C5CE7,#4ECDC4);
                     border-radius:30px;font-size:12px;font-weight:700;
                     color:#fff;letter-spacing:2px;text-transform:uppercase;
                     box-shadow:0 0 18px rgba(108,92,231,0.6);">
          ✦ &nbsp;by Vedant Bhise&nbsp; ✦
        </span>
      </div>
      <p style="margin:6px 0 0;color:rgba(255,255,255,0.5);font-size:12px;">
        {today} &nbsp;·&nbsp; {now}
      </p>
      <div style="margin-top:20px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#FF6B6B;margin:0 3px;"></span>
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#4ECDC4;margin:0 3px;"></span>
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#6C5CE7;margin:0 3px;"></span>
      </div>
    </div>
  </td></tr>
  <tr><td>
    <div style="background:#fff;padding:16px 20px;border-left:1px solid #e0e0e0;
                border-right:1px solid #e0e0e0;text-align:center;">
      <p style="margin:0 0 10px;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:1px;">Today's Sections</p>
      <div>{pills}</div>
    </div>
  </td></tr>
  <tr><td>
    <div style="background:#EAECF0;padding:20px 12px;">{cards_html}</div>
  </td></tr>
  <tr><td>
    <div style="background:linear-gradient(135deg,#0F0C29,#302B63);
                border-radius:0 0 16px 16px;padding:20px 32px;text-align:center;">
      <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.4);">
        Powered by <strong style="color:rgba(255,255,255,0.7);">Groq Llama 3.3 70B</strong> &nbsp;·&nbsp;
        <strong style="color:rgba(255,255,255,0.7);">Tavily Search</strong> &nbsp;·&nbsp;
        <strong style="color:rgba(255,255,255,0.7);">GitHub Actions</strong>
      </p>
      <p style="margin:6px 0 0;font-size:10px;color:rgba(255,255,255,0.25);">
        Delivered automatically every day at 7 PM IST
      </p>
    </div>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

def make_whatsapp_summary(full_report):
    lines = [l.strip() for l in full_report.splitlines() if l.strip()]
    summary_lines = ["📋 *360° AI Daily Intelligence Report*", f"🗓 _{now_ist()}_", "━━━━━━━━━━━━━━━━━━━━", ""]
    current_section, count = "", 0
    for line in lines:
        if line.startswith("## "):
            current_section = line[3:].strip(); count = 0
        elif current_section and count == 0 and not line.startswith("#"):
            clean = line.replace("**", "*")
            summary_lines += [f"*{current_section}*", clean[:140] + ("..." if len(clean) > 140 else ""), ""]
            count += 1
    summary_lines += ["━━━━━━━━━━━━━━━━━━━━", "📧 Full report in your Gmail inbox."]
    return "\n".join(summary_lines)

def send_gmail(subject, report_text, today):
    html = build_html_email(report_text, today)
    for recipient in [GMAIL_RECIPIENT, GMAIL_RECIPIENT_2]:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_SENDER
        msg["To"]      = recipient
        msg.attach(MIMEText(report_text, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, recipient, msg.as_string())
        print(f"[{now_ist()}] Gmail sent to {recipient}")

def send_whatsapp(message):
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    for number in [TWILIO_TO, TWILIO_TO_2]:
        msg = client.messages.create(from_=TWILIO_FROM, to=number, body=message)
        print(f"[{now_ist()}] WhatsApp sent to {number}. SID: {msg.sid}")

def main():
    print(f"[{now_ist()}] Starting daily report job...")
    today    = today_ist()
    news_ctx = fetch_news()
    report   = generate_report(news_ctx, today)
    date_str = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y")
    send_gmail(f"📋 360° AI Daily Report — {date_str}", report, today)
    send_whatsapp(make_whatsapp_summary(report))
    print(f"[{now_ist()}] All done!")

if __name__ == "__main__":
    main()
