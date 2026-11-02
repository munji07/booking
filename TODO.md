# 책마루 구현 TODO

## 완료 — PHASE 1 기반 골격

- [x] 현재 프로젝트 파일을 확인하고 기존 코드가 없는 빈 프로젝트에 필요한 폴더·모듈 구조를 구성한다.
- [x] Python Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate, Werkzeug, python-dotenv 및 PostgreSQL 드라이버를 `requirements.txt`에 명시한다.
- [x] Flask 앱 팩토리 패턴과 `main`, `student`, `admin` Blueprint 기본 구조를 구현한다.
- [x] `config.py`, python-dotenv 및 환경변수를 사용해 운영 PostgreSQL과 로컬 SQLite 설정을 분리한다.
- [x] `extensions.py`에서 SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate 확장을 초기화하고 앱에 연결한다.
- [x] User, Student, InviteCode, Book, Reservation, Loan, Locker, PaperTicket, SnackExchange, SystemSetting, ActivityLog 기본 SQLAlchemy 모델과 상태 필드를 정의한다.
- [x] UTC 저장과 한국 시간 표시를 위한 공통 시간 처리 기반을 마련한다.
- [x] 전 페이지 한국어 공통 레이아웃과 학생용·관리자용 기본 화면 및 반응형 내비게이션을 구현한다.
- [x] 지정된 현대식 도서관 디자인 시스템을 적용한 학생용 카드형 화면과 관리자용 사이드바·테이블 기본 UI를 구성한다.
- [x] 고정 관리자 자격 증명을 포함하지 않고 로컬 실행, 데이터베이스 초기화·마이그레이션 및 PHASE 1 확인 방법을 문서화한다.

## 다음 단계 승인 대기

- [ ] PHASE 2: 관리자 로그인, 학생 등록, 1회용 만료 가입 코드 생성·재발급, 학생 회원가입, 학생 로그인·로그아웃.
- [ ] PHASE 3: 학생 대시보드 연결, 만화책 등록·조회, 표지 업로드, 검색·카테고리 필터.
- [ ] PHASE 4: 예약 신청·취소, 관리자 승인·거절, 재고 초과 방지 트랜잭션과 상태 기록.
- [ ] PHASE 5: 사물함, 종이 대여증, 대여·반납, 간식 교환 관리.
- [ ] PHASE 6: 모바일 최적화 보완, 보안 점검, 통합 테스트, 배포 문서와 운영 점검.
