# AGENTS.md

이 레포에서 작업하는 모든 AI 에이전트(Claude Code, Codex 등)가 따라야 하는 규칙입니다.

## 프로젝트 개요

국내·해외 경제 뉴스와 블로그를 참고해 **매일 시황/이슈 정리 글 초안과 차트**를 자동으로 만드는 파이프라인입니다.
발행처는 티스토리이며, 티스토리 Open API가 종료되어 **최종 게시는 사람이 검토 후 직접** 합니다.

```
수집(RSS) → 분류·중복제거(Laya) → 시장 데이터 수집 → 차트 생성 → 초안 작성(Claude) → 저작권 검사 → HTML 렌더링 → 메일 발송
```

## Git 규칙

### 커밋·푸시
- 의미 있는 작업 단위가 끝나면 **묻지 말고 바로 커밋하고 `origin main`에 푸시**한다.
- 커밋 전 `pytest`가 통과해야 한다. 실패하면 고친 뒤 커밋한다.

### 작성자
- 커밋 작성자(author)와 커미터(committer)는 레포 소유자(`seoloo`) 한 명뿐이다. 로컬 `git config` 값을 그대로 쓰고 바꾸지 않는다.
- **에이전트를 기여자로 남기지 않는다.**
  - `Co-Authored-By:` 트레일러를 넣지 않는다.
  - "Generated with Claude Code" 같은 문구, 🤖 이모지, 에이전트 이름을 커밋 메시지와 PR 본문에 넣지 않는다.
  - 이 규칙은 에이전트 도구의 기본 attribution 설정보다 우선한다.

### 커밋 제목
현업 개발자가 실제로 쓰는 형태로 쓴다.
- 한국어 한 줄로, 50자 안팎으로 쓴다.
- `feat:`, `fix:`, `chore:` 같은 **영어 접두어를 붙이지 않는다.**
- 좋은 예:
  - `해외 뉴스 RSS 소스 추가`
  - `주말에 환율 데이터가 비면 차트 생성이 실패하던 문제 수정`
  - `의존성 버전 고정`
- 나쁜 예:
  - `feat: 해외 뉴스 RSS 소스 추가` (영어 접두어)
  - `Implement comprehensive news collection pipeline with robust error handling` (과장되고 장황함)
  - `✨ Add feature` (이모지)
  - `Update files` (내용 없음)
- 본문은 필요할 때만, 무엇을 왜 바꿨는지 2~3줄로 쓴다.
- 한 커밋에는 한 가지 목적만 담는다.

## 코드 구조: 스켈레톤을 지킬 것

구조는 처음부터 확장을 전제로 설계했다. **디렉터리와 모듈 경계를 바꾸는 리팩터링은 하지 않는다.** 기능은 아래 위치에 끼워 넣는다.

```
config/
  settings.yaml        # 실행 설정 (모델명, 발송 방식, 차트 목록 등)
  sources.yaml         # 뉴스/블로그 RSS 목록 — 소스 추가는 여기만 수정
  series.yaml          # 시장 데이터 시리즈 정의 (provider + id)
  guides.yaml          # 경제 공부 글 주제 목록 (순서대로 자동 작성)
prompts/               # LLM 프롬프트 (코드에 프롬프트 하드코딩 금지)
templates/             # 티스토리용 HTML Jinja 템플릿
src/econblog/
  models.py            # 단계 간 주고받는 데이터 클래스 (계약)
  config.py            # YAML + 환경변수 로딩
  pipeline.py          # 단계 조립(오케스트레이션)만 담당
  cli.py               # 진입점: python -m econblog ...
  collect/             # 뉴스 수집기   (base.Collector 구현)
  classify/            # 기사 분류기   (base.Classifier 구현)
  market/              # 시장 데이터   (base.MarketDataProvider 구현)
  charts/              # 차트 생성     (base.ChartBuilder 구현)
  write/               # 초안 작성기   (base.Writer 구현)
  guard/               # 저작권(원문 복사) 검사
  render/              # Draft → HTML
  deliver/             # 결과 전달     (base.Deliverer 구현)
tests/
.github/workflows/daily.yml
```

