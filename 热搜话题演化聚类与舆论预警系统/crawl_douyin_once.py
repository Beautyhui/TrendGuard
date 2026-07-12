"""单次抓取抖音热搜并追加到 data/douyin_snapshots.csv。项目根目录：python crawl_douyin_once.py"""

from __future__ import annotations

from src.douyin_hot import DEFAULT_DOUYIN_CSV, fetch_douyin_hot_once
from src.weibo_loader import append_snapshot_rows


def main() -> None:
    df = fetch_douyin_hot_once()
    if df.empty:
        print("未抓取到数据（可检查网络；若遇验证，设置 DOUYIN_COOKIE 后重试）。")
        return
    path = append_snapshot_rows(df, DEFAULT_DOUYIN_CSV)
    print(f"已追加 {len(df)} 条 -> {path}")


if __name__ == "__main__":
    main()
