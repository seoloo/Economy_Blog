# Economy_Blog

국내·해외 경제 뉴스와 블로그를 참고해 **월~토 아침 경제 시황 글 초안과 차트**를 만드는 파이프라인입니다.
일요일은 새 시장 데이터가 없어 쉽니다 (토요일 글이 금요일 미국·국내 장 마감을 다룸).
초안은 메일로 받고, 사람이 검토한 뒤 티스토리에 게시합니다.

```
RSS 수집 → Laya 분류·중복 제거 → 시장 데이터(yfinance·FRED·ECOS) → 차트 직접 생성
  → Claude 초안 작성 → 저작권(원문 복사) 검사 → HTML 렌더링 → 메일 발송
```

에이전트 작업 규칙과 코드 구조는 [AGENTS.md](AGENTS.md)에 있습니다.

## 월~토 아침에 하는 일 (약 10분)

1. 07시쯤 `[블로그 초안] 11/07 ...` 메일이 옵니다. 상단 「발행 전 확인」 상자를 먼저 봅니다.
2. 티스토리 글쓰기에서 편집기를 **HTML 모드**로 바꾸고, 첨부된 `post.html` 내용을 붙여넣습니다.
3. 기본 모드로 돌아와 `[이미지 삽입]` 상자 자리에 첨부된 차트 PNG를 올립니다.
4. 수치와 사실을 확인하고, 내 의견을 한두 문장 덧붙입니다. 메일의 제목과 태그를 넣고 발행합니다.

메일 제목에 `[검토 N건]`이 붙어 있으면 출처 문장과 겹치는 구간이나 데이터 누락이 있다는 뜻입니다. 반드시 고친 뒤 발행합니다.

## 처음 설정

### 1. API 키 발급

| 이름 | 용도 | 발급처 | 비용 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | 초안 작성 | https://console.anthropic.com | 글 1편에 수십 원~백원대 |
| `LAYA_API_KEY` | 기사 주제·중요도 분류 | https://console.laya-ai.com | 1,000회 호출당 $0.05 |
| `FRED_API_KEY` | 미국 금리 | https://fred.stlouisfed.org/docs/api/api_key.html | 무료 |
| `ECOS_API_KEY` | 한국 금리 | https://ecos.bok.or.kr/api/ | 무료 |
| `SMTP_USER` / `SMTP_PASSWORD` | 초안 메일 발송 | Gmail: 2단계 인증 후 [앱 비밀번호](https://myaccount.google.com/apppasswords) | 무료 |
| `MAIL_TO` | 받을 메일 주소 | - | - |

키가 없는 단계는 자동으로 대체 동작합니다.
- Laya 키가 없으면 키워드 분류기를 씁니다.
- FRED·ECOS 키가 없으면 해당 데이터를 빼고 진행합니다.
- Claude 키가 없으면 데이터만 채운 템플릿 초안을 만듭니다.

### 2. GitHub Secrets 등록

레포 **Settings → Secrets and variables → Actions → New repository secret**에 위 이름 그대로 등록합니다.
`SMTP_HOST`(smtp.gmail.com)와 `SMTP_PORT`(587)도 함께 등록합니다.

### 3. 동작 확인

**Actions → daily-post → Run workflow**에서 `dry_run`을 체크하고 실행합니다. 샘플 데이터로 만든 메일이 오면 설정이 끝난 것입니다.

## 로컬 실행

```bash
pip install -e ".[dev]"
cp .env.example .env              # 키 입력
python -m econblog run --dry-run  # 외부 호출 없이 샘플로 전체 흐름 확인 → output/<날짜>/preview.html
python -m econblog run            # 실제 실행
python -m econblog check-sources  # RSS 소스 점검
pytest
```

## 확장

- 뉴스·블로그 추가: `config/sources.yaml`
- 지표 추가: `config/series.yaml`
- 차트 추가: `config/settings.yaml`의 `charts`
- 글 스타일 변경: `prompts/`
- 레이아웃 변경: `templates/post.html.j2`

## 참고

- 레포가 public인 동안에는 60일 동안 커밋이 없으면 GitHub가 예약 실행을 자동으로 끕니다. private으로 바꾸면 이 제한이 없고, 무료 플랜의 월 2,000분 안에서 충분히 돌아갑니다(1회 약 3~5분).
- 수집한 기사와 생성된 초안(`output/`)은 커밋하지 않습니다.
