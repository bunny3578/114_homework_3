import re
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

SEARCH_URL = "https://search.books.com.tw/search/query/key/LLM/cat/BKA"


def extract_price_int(text: str) -> int:
    if not text:
        return 0
    nums = re.findall(r"\d+", str(text))  # 找出所有連續數字
    if not nums:
        return 0
    try:
        return int(nums[-1])  # 最後一段通常是實際價格
    except ValueError:
        return 0


# 新增：統一取得下一頁按鈕的輔助函式
def find_next_button(driver, wait):
    selectors = [
        # 優先：href 不是 javascript 的下一頁按鈕
        (By.CSS_SELECTOR, "a.next[rel='change_page'][href]:not([href^='javascript'])"),
        (By.CSS_SELECTOR, "div.page a.next[href]:not([href^='javascript'])"),
        (
            By.XPATH,
            "//div[contains(@class,'page')]//a[contains(@class,'next') and not(starts-with(@href,'javascript'))]",
        ),
        # 後備：原本的選擇器
        (By.CSS_SELECTOR, "a.next[rel='change_page']"),
        (By.CSS_SELECTOR, "div.page a.next"),
        (
            By.XPATH,
            "//div[contains(@class,'page')]//a[contains(@class,'next') or contains(normalize-space(.),'下一頁')]",
        ),
    ]
    for by, sel in selectors:
        try:
            btn = driver.find_element(by, sel)
            if not btn.is_displayed():
                continue
            wait.until(EC.element_to_be_clickable((by, sel)))
            return btn
        except Exception:
            continue
    return None  # 沒有下一頁


