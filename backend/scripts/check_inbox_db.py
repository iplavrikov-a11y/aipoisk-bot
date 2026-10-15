import sqlite3
import json

con = sqlite3.connect('data/aipoisk.db')
cur = con.cursor()

print("=== INBOX COUNTS BY CATEGORY & SPAM ===")
cur.execute("""
SELECT 
    category, 
    is_spam, 
    count(*) 
FROM outreach_inbox 
GROUP BY category, is_spam
""")
for row in cur.fetchall():
    print(row)

print("\n=== ALL INBOX MESSAGES WITH SENDER AND CATEGORY ===")
cur.execute("""
SELECT 
    i.id,
    i.sender_email,
    i.sender_name,
    i.subject,
    i.category,
    i.is_spam,
    i.is_read,
    l.company_name,
    l.status,
    i.body_text
FROM outreach_inbox i
LEFT JOIN outreach_leads l ON l.id = i.lead_id
ORDER BY i.date_received DESC
""")
messages = cur.fetchall()
print(f"Total inbox messages: {len(messages)}")

for m in messages:
    mid, s_email, s_name, subj, cat, is_spam, is_read, comp, l_status, body = m
    body_prev = (body or "").replace("\n", " ")[:120]
    print(f"[{cat.upper()}] (Spam:{is_spam}|Read:{is_read}) From: {s_email} | Name: {s_name} | Co: {comp}")
    print(f"   Subj: {subj}")
    print(f"   Body: {body_prev}")
    print("-" * 60)
