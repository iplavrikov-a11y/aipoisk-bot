import pytest
from app.outreach_mail import is_auto_reply_message, parse_bounce_info


def test_is_auto_reply_message_patterns():
    # Ticket support bot
    assert is_auto_reply_message(
        subject="[#8403217] Поиск производителей под спецификации",
        body_text="Здравствуйте! По Вашему обращению зарегистрирована заявка № 8403217. Специалист службы поддержки ответит Вам в ближайшее время.",
        sender_name="Служба поддержки",
        sender_email="gz86@krista.ru",
    ) is True

    # Bank automated receipt acknowledgement
    assert is_auto_reply_message(
        subject="Поиск производителей под спецификации",
        body_text="Добрый день! Ваше обращение зарегистрировано в ПАО «Промсвязьбанк» под номером #12345.",
        sender_name="broker@psbank.ru",
        sender_email="broker@psbank.ru",
    ) is True

    # Out of office
    assert is_auto_reply_message(
        subject="Automatic reply: Поиск производителей",
        body_text="Коллеги, с 24.08 по 28.08 нахожусь в отпуске.",
        sender_name="nbezrukov@lockobank.ru",
        sender_email="nbezrukov@lockobank.ru",
    ) is True

    # Bot
    assert is_auto_reply_message(
        subject="[#TICKET-2141707] Поиск производителей",
        body_text="Здравствуйте! Я бот Skillbox и учусь вместе с вами.",
        sender_name="Skillbox",
        sender_email="hello@skillbox.ru",
    ) is True

    # Normal human email
    assert is_auto_reply_message(
        subject="Re: Поиск производителей под спецификации и ТЗ",
        body_text="Здравствуйте! Наша компания готова поставить кабельную продукцию по вашему ТЗ. Прикрепляю коммерческое предложение и карточку предприятия.",
        sender_name="Иван Петров",
        sender_email="ivan@zavod-kabel.ru",
    ) is False


def test_smart_lead_matching():
    from app.outreach_mail import find_matched_lead_id

    email_map = {
        "mail@fin-direct.ru": "lead-1",
        "trukhan.tdtekhnologiya@bk.ru": "lead-2",
        "info@antey66.ru": "lead-3",
    }
    domain_map = {
        "fin-direct.ru": "lead-1",
        "tdtechnologia.ru": "lead-2",
        "antey66.ru": "lead-3",
    }

    # 1. Corporate domain match (sender o.sapojnikova@fin-direct.ru matched to lead mail@fin-direct.ru)
    matched = find_matched_lead_id(
        sender_email="o.sapojnikova@fin-direct.ru",
        sender_name="Ольга Сапожникова",
        subject="Re: Поиск производителей",
        body_text="Здравствуйте, нам интересен ваш сервис...",
        email_map=email_map,
        domain_map=domain_map,
    )
    assert matched == "lead-1"

    # 2. Quoted email match in body (sender ktkach@mail.ru forwarded/replied to email sent to trukhan.tdtekhnologiya@bk.ru)
    matched = find_matched_lead_id(
        sender_email="ktkach@mail.ru",
        sender_name="Kanstantsin Tkach",
        subject="Re: Поиск производителей",
        body_text="Не плохо, нужно Александре дать\n\nсреда, 26 августа от <trukhan.tdtekhnologiya@bk.ru>:\n> Здравствуйте!",
        email_map=email_map,
        domain_map=domain_map,
    )
    assert matched == "lead-2"

    # 3. URL match in signature (sender 2532385@mail.ru with antey66.ru in signature)
    matched = find_matched_lead_id(
        sender_email="2532385@mail.ru",
        sender_name="группа компаний Антей",
        subject="Re: Поиск производителей",
        body_text="Спасибо что обратились к нашему сервису! Сайт: https://antey66.ru/",
        email_map=email_map,
        domain_map=domain_map,
    )
    assert matched == "lead-3"