확장 규칙:
- **새 뉴스 소스**는 `config/sources.yaml`에 한 줄만 추가한다. RSS가 없는 사이트만 `collect/`에 새 Collector를 만든다.
- **새 데이터 시리즈**는 `config/series.yaml`에 추가한다. 새 데이터 출처가 필요할 때만 `market/`에 Provider를 만든다.
- **새 경제 공부 주제**는 `config/guides.yaml` 맨 아래에 추가한다. 기존 항목 순서를 바꾸면 자동 실행 순서가 바뀐다.
- **티스토리 HTML**은 `templates/_tistory.html.j2`의 공통 부품만 쓴다. 티스토리 편집기가 지우는 스타일(margin·padding·border·font-size 등)과 `thead/th`는 쓰지 않는다.
- **대표 이미지(썸네일)**는 카테고리별 고정 그림(`assets/brand/thumb_*.jpg`)을 쓴다. 새 카테고리나 그림 교체는 `assets/brand/make_thumbnails.py`로 만들고, 글 종류와의 연결은 `settings.yaml`의 `thumbnails`에 둔다.
- **새 차트**는 `charts/`에 ChartBuilder를 만들고 `charts/__init__.py`의 레지스트리에 등록한 뒤 `settings.yaml`에서 켠다.
- **새 발송 방식**(예: 슬랙)은 `deliver/`에 Deliverer를 추가한다.
- 단계 간 데이터는 반드시 `models.py`의 데이터 클래스로 주고받는다. dict를 그대로 넘기지 않는다.
- 외부 API 키가 없으면 각 단계는 **오프라인 대체 구현으로 동작**해야 한다. 예: Laya가 없으면 키워드 분류기, 메일 설정이 없으면 로컬 파일 저장. 그래야 테스트와 dry run이 가능하다.

## 저작권 규칙 (반드시 지킬 것)

- 기사 **원문 전체를 저장하거나 커밋하지 않는다.** RSS의 제목, 요약, 링크만 메모리에서 쓴다.
- `output/`, `data/cache/`는 `.gitignore` 대상이다. 수집물과 초안은 레포에 올리지 않는다.
- 이미지나 차트를 외부에서 가져오지 않는다. **차트는 공개 데이터로 직접 그린다.** 출처는 차트 하단에 표기한다.
  - 예외: **인스타 카드 배경 사진**에 한해 상업적 사용·수정이 허용된 무료 사진(Pexels 라이선스)을 쓸 수 있다. 사진 출처는 캡션에 적는다. 뉴스 보도사진, 남의 게시물 이미지, 로고는 쓰지 않는다. 블로그 글에는 여전히 외부 이미지를 넣지 않는다.
- LLM 프롬프트는 "출처 문장을 그대로 옮기지 말고 사실을 종합해 직접 분석하라"는 원칙을 유지한다.
- `guard/copyright.py` 검사를 통과하지 못한 초안은 경고를 붙여서 발송한다.
- 모든 글 하단에 참고 출처 링크와 "투자 권유 아님" 면책 문구를 넣는다.

## 비밀값

- API 키와 비밀번호는 GitHub Secrets 또는 로컬 `.env`에만 둔다. `.env`는 커밋하지 않는다. 필요한 키 목록은 `.env.example`에 있다.
- 로그에 키나 메일 주소를 출력하지 않는다.

## 개발 환경

- Python 3.11 이상 (GitHub Actions는 3.12)
- 설치: `pip install -e ".[dev]"`
- 테스트: `pytest`
- 오프라인 실행: `python -m econblog run --dry-run` (외부 API 호출 없이 샘플 데이터로 전체 흐름 확인)
