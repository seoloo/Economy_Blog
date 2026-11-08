# Economy_Blog

국내·해외 경제 뉴스와 블로그를 참고해 **화~토 아침 경제 시황 글 초안과 차트**를 만드는 파이프라인입니다.
일요일은 새 시장 데이터가 없어 쉽니다 (토요일 글이 금요일 미국·국내 장 마감을 다룸).
초안은 메일로 받고, 사람이 검토한 뒤 티스토리에 게시합니다.

```
RSS 수집 → Laya 분류·중복 제거 → 시장 데이터(yfinance·FRED·ECOS) → 차트 직접 생성
  → Claude 초안 작성 → 저작권(원문 복사) 검사 → HTML 렌더링 → 메일 발송
```

에이전트 작업 규칙과 코드 구조는 [AGENTS.md](AGENTS.md)에 있습니다.

## 화~토 아침에 하는 일 (약 10분)

1. 07시쯤 `[블로그 초안] 11/07 ...` 메일이 옵니다. 상단 「발행 전 확인」 상자를 먼저 봅니다.
2. 티스토리 글쓰기에서 편집기를 **HTML 모드**로 바꾸고, 첨부된 `post.html` 내용을 통째로 붙여넣습니다.
   차트와 대표 이미지는 공개 이미지 레포(`publish`)에 올라가 있어 붙여넣기 한 번으로 함께 들어갑니다.
   (`CHARTS_REPO_TOKEN`이 없으면 `[이미지 삽입]` 상자 자리에 첨부된 PNG를 직접 올립니다.)
3. 맨 위 그림을 대표 이미지로 지정하고, `[함께 보면 좋은 글]` 상자에 지난 글 링크를 넣습니다.
   본문은 티스토리 기본 편집기가 남기는 요소만 쓰므로(글자색·배경색·data-ke-size·인용 상자·표 tbody), 기본 모드로 돌아가도 모양이 유지됩니다.
4. 수치와 사실을 확인하고, 내 의견을 한두 문장 덧붙입니다. 메일의 제목과 태그를 넣고 발행합니다.

메일 제목에 `[검토 N건]`이 붙어 있으면 출처 문장과 겹치는 구간이나 데이터 누락이 있다는 뜻입니다. 반드시 고친 뒤 발행합니다.

## 경제 공부 글 (수·토, 오래 읽히는 글)

시황 글과 별도로, 경제 지표·개념을 쉽게 풀어 주는 글 초안이 **수·토 아침 8시쯤** `[블로그 초안·경제 공부]` 메일로 옵니다.
- 주제는 `config/guides.yaml` 순서대로 하나씩 씁니다 (장단기 금리차, 환율과 코스피, CPI, FOMC, VIX …).
- 대표 이미지(고정 썸네일), 우리 데이터로 그린 5년 차트, '지금 수치' 표(지금·1년 전·5년 범위)가 들어갑니다.
- 티스토리 카테고리는 '경제 공부'로 두고, 발행 방법은 시황 글과 같습니다. 예약 발행으로 원하는 날에 올려도 됩니다.
- 원하는 주제를 바로 만들려면 **Actions → daily-post → Run workflow**에서 `mode`를 `guide`, `topic`에 아이디(예: `vix`)를 넣고 실행합니다.
- 수동으로 몇 편을 먼저 만들었다면 `config/settings.yaml`의 `guide.start_index`를 그만큼 올려야 자동 실행이 같은 주제를 다시 쓰지 않습니다.

## 대표 이미지(썸네일)

같은 캐릭터 그림(`assets/brand/character.png`)에 카테고리 색과 제목만 바꾼 썸네일을 씁니다. 글 맨 위에 들어가고 티스토리 목록 썸네일로도 쓰입니다.

| 카테고리 | 파일 | 쓰는 곳 |
|---|---|---|
| 시황 | `assets/brand/thumb_market.jpg` | 시황 글에 자동으로 들어감 |
| 경제 공부 | `assets/brand/thumb_study.jpg` | 경제 공부 글에 자동으로 들어감 |
| 시사 | `assets/brand/thumb_issue.jpg` | 직접 쓰는 글에 대표 이미지로 올림 |
| 정치 | `assets/brand/thumb_politics.jpg` | 직접 쓰는 글에 대표 이미지로 올림 |

