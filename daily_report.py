"""
daily_report.py
───────────────
Fetches a 360° AI Daily Intelligence Report from Gemini 2.5 Flash
(with Google Search grounding) and delivers it via:
  • Gmail
  • WhatsApp (via Twilio)

Triggered daily at 7 PM IST by GitHub Actions.
All secrets are stored as GitHub repository secrets (never hardcoded).
"""

import os
import smtplib
import pytz
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

# ─── CONFIG (all pulled from GitHub Secrets → env vars) ──────────────────────

GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
GMAIL_SENDER        = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD  = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_RECIPIENT     = os.environ["GMAIL_RECIPIENT"]
TWILIO_ACCOUNT_SID  = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN   = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM         = os.environ["TWILIO_FROM"]         # e.g. whatsapp:+14155238886
TWILIO_TO           = os.environ["TWILIO_TO"]           # e.g. whatsapp:+919876543210

MODEL = "gemini-2.5-flash-preview-04-17"

# ── 360° Daily Intelligence Report prompt ─────────────────────────────────────
DAILY_PROMPT = """
Act as a world-class AI research analyst and strategy consultant. Today's date is {today}.
Search the web for the most recent AI news from the last 24 hours, then produce a
'360-Degree AI Daily Intelligence Report.' Filter the noise — only the most high-leverage
information.

Structure the report as follows:

## 1. The 'Big Three' Breakthroughs
The most significant papers, model releases, or hardware advancements
(e.g., NVIDIA updates, OpenAI/Anthropic/Google releases).

## 2. The LLM & Open-Source Frontier
Developments in small language models (SLMs), fine-tuning techniques,
and the latest top-performing models on the Hugging Face Leaderboard.

## 3. Agents & Autonomy
Progress in autonomous agents, multi-agent workflows, and AI-to-software integration.

## 4. AI Business & Geopolitics
Major funding rounds, M&A activity, GPU supply chain shifts,
and global regulatory/policy changes.

## 5. Multi-Modal & Creative Tech
Advancements in Video, Audio, 3D, and Image generation ready for production use.

## 6. Prompt Engineering Updates
New discoveries in prompting logic (e.g., Chain-of-Thought breakthroughs,
specialized system prompts, or jailbreak mitigations) that improve output quality.

## 7. The 'Under-the-Radar' Tool
One specific, niche AI tool or library gaining traction among developers or power users.

## 8. Opportunity Synthesis
Based on these advancements, list 3 specific high-value opportunities:
- Arbitrage Opportunity: Where can I use new tools to do something faster/cheaper than others?
- Skill Pivot: What should I learn tonight to stay relevant based on today's news?
- Product/Service Idea: A gap in the market created by today's specific tech release.

Tone: Concise, technical but accessible, and hyper-focused on utility.
"""


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def now_ist() -> str:
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M IST")


def markdown_to_html(text: str) -> str:
    """Convert basic markdown to styled HTML for Gmail."""
    html_lines = []
    in_ul = False

    for line in text.splitlines():
        if line.startswith("## "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(
                f"<h2 style='color:#16213e;border-bottom:2px solid #0f3460;"
                f"padding-bottom:4px;margin-top:24px'>{line[3:]}</h2>"
            )
        elif line.startswith("# "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h1 style='color:#1a1a2e'>{line[2:]}</h1>")
        elif line.startswith("### "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h3 style='color:#0f3460'>{line[4:]}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_ul: html_lines.append("<ul>"); in_ul = True
            item = line[2:].replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html_lines.append(f"<li style='margin:4px 0'>{item}</li>")
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


def make_whatsapp_summary(full_report: str) -> str:
    """
    Condense the full report into a punchy WhatsApp message.
    WhatsApp via Twilio supports up to 1600 chars.
    Pulls the first content line from each section.
    """
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
            summary_lines.append(clean[:140] + ("…" if len(clean) > 140 else ""))
            summary_lines.append("")
            count += 1

    summary_lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        "📧 Full report in your Gmail inbox.",
    ]
    return "\n".join(summary_lines)


# ─── DELIVERY FUNCTIONS ───────────────────────────────────────────────────────

def call_gemini_with_search(prompt: str) -> str:
    """Call Gemini 2.5 Flash with Google Search grounding."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"[{now_ist()}] 🌐 Gemini is searching Google for today's AI news...")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.7,
            max_output_tokens=4096,
        ),
    )
    print(f"[{now_ist()}] ✅ Report generated ({len(response.text)} chars).")
    return response.text


def send_gmail(subject: str, body: str) -> None:
    """Send the full report as a styled HTML email."""
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
          Generated by Gemini 2.5 Flash · Google Search Grounding · GitHub Actions
        </p>
      </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(full_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, GMAIL_RECIPIENT, msg.as_string())

    print(f"[{now_ist()}] 📧 Gmail sent to {GMAIL_RECIPIENT}")


def send_whatsapp(message: str) -> None:
    """Send a WhatsApp message via Twilio."""
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    msg = client.messages.create(
        from_=TWILIO_FROM,
        to=TWILIO_TO,
        body=message,
    )
    print(f"[{now_ist()}] 💬 WhatsApp sent. SID: {msg.sid}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{now_ist()}] 🔄 Starting daily report job...")

    today  = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%A, %d %B %Y")
    prompt = DAILY_PROMPT.format(today=today)

    # 1. Generate report
    report = call_gemini_with_search(prompt)

    date_str = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y")

    # 2. Send full report to Gmail
    send_gmail(f"📋 360° AI Daily Report — {date_str}", report)

    # 3. Send summary to WhatsApp
    summary = make_whatsapp_summary(report)
    send_whatsapp(summary)

    print(f"[{now_ist()}] 🎉 All done!")


if __name__ == "__main__":
    main()
