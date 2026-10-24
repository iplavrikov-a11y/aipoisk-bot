import pytest
from app import bot

@pytest.mark.parametrize('text,expected', [('Москва; 300',('Москва',300)),('Казань;10',('Казань',10)),('выкл',('',None))])
def test_delivery_command_input(text,expected):
    assert bot._parse_delivery_input(text,mode='supplier_search')==expected

@pytest.mark.parametrize('text', ['Москва', 'Москва;0','Москва;-1','Москва;5001','НеизвестныйГород;300','Москва;10.5'])
def test_delivery_command_rejects_invalid_input(text):
    with pytest.raises(ValueError):bot._parse_delivery_input(text,mode='supplier_search')


def test_geo_control_only_for_supported_pending_modes():
    for mode in ['supplier_search','analysis_and_suppliers','exact_product','procurement_report']:
        pending=bot.PendingBatch(telegram_id='fixture',mode=mode,files=[])
        callbacks=[b.callback_data for row in bot.batch_inline_keyboard(pending).inline_keyboard for b in row]
        assert ('batch:geo' in callbacks)==(mode in {'supplier_search','analysis_and_suppliers'})


def test_mode_switch_clears_hidden_geo():
    chat=-123456789
    try:
        bot.PENDING_GEO[chat]=('Казань',300)
        bot._select_scenario(chat,bot.SCENARIO_EXACT_PRODUCT)
        assert chat not in bot.PENDING_GEO
    finally:bot._clear_pending_state(chat)
