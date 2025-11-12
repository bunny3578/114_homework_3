import scraper
import database
import sqlite3  # 增加引入 sqlite3 以便捕捉 OperationalError


def main():
    # 程式一啟動就確保資料表已建立
    try:
        database.init_db()
    except sqlite3.OperationalError as e:
        print(f"資料庫連線失敗：{e}")
        print("請檢查 'books.db' 檔案是否被鎖定 (例如被 DB Browser 佔用)。")
        return  # 如果資料庫鎖定，直接退出程式

    while True:
        print("\n----- 博客來 LLM 書籍管理系統 -----")
        print("1. 更新書籍資料庫 ")
        print("2. 查詢書籍")
        print("3. 離開系統")
        choice = input("請選擇功能 (1-3): ").strip()

        if choice == "1":
            print("\n開始從網路爬取最新書籍資料...")
            try:
                # 執行爬蟲 (建議 headless=True 效能較好)
                books = scraper.scrape_books(headless=True, delay=0.5)

                # 批次寫入資料庫
                added = database.bulk_insert(books)
                total = database.count_books()

                print(
                    f"資料庫更新完成！共爬取 {len(books)} 筆資料，新增了 {added} 筆新書記錄。"
                )

            except sqlite3.OperationalError as e:
                print(f"\n[錯誤] 操作資料庫時發生錯誤：{e}")
                print("請確認 'books.db' 檔案是否被其他程式鎖定。")
            except Exception as e:
                print(f"\n[錯誤] 爬蟲執行失敗：{e}")
                print("請檢查網路連線或 Chrome 驅動程式 (chromedriver) 是否正常。")

        elif choice == "2":
            # --- 這是子選單 ---
            while True:
                print("\n--- 查詢書籍 ---")
                print("a. 依書名查詢")
                print("b. 依作者查詢")
                print("c. 返回主選單")
                sub = input("請選擇查詢方式 (a-c): ").strip().lower()

                results = []  # 先初始化

                if sub == "a":
                    keyword = input("請輸入關鍵字: ").strip()
                    results = database.query_title(keyword)

                elif sub == "b":
                    keyword = input("請輸入關鍵字: ").strip()
                    results = database.query_author(keyword)

                elif sub == "c":

                    break

                else:

                    print("無效選項，請重新輸入。")
                    continue

                if results:
                    print(
                        f"\n==================== (共 {len(results)} 筆相符的結果) ==="
                    )
                    for row in results:
                        print(
                            f"書名：{row['title']}\n作者：{row['author']}\n價格：{row['price']}\n---"
                        )
                    print("====================")
                else:

                    print("查無資料。")

        elif choice == "3" or choice.lower() in ("q", "quit"):
            print("已離開系統。")
            break
        else:
            print("選項無效，請重新輸入。")


if __name__ == "__main__":
    main()
