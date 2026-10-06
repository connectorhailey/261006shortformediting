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
