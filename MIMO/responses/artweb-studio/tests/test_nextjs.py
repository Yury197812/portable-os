"""UI tests for the Next.js app (artweb-next, http://localhost:3000)."""
NEXT = "http://localhost:3000"


def test_catalog(page):
    page.goto(NEXT + "/", wait_until="domcontentloaded")
    page.wait_for_selector(".mcard", timeout=20000)
    assert page.locator(".navitem").count() == 11
    assert page.locator(".mcard").count() >= 20


def test_routing_lab(page):
    page.goto(NEXT + "/routing", wait_until="domcontentloaded")
    page.wait_for_selector(".slider", timeout=20000)
    assert page.locator(".slider").count() == 8
    assert page.locator(".rankrow").count() == 5


def test_about(page):
    page.goto(NEXT + "/about", wait_until="domcontentloaded")
    page.wait_for_selector(".card", timeout=20000)
    assert "github.com/Yury197812/portable-os" in page.content()


def test_compare_structure(page):
    page.goto(NEXT + "/compare", wait_until="domcontentloaded")
    page.wait_for_selector(".cmp-select", timeout=20000)
    assert page.locator(".cmp-select").count() == 2
    assert page.locator(".rev-form").count() == 2


def test_sidebar_navigation(page):
    page.goto(NEXT + "/", wait_until="domcontentloaded")
    page.wait_for_selector(".navitem", timeout=20000)
    page.get_by_role("link", name="Skills Registry").click()
    page.wait_for_selector(".scard", timeout=20000)
    assert page.locator(".scard").count() >= 20


def test_compare_reviews_flow(page):
    page.goto(NEXT + "/compare", wait_until="domcontentloaded")
    page.wait_for_selector(".rev-form", timeout=20000)
    col = page.locator(".rev-col").nth(0)
    col.locator(".star-btn").nth(4).click()          # 5 stars
    col.locator(".rev-input").fill("pytest")
    col.locator(".rev-textarea").fill("automated review")
    col.locator(".btn").click()                       # submit
    page.wait_for_selector(".rev-col .review", timeout=15000)
    assert col.locator(".review").count() == 1
    col.locator(".review .x").first.click()           # delete
    page.wait_for_timeout(1200)
    assert col.locator(".review").count() == 0