def scrape_books(
    headless: bool = True, delay: float = 1.5, max_pages: int | None = None
):
    """爬取所有結果頁面，回傳書籍列表，每筆包含 title/author/price/link。
    headless: 是否使用無頭模式；delay: 每頁抓取後的短暫等待秒數（防止過快）。
    max_pages: 測試用途，限制最多抓取的頁數（None 表示全部）。
    """
    # Selenium 啟動參數
    opts = Options()
    # 允許以環境變數指定 Chrome 可執行檔路徑（例如 CHROME 或 GOOGLE_CHROME_BIN）
    chrome_bin = os.environ.get("CHROME") or os.environ.get("GOOGLE_CHROME_BIN")
    if chrome_bin:
        opts.binary_location = chrome_bin

    # 封鎖瀏覽器層級的通知/權限與彈出視窗（盡量減少被蓋住的情況）
    opts.add_argument("--disable-notifications")
    opts.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.notifications": 2,  # 封鎖通知
            "profile.default_content_setting_values.geolocation": 2,  # 封鎖定位權限
            "profile.default_content_setting_values.media_stream": 2,  # 封鎖相機/麥克風權限
            "profile.default_content_settings.popups": 0,  # 0=封鎖彈出視窗 (舊版鍵)
            "profile.managed_default_content_settings.popups": 2,  # 2=封鎖彈出視窗 (新版鍵)
        },
    )

    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")  # 確保桌面版版面會顯示分頁

    # 關閉自動化提示 (例如 "Chrome is being controlled by...")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # 若設定了 CHROMEDRIVER，則使用指定的 driver；否則交由 Selenium Manager 自動處理
    driver_path = os.environ.get("CHROMEDRIVER")
    if driver_path:
        driver = webdriver.Chrome(service=Service(driver_path), options=opts)
    else:
        driver = webdriver.Chrome(options=opts)

    # 加上 User-Agent 模擬真人瀏覽器
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        },
    )

    books = []
    # 統計資訊
    skipped_no_title = 0
    missing_author = 0
    missing_price = 0
    popup_closed_count = 0
    next_not_found_count = 0

    try:
        driver.get(SEARCH_URL)
        wait = WebDriverWait(driver, 10)
        short_wait = WebDriverWait(driver, 2)
        page = 1
        # 分頁偵測
        total_pages = None
        try:
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "select#page_select"))
            )
            select = driver.find_element(By.CSS_SELECTOR, "select#page_select")
            options = select.find_elements(By.TAG_NAME, "option")
            if options:
                first_text = options[0].text.strip()
                match = re.search(r"共\s*(\d+)\s*頁", first_text)
                if match:
                    total_pages = int(match.group(1))
        except Exception:
            pass
        if not total_pages:
            try:
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.page"))
                )
                page_links = driver.find_elements(By.CSS_SELECTOR, "div.page a")
                nums = [int(a.text) for a in page_links if a.text.isdigit()]
                if nums:
                    total_pages = max(nums)
            except Exception:
                pass
        if total_pages:
            print(f"偵測到總共有 {total_pages} 頁。")
        else:
            print("偵測不到總頁數，將逐頁嘗試…")

        while True:
            # 進度輸出（避免冗長 URL 與每頁筆數）
            if total_pages:
                print(f"正在爬取第 {page} / {total_pages} 頁...")
            else:
                print(f"正在爬取第 {page} 頁...")
            # 等待包含書籍的容器出現
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.table-searchbox"))
            )
            container = driver.find_element(By.CSS_SELECTOR, "div.table-searchbox")
            items = container.find_elements(
                By.XPATH, ".//div[contains(@class,'table-td')][.//h4//a]"
            )

            if not items:
                break

            added_this_page = 0
            for it in items:
                # 書名與連結
                try:
                    a = it.find_element(By.CSS_SELECTOR, "h4 a")
                    title = a.text.strip()
                    link = a.get_attribute("href") or ""
                except Exception:
                    title = ""
                    link = ""

                # 作者（可能多個 a）
                author = "N/A"
                try:
                    author_links = it.find_elements(By.CSS_SELECTOR, "p.author a")
                    text_joined = ",".join(
                        x.text.strip() for x in author_links if x.text.strip()
                    )
                    if text_joined:
                        author = text_joined
                except Exception:
                    pass
                if author == "N/A":
                    missing_author += 1

                # 價格：優先從包含「元/折」的區塊擷取數字
                price = 0
                try:
                    price_text = ""
                    for sel in [
                        "li.price_a",
                        "li.price",
                        "p.price",
                        "div.price",
                        "ul.price",
                    ]:
                        try:
                            t = it.find_element(By.CSS_SELECTOR, sel).text
                            if ("元" in t) or ("折" in t):
                                price_text = t
                                break
                        except Exception:
                            continue
                    if not price_text:
                        # 從各行文字中找包含「元/折」
                        for line in (it.text or "").splitlines():
                            if ("元" in line) or ("折" in line):
                                price_text = line
                                break
                    price = extract_price_int(price_text) if price_text else 0
                except Exception:
                    price = 0
                if price == 0:
                    missing_price += 1

                if title:  # 沒有書名就略過
                    books.append(
                        {
                            "title": title,
                            "author": author,
                            "price": price,
                            "link": link,
                        }
                    )
                    added_this_page += 1
                else:
                    skipped_no_title += 1

            if max_pages is not None and page >= max_pages:
                break
            # 關閉彈窗
            popup_selectors = [
                "a.box_close",
                "div.popup-close",
                "button.close",
                "button[aria-label='Close']",
                "div[class*='popup'] button[class*='close']",
            ]
            for sel in popup_selectors:
                try:
                    close_btn = short_wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    close_btn.click()
                    time.sleep(0.2)
                    popup_closed_count += 1
                    break
                except Exception:
                    continue
            # 下一頁
            next_btn = find_next_button(driver, wait)
            if not next_btn:
                print(f"找不到下一頁按鈕，爬取結束（停在第 {page} 頁）。")
                break
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", next_btn
                )
                time.sleep(0.1)
            except Exception:
                pass
            href = next_btn.get_attribute("href") or ""
            if not href or href.startswith("javascript"):
                print(f"下一頁按鈕無有效連結，爬取結束（停在第 {page} 頁）。")
                break
            driver.get(href)
            try:
                wait.until(
                    EC.any_of(
                        EC.staleness_of(container), EC.url_changes(driver.current_url)
                    )
                )
            except Exception:
                pass
            time.sleep(delay)
            page += 1
        print("爬取完成。")
    finally:
        driver.quit()

    return books


if __name__ == "__main__":
    print("正在以非無頭模式 (headless=False) 測試爬蟲...")
    # 測試時建議 headless=False 才能親眼看到彈出視窗被關閉
    data = scrape_books(headless=False, delay=1.0)
    print(f"\n爬取完畢，共抓到 {len(data)} 筆資料。")
