"""UI tests for the vanilla single-file app.html."""
APP = "file:///C:/Users/Art/ArtWebStudio/artweb-studio/app.html"


def test_catalog(page):
    page.goto(APP + "#catalog", wait_until="domcontentloaded")
    page.wait_for_selector(".mcard", timeout=25000)
    assert page.locator(".navitem").count() == 11
    assert page.locator(".mcard").count() >= 20


def test_about(page):
    page.goto(APP + "#about", wait_until="domcontentloaded")
    page.wait_for_selector("#view-dynamic.active", timeout=15000)
    assert "github.com/Yury197812/portable-os" in page.content()


def test_compare_openrouter_data(page):
    page.goto(APP + "#compare", wait_until="domcontentloaded")
    page.wait_for_selector("#ordata-a .kv", timeout=30000)
    assert page.locator("#ordata-a .kv").count() >= 4


def test_reviews_submit_delete(page):
    page.goto(APP + "#compare", wait_until="domcontentloaded")
    page.wait_for_selector('[data-stars="a"]', timeout=20000)
    page.click('[data-stars="a"][data-n="5"]')
    page.fill("#author-a", "pytest")
    page.fill("#text-a", "automated review")
    page.click("#send-a")
    page.wait_for_selector("#revlist-a .review", timeout=15000)
    assert page.locator("#revlist-a .review").count() == 1
    assert page.locator("#revlist-a .review .rev-del").count() == 1
    page.click("#revlist-a .review .rev-del")
    page.wait_for_timeout(1200)
    assert page.locator("#revlist-a .review").count() == 0


def test_hash_navigation(page):
    page.goto(APP, wait_until="domcontentloaded")
    page.wait_for_selector(".mcard", timeout=25000)
    page.click('[data-id="routing"]')
    page.wait_for_selector(".slider", timeout=15000)
    assert page.locator(".slider").count() == 8