- 썸네일은 `python assets/brand/make_thumbnails.py`로 다시 만듭니다. 캐릭터 그림을 바꾸거나 카테고리를 늘릴 때 이 스크립트만 고칩니다.
- 이미지 레포에는 날짜 폴더가 아니라 `shared/`에 한 번만 올라가고, 그림이 바뀔 때만 다시 올라갑니다.
- 글마다 데이터로 그린 표지(시황: 지수 4개 카드, 경제 공부: 키워드 카드)로 돌아가려면 `config/settings.yaml`의 `thumbnails`에서 해당 항목을 지웁니다.

## 인스타 카드뉴스 (한국어·영어 계정)

시황 글과 같은 실행에서 인스타 카드 묶음을 계정마다 만들어 `[인스타 카드]` 메일로 보냅니다.
- **한국어 계정(그냥모아, 8장)**: 표지 → 오늘 시장 한눈에 → 이슈 2장 → 미국 업종 히트맵 → 미국 대형주 → 일정 → 오늘의 한 줄
- **영어 계정(@the4pmrecap, 10장)**: 미국장 메인. 표지 → 스코어보드 → 업종 → 대형주 → 이슈 2장 → 아시아·한국 체크 → 한국 증시 이슈 → 일정 → 다음 거래일 체크리스트
- 숫자 카드는 데이터로 그리고, 글(제목·이슈·캡션)은 Claude 가 씁니다. 배경 사진은 Pixabay 에서 찾습니다 (`PIXABAY_API_KEY`, 없으면 단색 배경).
- 메일에 카드 이미지와 캡션이 들어 있어, 처음에는 휴대폰에 저장해 직접 올립니다.
- 자동 게시: 계정 토큰을 Secrets(`INSTAGRAM_ACCESS_TOKEN`·`INSTAGRAM_USER_ID`, 영어 계정은 `INSTAGRAM_EN_…`)에 넣고 `config/settings.yaml`의 `instagram.publish`를 `true`로 바꾸면 그날부터 게시합니다. 카드는 공개 이미지 레포에 올린 주소로 게시됩니다.
- 카드만 다시 받아 보려면 **Actions → daily-post → Run workflow**에서 `mode`를 `cards`로 실행합니다 (블로그 초안 메일은 보내지 않음).
- 계정 이름·카드 순서·숫자판 지표는 `settings.yaml`의 `instagram.accounts`, 디자인은 `templates/cards/card.html.j2`에서 바꿉니다.
- **확인한 카드 올리기**: `mode`를 `insta-edit`(문장 고치기, `edits`에 `[["찾을 문장","바꿀 문장"]]`) 또는 `insta-post`로 두고 `source_run`에 카드를 만든 실행 번호를 넣습니다.
- **릴스**: 같은 카드를 장당 3초씩 이어 붙인 세로 영상(약 27초)을 캐러셀과 함께 올립니다. 릴스 탭에만 보이고 프로필 격자에는 쌓이지 않습니다. 음악은 Pixabay 무료 음원 6곡을 날짜별로 돌려 씁니다(`instagram.reels`). 릴스만 다시 올리려면 `mode`를 `insta-reel`로 실행합니다.
- **계정 소개 게시물(프로필 고정용)**: `mode`를 `insta-intro`, `source_run`에 예시로 보여 줄 카드를 만든 실행 번호를 넣으면 7장짜리 소개 게시물을 만들어 메일로 보냅니다. 확인 후 그 실행 번호로 `insta-post`를 돌리고, 앱에서 게시물을 프로필 맨 위에 고정합니다. 글은 `config/intro.yaml`에서 고칩니다.

## 처음 설정

### 0. 티스토리 스킨 (Book Club)
Book Club 스킨은 대표 이미지를 글 제목 뒤 배경으로 깔아 썸네일의 숫자와 제목이 겹칩니다.
**꾸미기 → 스킨 편집 → html 편집 → CSS** 맨 아래에 아래 한 줄을 넣으면 제목 띠가 남색 단색으로 바뀝니다 (대표 이미지는 본문 첫 그림과 목록 썸네일로 그대로 쓰입니다).

```css
.post-cover { background-image: none !important; background-color: #13294b !important; }
```


