# DeepMail_26AI

## OpenAI API 챗봇 프로젝트

Streamlit과 OpenAI API를 사용하여 구현한 지능형 챗봇 애플리케이션입니다.

### 기능

- 🤖 OpenAI GPT 모델 기반 지능형 대화
- 🔑 환경변수 기반 API 키 설정
- 🎛️ 모델 선택 (GPT-3.5-turbo, GPT-4)
- 🌡️ 창의성 조절 (Temperature)
- 💬 실시간 채팅 인터페이스
- 🔄 대화 초기화
- 💾 대화 내보내기
- ⚠️ 오류 처리 및 사용자 안내

### 설치 및 실행

1. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

2. **환경변수 설정**
   - 프로젝트 루트에 `.env` 파일 생성
   - `env_example.txt` 파일을 참고하여 API 키 설정:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **OpenAI API 키 준비**
   - [OpenAI 웹사이트](https://platform.openai.com/api-keys)에서 API 키 발급
   - 유료 계정 필요 (크레딧 충전)

4. **애플리케이션 실행**
   ```bash
   streamlit run app.py
   ```

5. **브라우저에서 확인**
   - 자동으로 브라우저가 열리거나
   - `http://localhost:8501`에서 접속

### 사용법

1. **환경변수 확인**
   - 사이드바에서 API 키 설정 상태 확인
   - ✅ 표시가 있으면 정상 설정됨

2. **모델 및 설정 조정**
   - 모델 선택: GPT-3.5-turbo (빠름, 저렴) 또는 GPT-4 (정확함, 비쌈)
   - Temperature 조절: 0.0 (일관성) ~ 2.0 (창의성)

3. **대화 시작**
   - 하단 입력창에 메시지 입력
   - 챗봇이 실시간으로 응답

4. **대화 관리**
   - "대화 초기화" 버튼으로 새로 시작
   - "대화 내보내기"로 채팅 기록 저장

### 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

**주의**: `.env` 파일은 절대 Git에 커밋하지 마세요!

### 주의사항

- **API 비용**: OpenAI API는 사용량에 따라 비용이 발생합니다
- **API 키 보안**: `.env` 파일을 안전하게 보관하고 공유하지 마세요
- **요청 한도**: API 사용량 한도가 있으니 주의해서 사용하세요
- **환경변수**: `.env` 파일이 `.gitignore`에 포함되어 있는지 확인하세요

### 기술 스택

- **Streamlit**: 웹 애플리케이션 프레임워크
- **OpenAI API**: GPT 모델 API
- **python-dotenv**: 환경변수 관리
- **Python**: 프로그래밍 언어
### 지원하는 모델

- **GPT-3.5-turbo**: 빠르고 경제적인 모델
- **GPT-4**: 더 정확하고 창의적인 응답 (더 비쌈)
