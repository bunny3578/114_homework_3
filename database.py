import sqlite3


# 連線工具：回傳可用欄位名稱取值的連線
def connect_db():
    """建立資料庫連線，並設定 row_factory 以便用欄位名稱存取。"""
    conn = sqlite3.connect("books.db")
    conn.row_factory = sqlite3.Row
    return conn


# [修正 1] 函式名稱應為 init_db (與 app.py 和下面的呼叫保持一致)
def init_db():
    sql_command = """
    CREATE TABLE IF NOT EXISTS llm_books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        author TEXT,
        price INTEGER,
        link TEXT
    );
    """

    with connect_db() as conn:
        # 建立主資料表
        conn.execute(sql_command)

        # 建立索引以提升查詢效能
        conn.execute("CREATE INDEX IF NOT EXISTS idx_author ON llm_books (author);")

    print("資料庫初始化完成。")


def bulk_insert(books):
    """
    使用 executemany() 高效能批次插入資料。
    回傳實際新插入資料庫的筆數。
    """
    processed_books = []
    for b in books:
        title = (b.get("title") or "").strip()
        author = (b.get("author") or "N/A").strip()
        try:
            price = int(b.get("price", 0) or 0)
        except (TypeError, ValueError):
            price = 0
        link = (b.get("link") or "").strip()

        # 僅加入有書名的資料
        if title:
            processed_books.append((title, author, price, link))

    if not processed_books:
        return 0

    sql = "INSERT OR IGNORE INTO llm_books (title, author, price, link) VALUES (?, ?, ?, ?)"

    with connect_db() as conn:
        #  取得插入前的筆數
        cur = conn.execute("SELECT COUNT(*) FROM llm_books")
        before_count = cur.fetchone()[0]

        #  一次性批次執行
        conn.executemany(sql, processed_books)

        # 取得插入後的筆數並計算差異
        cur = conn.execute("SELECT COUNT(*) FROM llm_books")
        after_count = cur.fetchone()[0]

        return after_count - before_count


# 模糊查詢：依書名
def query_title(keyword):
    """依書名模糊查詢 (LIKE)"""
    with connect_db() as conn:
        return conn.execute(
            "SELECT * FROM llm_books WHERE title LIKE ? ORDER BY id DESC",
            (f"%{keyword}%",),
        ).fetchall()


# 模糊查詢：依作者
def query_author(keyword):
    """依作者模糊查詢 (LIKE)"""
    with connect_db() as conn:
        return conn.execute(
            "SELECT * FROM llm_books WHERE author LIKE ? ORDER BY id DESC",
            (f"%{keyword}%",),
        ).fetchall()


def query_title_sorted_price(keyword):
    with connect_db() as conn:
        return conn.execute(
            "SELECT * FROM llm_books WHERE title LIKE ? ORDER BY price DESC, id DESC",
            (f"%{keyword}%",),
        ).fetchall()


def query_author_sorted_price(keyword):
    with connect_db() as conn:
        return conn.execute(
            "SELECT * FROM llm_books WHERE author LIKE ? ORDER BY price DESC, id DESC",
            (f"%{keyword}%",),
        ).fetchall()


# 統計筆數
def count_books():
    """回傳 llm_books 資料表的總筆數"""
    with connect_db() as conn:
        # fetchone()[0] 能直接取得 COUNT(*) 的數字
        return conn.execute("SELECT COUNT(*) FROM llm_books").fetchone()[0]


if __name__ == "__main__":
    init_db()
    # 顯示目前總筆數
    print(f"目前共有 {count_books()} 筆資料")