### 1. API 키 발급

| 이름 | 용도 | 발급처 | 비용 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | 초안 작성 | https://console.anthropic.com | 글 1편에 수십 원~백원대 |
| `LAYA_API_KEY` | 기사 주제·중요도 분류 | https://console.laya-ai.com | 1,000회 호출당 $0.05 |
| `FRED_API_KEY` | 미국 금리 | https://fred.stlouisfed.org/docs/api/api_key.html | 무료 |
| `ECOS_API_KEY` | 한국 금리 | https://ecos.bok.or.kr/api/ | 무료 |
| `SMTP_USER` / `SMTP_PASSWORD` | 초안 메일 발송 | Gmail: 2단계 인증 후 [앱 비밀번호](https://myaccount.google.com/apppasswords) | 무료 |
| `MAIL_TO` | 받을 메일 주소 | - | - |
| `CHARTS_REPO_TOKEN` | 차트 PNG를 공개 이미지 레포에 올리기 | GitHub fine-grained 토큰 (아래 3번) | 무료 |

키가 없는 단계는 자동으로 대체 동작합니다.
- Laya 키가 없으면 키워드 분류기를 씁니다.
- FRED·ECOS 키가 없으면 해당 데이터를 빼고 진행합니다.
- Claude 키가 없으면 데이터만 채운 템플릿 초안을 만듭니다.

### 2. GitHub Secrets 등록

레포 **Settings → Secrets and variables → Actions → New repository secret**에 위 이름 그대로 등록합니다.
`SMTP_HOST`(smtp.gmail.com)와 `SMTP_PORT`(587)도 함께 등록합니다.

### 3. 차트 이미지 공개 레포 (붙여넣기 한 번으로 이미지까지)

이 레포는 나중에 비공개로 바꿀 예정이라, 차트 PNG는 별도 **공개** 레포에 올리고 GitHub Pages 주소를 본문에 넣습니다.
1. 공개 레포 `seoloo/econblog-assets`를 만들고 **Settings → Pages**에서 `main` 브랜치 `/ (root)`로 배포를 켭니다.
2. **Settings → Developer settings → Fine-grained tokens**에서 토큰을 만듭니다.
   Repository access는 `econblog-assets` 하나만, 권한은 **Contents: Read and write** 하나만 줍니다.
3. 이 레포 Secrets에 `CHARTS_REPO_TOKEN`으로 등록합니다.
레포 이름이나 주소를 바꾸면 `config/settings.yaml`의 `publish`를 함께 고칩니다.

### 4. 동작 확인

**Actions → daily-post → Run workflow**에서 `dry_run`을 체크하고 실행합니다. 샘플 데이터로 만든 메일이 오면 설정이 끝난 것입니다.

## 로컬 실행

```bash
pip install -e ".[dev]"
cp .env.example .env              # 키 입력
python -m econblog run --dry-run  # 외부 호출 없이 샘플로 전체 흐름 확인 → output/<날짜>/preview.html
python -m econblog run            # 실제 실행
python -m econblog check-sources  # RSS 소스 점검
python -m econblog guide --list   # 경제 공부 주제 목록과 오늘 차례
python -m econblog guide --topic vix --dry-run   # 경제 공부 글 샘플 → output/<날짜>-guide-vix/
pytest
```

## 확장

- 뉴스·블로그 추가: `config/sources.yaml`
- 지표 추가: `config/series.yaml`
- 차트 추가: `config/settings.yaml`의 `charts`
- 경제 공부 주제 추가: `config/guides.yaml` 맨 아래에 한 항목
- 글 스타일 변경: `prompts/` (말투 공통 규칙은 `prompts/_human.md`)
- 레이아웃 변경: `templates/post.html.j2`(시황), `templates/guide.html.j2`(경제 공부), 공통 부품은 `templates/_tistory.html.j2`

## 참고

- 레포가 public인 동안에는 60일 동안 커밋이 없으면 GitHub가 예약 실행을 자동으로 끕니다. private으로 바꾸면 이 제한이 없고, 무료 플랜의 월 2,000분 안에서 충분히 돌아갑니다(1회 약 3~5분).
- 수집한 기사와 생성된 초안(`output/`)은 커밋하지 않습니다.
