# Minute

한국어 영상 → 약 1분 숏폼 편집기. 차콜·라임 UI, 로그인, 사용자별 프로젝트, 실제 FFmpeg 백그라운드 렌더링.

## Netlify 배포

이 저장소를 Netlify **Import an existing project → GitHub**에서 선택합니다.

- Branch: `main`
- Base directory: 비워두기 (저장소 루트)
- Build command: `node scripts/build-netlify.mjs`
- Publish directory: `dist`
- 설정은 루트 `netlify.toml`에 포함되어 자동 적용됩니다.

환경 변수 없이도 소개/업로드 안내 화면은 배포됩니다. **이 경우 영상 처리 서버 미연결을 표시하며 로그인·업로드·가짜 처리 결과를 제공하지 않습니다.**

### 실제 영상 처리를 연결하려면

Netlify만으로 Python/FFmpeg 서버, 영구 디스크, 장시간 작업 큐를 실행할 수 없습니다. Netlify proxy의 26초 제한 때문에 대용량 영상을 프록시하지 않고 처리 서버로 직접 보냅니다.

권장 구성은 같은 소유 도메인의 HTTPS 하위 도메인입니다:

| 항목 | 예시 및 설정 |
| --- | --- |
| Netlify 웹 주소 | `https://minute.example.com` |
| 별도 영상 처리 서버 | `https://api.example.com` |
| Netlify 환경 변수 | `MINUTE_API_ORIGIN=https://api.example.com` |
| 영상 서버 환경 변수 | `PUBLIC_ORIGIN=https://minute.example.com` |
| 자동 전사·추천 | 서버와 worker에만 `OPENAI_API_KEY` 설정 |

`MINUTE_API_ORIGIN`은 공개 API 주소이며 비밀키가 아닙니다. **API 키는 Netlify 프런트엔드 환경 변수/JS에 넣지 마세요.**

동일한 소유 도메인의 하위 도메인을 사용해야 HttpOnly·SameSite=Strict 쿠키 로그인이 작동합니다. 기본 `*.netlify.app`와 다른 도메인의 서버를 조합하면 cross-site 쿠키가 차단되므로, 이 구성에서는 custom domain을 연결하거나 FastAPI에서 웹 화면까지 함께 서비스하세요. 단순히 환경 변수에 서버 주소만 넣어 이 제약이 해결된다고 안내하지 않습니다.

영상 서버 실행·Docker Compose·제한·비용 구조·검증 결과는 [상세 운영 문서](minute/README.md)에 있습니다.

## 현재 확인한 범위

- 10분 **합성 테스트 영상**을 실제 업로드 → 한국어 수동 자막/제목 적용 → 60초 1080×1920 H.264/AAC MP4 생성 → 실제 다운로드.
- 다른 사용자의 파일 접근 거부, 손상 파일 실패, 새 세션에서 저장 복구, 자동/수동 삭제.
- 데스크톱 및 모바일 화면 확인, 잘못된 유튜브 링크 거부.

아직 미검증: 실제 사람의 한국어 음성 자동 전사·추천 품질, 인물 입모양/소리 검증, 공개 운영 서버 배포. 자동 분석은 서버 API 키 연결 전 비활성화됩니다. 인물 자동 추적은 미구현입니다.

YouTube는 임베드 미리보기만 지원하며 편집용 다운로드로 표시하지 않습니다. 자신의 원본 파일을 업로드해야 합니다.

공식 제한 참고: [Netlify proxy](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/), [Netlify Functions](https://docs.netlify.com/build/functions/configuration/).

## 사용자 Gemini 키 · 숏폼 상담

편집 화면에서 사용자 API 키 입력 → 데이터 전송/과금 안내 확인 → `완성도 점검 · 상담하기`를 누릅니다. **gemini-3.5-flash-lite**가 자막 기준으로 문장 끊김·맥락 누락을 검토하고 구간 수정을 제안합니다. 키는 저장하지 않으며 제안은 사용자 확인 후 적용합니다. 자막이 필요하고, 영상/음성 자체의 검사는 아닙니다. [연결·검증·보안 상세](minute/README.md#gemini-숏폼-완성도-상담원)를 참고하세요. 웹과 별도 FastAPI 서버를 모두 업데이트해야 합니다.

## 첫 화면에서 바로 Gemini 상담 (영상 서버 불필요)

첫 화면의 **내 자막으로 숏폼 완성도 점검하기**에서 새 Gemini API 키와 자막을 입력하면 로그인·FastAPI·영상 업로드 없이 상담할 수 있습니다.

- 일반 텍스트: 선택 구간의 자막과 선택적으로 앞뒤 발화를 입력합니다. 문장 단위로 조언하며 시간을 만들어내지 않습니다.
- SRT: 시간 포함 자막을 붙여넣고 1~95초 구간을 지정합니다. 자막 경계에 맞는 수정 시간을 제안합니다. `상담 구간에 적용`은 다음 상담 범위를 변경하며 영상 파일을 편집하지 않습니다.
- 데이터 전송/사용자 API 과금 안내에 동의한 뒤 상담하며, 자동 재시도하지 않습니다. 키와 대화는 DB·브라우저 저장소에 보관하지 않습니다.

### Vercel

GitHub `main`을 재배포하세요. Root Directory는 **저장소 최상위**입니다. 루트 `vercel.json`에 프리셋 Other(`framework: null`), 빌드 명령과 `dist` 출력 폴더를 지정했습니다. `api/consult.mjs`가 Vercel Node Function으로 실행되어 사용자의 키로 Gemini를 호출합니다. 상담에는 `MINUTE_API_ORIGIN`이나 서버 API 키 환경 변수가 필요하지 않습니다. **API 키는 웹 입력란에만 입력하세요.**

### Netlify

같은 빌드 설정에서 `netlify/functions/consult.mjs`가 `/api/consult`를 처리합니다. Vercel/Netlify 모두 단순 정적 파일 업로드만 하면 함수가 실행되지 않으므로 GitHub 연결 빌드로 배포해야 합니다.

상담은 Gemini API 사용량과 호스팅 함수 호출/실행량을 소비하며 각 계정의 플랜·무료 한도에 따라 비용이 발생할 수 있습니다. 이번 변경은 별도 유료 서버를 생성하지 않습니다. 기존 영상 업로드/렌더링은 여전히 별도 영상 서버가 필요합니다.

보안/제한: 상담 본문 최대 180KB, 자막 최대 60,000자·600개, 요청당 Gemini 응답 대기 25초. 같은 함수 인스턴스에서 키의 해시별 분당 6회 제한을 두며, 키 원문은 보관하지 않습니다. 인스턴스 간 공유되는 전역 한도는 아니므로 공개 트래픽 규모에 따라 호스팅 방화벽의 요청 제한을 추가하세요. 호스팅 로그/APM에 `X-Gemini-Key` 요청 헤더를 수집하지 마세요. 모델은 `gemini-3.5-flash-lite`로 고정합니다.

검증: `node --test tests/standalone-consult.test.mjs`. 모의 Google 응답으로 일반 자막/SRT, 입력 제한, 키 보호, 모델 오류, 시간 제안 검증 및 두 호스팅 어댑터를 확인했습니다. 실제 사용자 키 호출 및 공개 Vercel 배포는 사용자 재배포 후 확인이 필요합니다.
