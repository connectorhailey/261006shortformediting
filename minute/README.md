# Minute

한국어 숏폼 편집기. **로컬 구현 및 FFmpeg 검증 완료, 공개 배포와 실제 한국어 음성 AI 품질 검증은 미완료**입니다. 가짜 추천/샘플 결과를 사용자 프로젝트로 표시하지 않습니다.

## 실행

Python 3.12+, FFmpeg/ffprobe(libx264, libass 포함), Noto Sans CJK KR 필요.

```bash
cd minute
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export PUBLIC_ORIGIN=http://localhost:8000
uvicorn app:app --host 127.0.0.1 --port 8000
# 별도 터미널, 동일 환경과 디렉터리
python worker.py
```

소개 화면은 비로그인 상태에서 접근합니다. 실제 업로드는 회원가입 후 진행합니다. 기본 보관 위치는 `data/`입니다. 미디어는 정적 파일 경로로 공개하지 않으며 매 요청마다 세션의 소유자를 검증합니다.

## 운영 구조와 선정 이유

- FastAPI: 인증된 스트리밍 업로드, 프로젝트 상태/편집 저장, 다운로드와 Range 요청.
- SQLite WAL: 단일 서버에서 원자적으로 작업을 큐에 넣고 claim합니다. 외부 큐 계정 없이 재시작 후 상태가 남습니다. 실행 중 재시작된 작업은 명확히 실패로 바꾸며 사용자 재시도를 허용합니다.
- 별도 Python worker: FFmpeg subprocess를 실행합니다. 브라우저가 닫혀도 계속 처리합니다. 단일 worker 잠금을 사용하며 다중 서버용 큐는 아닙니다.
- 영구 디스크: 원본, 결과, ASS 자막, 상태 DB를 동일 볼륨에 보관합니다. 작업마다 최대 30분 timeout, worker RAM 4GB/CPU 2 제한. 웹 컨테이너 RAM 512MB/CPU 1.
- 5GB / 20분 / 최대 가로·세로 4096px, 사용자당 프로젝트 5개, 업로드 5회/일, 분석·렌더링 10회/일, 정확한 미리보기 30회/시간, IP당 API 요청 300회/분, 인증 15회/시간. 저장 공간 7GB 미만 시 신규 업로드 거부.
- 매 60초 보관 7일 경과 파일/DB 삭제, 중단 업로드는 1시간 뒤 정리. 실행 중 작업은 완료 후 삭제. 직접 삭제는 실행 중 작업 종료 후 가능.

Cloudflare Workers는 isolate 메모리 128MB이고 native FFmpeg 프로세스를 실행하는 서버가 아닙니다. 요청 본문 한도도 플랜별로 달라 5GB 직접 업로드 경로로 사용하지 않았습니다. 이 코드는 Workers에 그대로 배포할 수 없으며 전용 Linux 서버가 필요합니다.

## 자동 분석 연결

`OPENAI_API_KEY`를 서버/worker의 비밀 환경 변수로만 설정합니다. 브라우저에 키를 전달하지 않습니다. 키가 없으면 자동 분석 버튼을 비활성화하고 직접 편집·렌더링을 허용합니다.

1. FFmpeg로 16kHz 모노 48kbps MP3 추출(20분 약 7.2MB).
2. `whisper-1`, language `ko`, verbose_json segment timestamps로 음성 인식.
3. `HIGHLIGHT_MODEL`(기본 `gpt-4o-mini`)이 발화 내용에서 독립적인 도입/결론을 갖는 3개 구간 선택. 제공된 segment index만 받아 서버에서 검증하며 중복 구간을 거부합니다.
4. 시작/종료는 음성 segment 경계로 정합니다. 문장 완결성과 추천 품질은 실제 한국어 발화 영상으로 추가 검증해야 합니다.
5. 추천이 실패해도 이미 전사된 자막은 보존하여 직접 편집 가능합니다.

API 연결 시 오디오와 전사 내용이 OpenAI API로 전송됩니다. API 과금은 전사한 오디오 분량 및 하이라이트 분석 토큰량에 따라 달라집니다. 키 연결 및 과금 승인은 별도로 필요합니다. 현재 외부 API 호출 검증을 하지 않았습니다.

## YouTube

링크 호스트/영상 ID를 검사하고 youtube-nocookie 임베드로 원본을 보여 줍니다. 비공개/삭제/임베드 제한 영상은 재생되지 않을 수 있습니다. 임베드는 가져오기/다운로드 기능이 아닙니다. YouTube API의 원본 다운로드를 지원하는 공식 연동을 확보하지 못했으므로, 자신의 YouTube Studio 또는 Google Takeout에서 받은 원본을 업로드하도록 안내합니다.

