# SWAP Ops Git 배포/롤백 런북

## 목적
- 코드 이력을 남기고 (`git`)
- 동일 버전을 재배포할 수 있으며
- 장애 시 즉시 이전 버전으로 롤백할 수 있는 운영 표준

## 1) 최초 1회: 로컬 저장소 준비
```bash
cd /Users/otaeseog/Desktop/codex/swap-ops-dashboard
git init -b main
git add .
git commit -m "chore: bootstrap swap ops dashboard"
git remote add origin <YOUR_REMOTE_GIT_URL>
git push -u origin main
```

## 2) 서버 1회 세팅 (이미 되어 있다면 생략)
```bash
ssh <USER>@<HOST>
sudo mkdir -p /srv/swap-ops-dashboard
sudo chown -R $USER:$USER /srv/swap-ops-dashboard
git clone <YOUR_REMOTE_GIT_URL> /srv/swap-ops-dashboard
```

## 3) 일반 배포
```bash
cd /Users/otaeseog/Desktop/codex/swap-ops-dashboard
git checkout main
git pull

# 수정
git add .
git commit -m "feat: <변경내용>"
git push origin main

# 서버 반영
./scripts/deploy_remote.sh <USER>@<HOST> main
```

## 4) 릴리즈 태그 배포 (권장)
```bash
cd /Users/otaeseog/Desktop/codex/swap-ops-dashboard
./scripts/release_tag.sh
# 또는 ./scripts/release_tag.sh v2026.04.25-ops

./scripts/deploy_remote.sh <USER>@<HOST> <TAG>
```

## 5) 롤백
```bash
cd /Users/otaeseog/Desktop/codex/swap-ops-dashboard
./scripts/rollback_remote.sh <USER>@<HOST> <이전_TAG_또는_커밋해시>
```

## 6) 운영 체크리스트
- 배포 직후:
  - `https://<domain>/api/health`
  - `https://<domain>/api/sync/status`
- 동기화 성공 여부:
  - 서버 로그 또는 `sync_status.json`
- 장애 시:
  - 즉시 `rollback_remote.sh` 실행 후 원인 분석

## 7) 주의사항
- `.redash_api_key`, `data/dashboard.db`, `logs/`, `reports/`는 git에 커밋하지 않음
- 실제 키는 서버 환경변수(`REDASH_API_KEY`)로 관리
- main 직접 작업 대신 기능 브랜치 + PR 방식 권장

