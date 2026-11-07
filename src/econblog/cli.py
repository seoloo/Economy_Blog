"""명령행 진입점.

    python -m econblog run                 # 실제 실행 (API 키 필요)
    python -m econblog run --dry-run       # 샘플 데이터로 전체 흐름 확인, 외부 호출 없음
    python -m econblog run --date 2026-11-06 --deliver local
    python -m econblog check-sources       # RSS 소스가 살아 있는지 점검
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone

from econblog.config import load_settings


def _cmd_run(args: argparse.Namespace) -> int:
    from econblog.pipeline import run

    settings = load_settings()
    methods = args.deliver.split(",") if args.deliver else (["local"] if args.dry_run else None)
    post = run(
        settings,
        run_date=date.fromisoformat(args.date) if args.date else None,
        offline=args.dry_run,
        deliver_methods=methods,
    )
    print(f"완료: {post.output_dir}")
    return 0


def _cmd_check_sources(args: argparse.Namespace) -> int:
    from econblog import registry
    from econblog.collect import COLLECTORS

    settings = load_settings()
    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    failed = 0
    for source in settings.sources:
        try:
            n = len(registry.load(COLLECTORS, source.collector)(settings).collect(source, since))
            print(f"OK   {source.id:<24} {n:>3}건")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {source.id:<24} {e}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="econblog")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="오늘 글 초안 생성")
    p_run.add_argument("--dry-run", action="store_true", help="샘플 데이터 사용, 외부 API 호출 없음")
    p_run.add_argument("--date", help="기준 날짜 YYYY-MM-DD (기본: 오늘, KST)")
    p_run.add_argument("--deliver", help="전달 방식 쉼표 구분 (예: local,email)")
    p_run.set_defaults(func=_cmd_run)

    p_chk = sub.add_parser("check-sources", help="RSS 소스 점검")
    p_chk.add_argument("--hours", type=int, default=72)
    p_chk.set_defaults(func=_cmd_check_sources)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "urllib3", "matplotlib", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
