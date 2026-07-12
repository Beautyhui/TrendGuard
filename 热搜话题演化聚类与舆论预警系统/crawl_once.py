"""
单次抓取微博热搜并追加写入 data/weibo_snapshots.csv。

用法（在项目根目录执行）：
  1. 设置环境变量 WEIBO_COOKIE（浏览器登录微博后复制 Cookie 整串）
  2. python crawl_once.py

定时累积：可配合系统「任务计划程序」每 30 分钟运行一次本脚本；
或长期跑定时循环：python -m src.weibo_loader
"""

from __future__ import annotations

from src.weibo_loader import DEFAULT_SNAPSHOT_CSV, append_snapshot_rows, fetch_weibo_top_once


def main() -> None:
    df = fetch_weibo_top_once()
    if df.empty:
        print("未抓取到数据。请先设置环境变量 WEIBO_COOKIE 后再运行。")
        return
    path = append_snapshot_rows(df)
    print(f"已追加 {len(df)} 条 -> {path}")


if __name__ == "__main__":
    main()