- https://developers.google.com/youtube/v3/docs/videos/list
- https://developers.google.com/youtube/terms/developer-policies
- https://support.google.com/youtube/answer/56100
- https://developers.cloudflare.com/workers/platform/limits/

## 미리보기와 출력

9:16 cover/contain, 수동 가로·세로 위치, 제목, 자막 문구/시간/크기/색/배경/위치 편집을 지원합니다. 인물 자동 추적은 제공하지 않습니다.

브라우저 재생 미리보기는 빠른 배치 확인용으로 글꼴/줄바꿈의 차이가 있을 수 있음을 명시합니다. `서버에서 정확한 첫 화면 확인`은 최종 영상과 동일한 ASS/FFmpeg 필터를 사용한 PNG를 만듭니다. 최종 결과 미리보기는 실제 다운로드할 MP4 자체입니다. 출력: 1080×1920, H.264 yuv420p, AAC 192kbps, faststart. 원본에 오디오가 없으면 무음 결과이며 오디오를 만들어내지 않습니다.

## 공개 배포 준비

현재 배포 URL은 없습니다. 연결된 호스팅 계정/서버/도메인이 없으며 유료 리소스를 생성하지 않았습니다. Sites 플러그인 배포 스크립트 또한 실행 환경에 설치되어 있지 않습니다.

구체적인 최소 운영 구성: Linux 서버 2 vCPU, RAM 4~8GB, 영구 디스크 50GB 이상, HTTPS 도메인. 실제 동시 사용자 수와 원본 해상도에 따라 증설이 필요합니다. `compose.yaml`은 web/worker를 격리하고 영구 볼륨을 공유합니다. 서버 가동 요금 + 디스크 용량 + 전송량 + 선택적 AI 사용량이 비용 요소입니다. 공급자와 지역이 정해지지 않아 확정 견적을 제시하지 않습니다.

1. 서버/도메인 및 비용 범위 확정 후 DNS를 연결합니다.
2. `.env.example`을 서버에서 `.env`로 복사하고 HTTPS `PUBLIC_ORIGIN`을 지정합니다. 키는 비밀 저장소를 통해 주입합니다.
3. `docker compose up -d --build`.
4. 호스트 reverse proxy에서 TLS 종료, 요청 크기 5GB, 업로드 timeout 최소 30분, request buffering off를 설정합니다. 외부에 8000 포트를 직접 노출하지 않습니다.
5. 프록시가 전달한 IP는 신뢰할 프록시에서만 해석해야 합니다. 기본 `--no-proxy-headers`는 위조 헤더를 신뢰하지 않지만 프록시 뒤의 IP rate limit을 공유하므로 운영 시 신뢰 프록시 CIDR 설정이 필요합니다.
6. 디스크 사용량, worker 생존/큐 길이, 실패 로그 모니터링 및 프로세스 자동 재시작을 설정합니다.
7. 실제 10~20분 한국어 영상으로 업로드→전사→추천→편집→다운로드를 검증한 뒤 공개 서비스로 안내합니다.

추가 운영 제한: 이메일 인증/비밀번호 재설정, 다중 서버/분산 큐, 계정별 결제/과금, 운영자 콘솔은 미구현입니다. 회원가입 폭주 방어는 현재 IP 제한 수준이며 공개 규모에 맞춘 추가 방어가 필요합니다. 컨테이너의 악성 미디어 공격면을 줄이기 위해 FFmpeg와 OS 보안 업데이트를 유지해야 합니다.

## 검증

```bash
python tests/test_flow.py
```

600초 합성 테스트 영상(움직이는 패턴+사인파)을 실제 HTTP API에 업로드하고 작업을 실행하여 60초의 실제 MP4를 다운로드합니다. 이는 실제 사람의 한국어 발화 영상 테스트를 대체하지 않습니다.

검증 항목: 로그인 강제, 다른 계정의 프로젝트/원본/결과/삭제 접근 404, 지원하지 않는 확장자 415, 손상 영상 처리 실패, 저장 후 새 세션에서 편집 복구, 중복 작업 409, 잘못된 구간 400, 외부 Origin 403, 결과 코덱/해상도/길이/A-V timestamp, 삭제 및 보관 만료 정리.

브라우저 검증: 데스크톱/390px 모바일 화면, 가로 넘침 없음, 잘못된 YouTube 주소 거부. 자동 음성 인식 정확도/추천 완결성/사람이 듣는 입모양 동기화, 운영 환경 배포 및 부하 테스트는 아직 검증하지 않았습니다.
