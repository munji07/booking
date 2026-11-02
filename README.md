# 책마루 (Bookmaru)

학생이 만화책을 찾고 예약하며, 관리자가 대여 흐름을 운영하는 Flask 기반 웹 애플리케이션입니다. 현재 PHASE 1에서는 운영 기능을 연결할 수 있는 애플리케이션 골격, 핵심 DB 모델, 공통 화면을 제공합니다.

## PHASE 1에서 준비된 것

- Flask 앱 팩토리와 `main`, `student`, `admin` Blueprint
- 환경변수 기반 설정: 운영 PostgreSQL / 로컬 SQLite
- Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate 연결
- User, Student, InviteCode, Book, Reservation, Loan, Locker, PaperTicket, SnackExchange, SystemSetting, ActivityLog 모델
- UTC 저장과 `Asia/Seoul` 표시 유틸리티
- 한국어 공통 레이아웃, 학생 카드형 화면, 관리자 사이드바·테이블 화면
- 실제 DB 집계 기반의 빈 상태 화면 및 `/health` 확인 엔드포인트

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app run.py init-db
python run.py
```

브라우저에서 `http://127.0.0.1:3000`을 엽니다. 로컬 기본 DB는 `instance/bookmaru.sqlite`입니다. 운영 PostgreSQL을 사용할 때는 `.env`의 `DATABASE_URL`을 `postgresql://...` 형식으로 지정하면 psycopg 연결 URL로 정규화됩니다.

## 마이그레이션

저장소에 초기 마이그레이션 이력이 포함되어 있으므로, 새 환경에서는 `init-db` 대신 다음 명령으로 스키마를 적용할 수 있습니다.

```bash
flask --app run.py db upgrade
```

스키마 변경은 `db migrate`로 생성된 이력을 검토한 뒤 `db upgrade`로 적용합니다. `flask --app run.py init-db`는 마이그레이션을 사용하지 않는 로컬 빠른 초기 확인용이므로 두 초기화 방식을 같은 DB에 연달아 실행하지 않습니다.

## 확인 방법

- `curl http://127.0.0.1:3000/health`가 `{"status":"ok",...}`를 반환하는지 확인합니다.
- `/`, `/student/`, `/student/books`, `/student/history`, `/admin/` 및 관리자 하위 화면을 순서대로 확인합니다.
- 책 데이터가 없는 최초 상태에서 “아직 등록된 책이 없습니다” 빈 상태가 표시되는지 확인합니다.
- 고정 관리자 계정이나 운영 비밀번호는 이 프로젝트에 포함하지 않습니다.

## 다음 단계

사용자 확인 후 PHASE 2에서 관리자 로그인, 학생 등록, `secrets` 기반 1회용 가입 코드, 학생 회원가입·로그인을 구현합니다. 이후 각 PHASE 완료 시 실제 DB 연결 기능과 보안·권한 테스트를 추가합니다.
