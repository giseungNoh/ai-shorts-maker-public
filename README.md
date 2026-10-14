# AI Shorts Maker — Public Portfolio Edition

주제 하나를 입력하면 **대본 → 장면별 이미지/영상 프롬프트 → 음성 → 영상 → 자막/편집** 단계로 이어지는 쇼츠 제작 자동화 프로젝트의 공개 포트폴리오 버전입니다.

> 이 저장소는 채용/포트폴리오 검토용으로 정리한 공개본입니다.  
> 실제 개발 저장소는 Private으로 유지하며, 계정·쿠키·토큰·개인 음성·로그·브라우저 자동화 관련 코드와 과거 Git history는 공개하지 않습니다.

## 무엇을 해결했나

쇼츠 하나를 만들 때 여러 AI 도구 사이에서 파일을 저장하고 옮기고, 실패한 장면을 다시 실행하는 반복 작업이 발생했습니다.  
이를 하나의 파이프라인으로 연결해 **각 Scene의 중간 결과를 저장하고, 완료된 작업은 유지한 채 실패 지점부터 이어서 처리**할 수 있도록 만들었습니다.

## 개발 방식

개발에는 **OpenAI Codex**를 사용했습니다.

1. 먼저 유지보수를 고려해 UI / Service / 자동화 기능의 책임을 나눴습니다.
2. 각 기능의 입력·출력과 완료 조건을 정한 뒤 Codex에 기능 단위 구현을 맡겼습니다.
3. 생성된 코드는 그대로 사용하지 않고 실제 실행 결과를 단위별로 확인했습니다.
4. 문제가 생기면 증상을 그대로 다시 요청하기보다 원인을 좁혀 수정 범위를 정한 뒤 재검증했습니다.

예를 들어 Gemini API를 이용한 대본·프롬프트 생성 기능은 단순히 API 응답 성공 여부만 확인하지 않고, **입력한 주제에 맞는 대본과 장면별 이미지·영상 프롬프트가 만들어지는지** 직접 확인했습니다.

## 핵심 설계

### 1. Scene 단위 상태 관리
각 장면의 이미지, 영상, 음성 등 중간 결과를 별도로 저장합니다.  
전체 작업이 중간에 실패해도 이미 완료된 장면을 다시 만들지 않도록 구성했습니다.

### 2. 8GB VRAM을 고려한 영상 생성
로컬 환경은 **RTX 4060 Ti 8GB**였습니다. MiniMax H3를 ComfyUI에서 실행할 때 여러 영상 생성을 동시에 처리하면 OOM 위험이 있어, GPU 영상 생성은 **단일 Queue Worker**로 순차 처리하도록 설계했습니다.

대신 이미지 생성 등 GPU 영상 생성과 직접 충돌하지 않는 단계는 먼저 진행하고, 준비가 끝난 Scene을 영상 Queue에 전달하는 구조로 전체 파이프라인을 구성했습니다.

### 3. 실패를 전체 실패로 만들지 않기
Scene 단위 결과 저장과 Queue 처리로 특정 장면에서 오류가 발생해도 완료된 결과를 유지할 수 있도록 했습니다. 테스트에서는 생성 실패 상황에서도 Queue의 task 상태가 정상적으로 정리되는지 확인했습니다.

## 공개 코드에서 볼 수 있는 부분

```
src/
├── core/
│   └── models.py              # 영상 작업 DTO
├── services/
│   ├── project_service.py     # Scene 상태/중간 결과 저장 및 복구
│   └── video_service.py       # 8GB VRAM 대응 순차 영상 Queue
├── automation/
│   └── minimax_h3.py          # ComfyUI 기반 MiniMax H3 클라이언트
└── utils/
    └── path_utils.py          # Scene별 파일 경로 규칙

tests/
└── test_video_queue_safety.py # 실패 시 Queue 정리/복구 검증
```

## 전체 파이프라인

```
주제 입력
  ↓
Gemini — 대본 / Scene / 이미지·영상 프롬프트 생성
  ↓
Scene별 이미지 생성
  ↓
TTS — 장면별 음성 생성
  ↓
ComfyUI + MiniMax H3 — 장면별 영상 생성
  ↓
MoviePy / FFmpeg — 자막·음성·영상 합성
  ↓
최종 Shorts
```

## 기술 스택

- Python
- Streamlit
- Gemini API
- Qwen3 TTS / GPT-SoVITS
- ComfyUI / MiniMax H3
- MoviePy / FFmpeg
- OpenAI Codex

## 결과물

실제 생성한 쇼츠 결과는 아래 채널에서 확인할 수 있습니다.

https://youtube.com/channel/UCkGD9b-9t4OaFFGACVO9wMw?si=HWIE-gtzzZcNvthd

## 공개 범위

보안을 위해 아래 항목은 이 공개 저장소에서 제외했습니다.

- API Key 및 환경 설정 원본
- 로그인 세션, Cookie, Token
- 사용자 음성 및 개인 데이터
- 실행 로그 및 로컬 경로
- 외부 웹 서비스 브라우저 자동화 구현
- Private 저장소의 기존 Git history

이 저장소는 실제 프로젝트의 문제 정의, 구조 설계, 로컬 영상 생성, 상태 관리, 실패 복구 및 테스트 방식을 확인할 수 있도록 필요한 부분만 선별한 포트폴리오용 공개본입니다.
