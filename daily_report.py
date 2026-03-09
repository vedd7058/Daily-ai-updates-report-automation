"""
daily_report.py
───────────────
Fetches live AI news via Tavily Search, generates a 360° report
using Groq (Llama 3.3 70B), and delivers it via Gmail + WhatsApp (Twilio).

Triggered daily at 7 PM IST by GitHub Actions.
Both APIs are 100% free. No credit card needed.

SECRETS NEEDED IN GITHUB:
  GROQ_API_KEY        → https://console.groq.com
  TAVILY_API_KEY      → https://app.tavily.com
  GMAIL_SENDER        → your Gmail address
  GMAIL_APP_PASSWORD  → https://myaccount.google.com/apppasswords
  GMAIL_RECIPIENT     → where to receive the report
  TWILIO_ACCOUNT_SID  → https://console.twilio.com
  TWILIO_AUTH_TOKEN   → https://console.twilio.com
  TWILIO_FROM         → whatsapp:+14155238886
  TWILIO_TO           → whatsapp:+91XXXXXXXXXX
"""

import os
import smtplib
import json
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
TWILIO_ACCOUNT_SID  = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN   = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM         = os.environ["TWILIO_FROM"]
TWILIO_TO           = os.environ["TWILIO_TO"]

GROQ_MODEL = "llama-3.3-70b-versatile"

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

def fetch_news():
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    all_results = []
    for query in SEARCH_QUERIES:
        print(f"[{now_ist()}] Searching: {query}")
        try:
            response = tavily.search(
                query=query,
                search_depth="basic",
                max_results=3,
                include_answer=True,
            )
            if response.get("answer"):
                all_results.append(f"TOPIC: {query}\nSUMMARY: {response['answer']}")
            for r in response.get("results", []):
                title   = r.get("title", "")
                content = r.get("content", "")[:300]
                url     = r.get("url", "")
                all_results.append(f"- {title}: {content} ({url})")
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

def markdown_to_html(text):
    html_lines = []
    in_ul = False
    for line in text.splitlines():
        if line.startswith("## "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h2 style='color:#16213e;border-bottom:2px solid #0f3460;padding-bottom:4px;margin-top:28px'>{line[3:]}</h2>")
        elif line.startswith("# "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h1 style='color:#1a1a2e'>{line[2:]}</h1>")
        elif line.startswith("### "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h3 style='color:#0f3460'>{line[4:]}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_ul: html_lines.append("<ul>"); in_ul = True
            item = line[2:].replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html_lines.append(f"<li style='margin:5px 0'>{item}</li>")
        elif line.strip() == "":
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append("<br>")
        else:
            if in_ul: html_lines.append("</ul>"); in_ul = False
            para = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html_lines.append(f"<p style='margin:6px 0'>{para}</p>")
    if in_ul:
        html_lines.append("</ul>")
    return "\n".join(html_lines)

def make_whatsapp_summary(full_report):
    lines = [l.strip() for l in full_report.splitlines() if l.strip()]
    summary_lines = [
        "📋 *360° AI Daily Intelligence Report*",
        f"🗓 _{now_ist()}_",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    current_section = ""
    count = 0
    for line in lines:
        if line.startswith("## "):
            current_section = line[3:].strip()
            count = 0
        elif current_section and count == 0 and not line.startswith("#"):
            clean = line.replace("**", "*")
            summary_lines.append(f"*{current_section}*")
            summary_lines.append(clean[:140] + ("..." if len(clean) > 140 else ""))
            summary_lines.append("")
            count += 1
    summary_lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        "📧 Full report in your Gmail inbox.",
    ]
    return "\n".join(summary_lines)

def send_gmail(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = GMAIL_RECIPIENT
    msg.attach(MIMEText(body, "plain"))
    html_body = markdown_to_html(body)
    full_html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:820px;margin:auto;
                 padding:24px;color:#222;background:#f4f4f4;">
      <div style="background:#fff;border-radius:10px;padding:28px;
                  box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);
                    color:white;padding:18px 22px;border-radius:8px;margin-bottom:28px;">
          <h1 style="margin:0;font-size:22px;">📋 360° AI Daily Intelligence Report</h1>
          <p style="margin:6px 0 0;opacity:0.75;font-size:13px;">{now_ist()}</p>
        </div>
        {html_body}
        <hr style="margin-top:36px;border:none;border-top:1px solid #eee;">
        <p style="font-size:11px;color:#aaa;text-align:center;margin-top:12px;">
          Powered by Groq Llama 3.3 70B · Tavily Search · GitHub Actions
        </p>
      </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(full_html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, GMAIL_RECIPIENT, msg.as_string())
    print(f"[{now_ist()}] Gmail sent to {GMAIL_RECIPIENT}")

def send_whatsapp(message):
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    msg = client.messages.create(
        from_=TWILIO_FROM,
        to=TWILIO_TO,
        body=message,
    )
    print(f"[{now_ist()}] WhatsApp sent. SID: {msg.sid}")

def main():
    print(f"[{now_ist()}] Starting daily report job...")
    today = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%A, %d %B %Y")
    news_context = fetch_news()
    report = generate_report(news_context, today)
    date_str = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y")
    send_gmail(f"360 AI Daily Report - {date_str}", report)
    summary = make_whatsapp_summary(report)
    send_whatsapp(summary)
    print(f"[{now_ist()}] All done!")

if __name__ == "__main__":
    main()
