"""依次抓取 B 站热搜与抖音热搜，分别写入各自 CSV。项目根目录：python crawl_bilibili_douyin_once.py"""

from __future__ import annotations

from src.bilibili_hot import DEFAULT_BILIBILI_CSV, fetch_bilibili_hot_once
from src.douyin_hot import DEFAULT_DOUYIN_CSV, fetch_douyin_hot_once
from src.weibo_loader import append_snapshot_rows


def main() -> None:
    b = fetch_bilibili_hot_once()
    if b.empty:
        print("B站：未抓取到数据")
    else:
        print(f"B站：已追加 {len(b)} 条 -> {append_snapshot_rows(b, DEFAULT_BILIBILI_CSV)}")

    d = fetch_douyin_hot_once()
    if d.empty:
        print("抖音：未抓取到数据")
    else:
        print(f"抖音：已追加 {len(d)} 条 -> {append_snapshot_rows(d, DEFAULT_DOUYIN_CSV)}")


if __name__ == "__main__":
    main()
