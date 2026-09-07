# HIT PICK · KBO 안타 기대 순위

KBO 공식 기록을 바탕으로 기본타율, 최근타율(10경기), 상대팀 상대 타율을 비교하는 정적 사이트입니다.

## 로컬 확인

```bash
python -m http.server 4173 --directory dist
```

## 데이터 갱신

```bash
python scripts/crawl_kbo.py
```

크롤러는 KBO 기본 타자기록, 선수별 최근 10경기, 상대팀별 시즌 기록, 해당 월 경기 일정을 수집하고 검증합니다. 검증 실패 시 기존 `dist/kbo-data.json`을 덮어쓰지 않습니다.

## GitHub Pages 배포

저장소 Settings → Pages → Source에서 **GitHub Actions**를 선택합니다. `pages.yml`이 `main` 브랜치의 `dist`를 배포합니다. `kbo-refresh.yml`은 한국시간 매일 00:00(UTC 15:00)에 갱신을 시작하고, 수집·검증 후 데이터와 Pages를 함께 갱신합니다. GitHub Actions 스케줄은 실행이 지연될 수 있습니다.

## 기준

- 기본타율: 시즌 안타 ÷ 타수
- 최근타율(10경기): 최근 10경기 안타 합계 ÷ 타수 합계
- 상대팀 상대 타율: 해당 상대전 안타 ÷ 타수
- 종합점수: 기본타율 50% + 보정 최근타율 30% + 보정 상대타율 20%

종합점수는 비교용 휴리스틱이며 보정된 안타 확률이 아닙니다. 상대 선발투수와 당일 선발 라인업은 포함하지 않습니다.
