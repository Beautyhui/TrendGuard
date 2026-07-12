"""单次抓取 B 站搜索热搜并追加到 data/bilibili_snapshots.csv。项目根目录：python crawl_bilibili_once.py"""

from __future__ import annotations

from src.bilibili_hot import DEFAULT_BILIBILI_CSV, fetch_bilibili_hot_once
from src.weibo_loader import append_snapshot_rows


def main() -> None:
    df = fetch_bilibili_hot_once()
    if df.empty:
        print("未抓取到数据（可检查网络，或设置 BILIBILI_COOKIE 后重试）。")
        return
    path = append_snapshot_rows(df, DEFAULT_BILIBILI_CSV)
    print(f"已追加 {len(df)} 条 -> {path}")


if __name__ == "__main__":
    main()
