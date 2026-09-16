import re
import sqlite3

def is_auto_reply(subject: str, body: str, sender_name: str = '', sender_email: str = '') -> bool:
    subj_low = (subject or '').lower()
    body_low = (body or '').lower()
    name_low = (sender_name or '').lower()
    email_low = (sender_email or '').lower()

    # Senders / Names indicating bot/support/ticket systems
    bot_names = [
        'поддержк', 'support', 'helpdesk', 'service desk', 'служба заботы', 
        'бот', 'bot', 'информационная служба', 'robot', 'noreply', 'no-reply', 'ticket'
    ]
    if any(bn in name_low or bn in email_low for bn in bot_names):
        # If it comes from a support/bot desk, check if it's automated ticket creation
        if any(w in subj_low or w in body_low for w in [
            'обращени', 'заявк', 'тикет', 'ticket', 'получен', 'принят', 'зарегистрирован', 
            'спешит на помощь', 'в порядке очереди', 'вернёмся с ответом', 'номер'
        ]):
            return True

    # Subject keywords
    subj_patterns = [
        'автоматический ответ', 'автоответ', 'automatic reply', 'auto-reply', 'auto reply',
        'out of office', 'в отпуске', 'ваше обращение', 'обращение принято', 'обращение [',
        'обращение #', 'заявка принята', 'заявка [', 'заявка №', 'запрос получен', 
        'мы получили ваше письмо', 'получили запрос', 'ваше письмо получено', 'ticket-',
        '[#', '[заявка'
    ]
    if any(p in subj_low for p in subj_patterns):
        return True

    # Body keywords
    body_patterns = [
        'автоматический ответ', 'автоматическое уведомление', 'это письмо отправлено автоматически',
        'робот', 'я бот', 'ваше обращение зарегистрировано', 'зарегистрирована заявка',
        'зарегистрирован инцидент', 'зарегистрировано под номером', 'присвоен номер #',
        'принято в обработку', 'дождитесь ответа менеджера', 'наш менеджер свяжется с вами',
        'специалист службы поддержки ответит', 'вернёмся с ответом в течение',
        'нахожусь в отпуске', 'в отпуске до', 'out of the office', 'out of office',
        'служба заботы о клиентах получила', 'вы обратились в службу поддержки',
        'вы обратились в техническую службу', 'команда техподдержки', 'зарегистрировано в пао',
        'необходимая информация от вас получена', 'для сокращения времени обработки обращений',
        'наш менеджер свяжется с вами в ближайшее время', 'спасибо за обращение! оно будет рассмотрено'
    ]
    if any(p in body_low for p in body_patterns):
        return True

    return False

con = sqlite3.connect('data/aipoisk.db')
cur = con.cursor()
cur.execute('''
SELECT i.id, i.sender_email, i.sender_name, l.company_name, i.subject, i.body_text
FROM outreach_inbox i 
JOIN outreach_leads l ON l.id = i.lead_id 
WHERE l.task_id LIKE 'task-ten%' AND i.category != 'bounce'
ORDER BY i.date_received DESC
''')
rows = cur.fetchall()
print(f'Testing on {len(rows)} messages:')
auto_count = 0
human_count = 0
for idx, r in enumerate(rows, 1):
    mid, s_email, s_name, comp, subj, body = r
    auto = is_auto_reply(subj, body, s_name, s_email)
    if auto:
        auto_count += 1
        label = '🟡 АВТООТВЕТ'
    else:
        human_count += 1
        label = '🟢 ЖИВОЙ ОТВЕТ'
    print(f'{idx}. {label} | {s_email} ({s_name}) | Subj: {subj[:40]}')
    if not auto:
        print(f'    Body snippet: {repr(body[:150])}')

print(f'\nResult: Auto-replies = {auto_count}, Human replies = {human_count}')
