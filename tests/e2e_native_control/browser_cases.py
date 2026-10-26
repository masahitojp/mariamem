"""Real browser actions; one intentional assertion failure is assessed by the parent."""
import os
from playwright.sync_api import expect


def test_01_commit_order(browser_page):
    page=browser_page
    page.get_by_label('SKU',exact=True).fill('ORDER-A')
    page.get_by_label('Quantity',exact=True).fill('3')
    page.get_by_role('button',name='Save',exact=True).click()
    expect(page.get_by_text('Order created',exact=True)).to_be_visible()
    expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready','ORDER-A:3:ready'])


def test_02_fail_after_commit(browser_page):
    page=browser_page
    page.get_by_label('SKU',exact=True).fill('FAILED-A')
    page.get_by_label('Quantity',exact=True).fill('4')
    page.get_by_role('button',name='Save',exact=True).click()
    expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready','FAILED-A:4:ready'])
    if os.environ.get('E2E_INJECT_FAILURE')=='1':
        raise AssertionError('E2E_EXPECTED_FAILURE_AFTER_COMMIT')


def test_03_next_case_sees_only_baseline(browser_page):
    expect(browser_page.get_by_test_id('order')).to_have_text(['SEED:2:ready'])
