"""Shared Playwright fixtures for ArtWeb Studio tests."""
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.set_default_timeout(60000)
    ctx.set_default_navigation_timeout(60000)
    pg = ctx.new_page()
    yield pg
    ctx.close()
