"""명령행 진입점.

    python -m econblog run                 # 실제 실행 (API 키 필요)
    python -m econblog run --dry-run       # 샘플 데이터로 전체 흐름 확인, 외부 호출 없음
    python -m econblog run --date 2026-11-06 --deliver local
    python -m econblog check-sources       # RSS 소스가 살아 있는지 점검
    python -m econblog guide --list        # 경제 공부 글 주제 목록과 오늘 차례
    python -m econblog guide --topic yield_curve --dry-run
    python -m econblog guide --scheduled   # 오늘이 자동 실행일이면 차례인 주제로 작성
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


def _cmd_guide(args: argparse.Namespace) -> int:
    """경제 공부 글 초안. --topic 으로 고르거나 --scheduled 로 오늘 차례 주제를 쓴다."""
    from econblog.pipeline import find_topic, pick_topic, run_guide, today

    settings = load_settings()
    run_date = date.fromisoformat(args.date) if args.date else today(settings)
    if args.list:
        current = pick_topic(settings, run_date)
        for i, t in enumerate(settings.guides):
            mark = "  ← 오늘 차례" if current and current.id == t.id else ""
            print(f"{i:>2}. {t.id:<16} {t.keyword}{mark}")
        return 0
    if args.topic:
        topic = find_topic(settings, args.topic)
    elif args.scheduled:
        topic = pick_topic(settings, run_date)
        if topic is None:
            print(f"{run_date}: 경제 공부 글 실행일이 아니거나 남은 주제가 없음")
            return 0
    else:
        print("--topic 아이디, --scheduled, --list 중 하나를 지정하세요")
        return 2
    methods = args.deliver.split(",") if args.deliver else (["local"] if args.dry_run else None)
    post = run_guide(settings, topic, run_date=run_date, offline=args.dry_run, deliver_methods=methods)
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


def _cmd_classify(args: argparse.Namespace) -> int:
    """수집·분류만 실행해 선택 결과를 확인한다. 글 작성·메일 발송은 하지 않는다."""
    from econblog.classify import classify_and_select
    from econblog.collect import collect_all

    settings = load_settings()
    since = datetime.now(timezone.utc) - timedelta(hours=settings.collect.lookback_hours)
    articles = collect_all(settings, since, offline=args.dry_run)
    selected = classify_and_select(settings, articles, offline=args.dry_run)
    print(f"수집 {len(articles)}건 → 선택 {len(selected)}건")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="econblog")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="오늘 글 초안 생성")
    p_run.add_argument("--dry-run", action="store_true", help="샘플 데이터 사용, 외부 API 호출 없음")
    p_run.add_argument("--date", help="기준 날짜 YYYY-MM-DD (기본: 오늘, KST)")
    p_run.add_argument("--deliver", help="전달 방식 쉼표 구분 (예: local,email)")
    p_run.set_defaults(func=_cmd_run)

    p_gd = sub.add_parser("guide", help="경제 공부 글 초안 생성")
    p_gd.add_argument("--topic", help="config/guides.yaml 의 주제 아이디")
    p_gd.add_argument("--scheduled", action="store_true", help="오늘이 자동 실행일이면 차례인 주제로 작성")
    p_gd.add_argument("--list", action="store_true", help="주제 목록과 오늘 차례 보기")
    p_gd.add_argument("--dry-run", action="store_true", help="샘플 데이터 사용, 외부 API 호출 없음")
    p_gd.add_argument("--date", help="기준 날짜 YYYY-MM-DD (기본: 오늘, KST)")
    p_gd.add_argument("--deliver", help="전달 방식 쉼표 구분 (예: local,email)")
    p_gd.set_defaults(func=_cmd_guide)

    p_cls = sub.add_parser("classify", help="수집·분류만 실행 (글 작성·발송 없음)")
    p_cls.add_argument("--dry-run", action="store_true")
    p_cls.set_defaults(func=_cmd_classify)

    p_chk = sub.add_parser("check-sources", help="RSS 소스 점검")
    p_chk.add_argument("--hours", type=int, default=72)
    p_chk.set_defaults(func=_cmd_check_sources)

    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
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
