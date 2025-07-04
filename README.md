# DeepMail - AI 기반 메일 관리 시스템

Gmail과 OpenAI API를 연동한 지능형 메일 관리 시스템입니다. 피싱 메일 탐지, 메일 요약, 웹서치 분석 등 다양한 AI 기능을 제공합니다.

## 주요 기능

### 메일 관리
- Gmail 연동 및 메일 목록 조회
- 메일 상세 내용 확인 및 첨부파일 다운로드
- 메일 삭제 및 휴지통 이동

### AI 분석 기능
- **피싱 메일 탐지**: 머신러닝 모델 기반 자동 탐지
- **메일 요약**: OpenAI GPT를 활용한 메일 내용 요약
- **웹서치 분석**: 실시간 웹 검색을 통한 메일 신뢰도 분석
- **에이전트 분석**: 복합 AI 도구를 활용한 종합 분석

### 사용자 인터페이스
- 직관적인 웹 인터페이스 (Streamlit)
- 실시간 채팅 형태의 AI 상호작용
- 대시보드를 통한 메일 통계 확인

## 설치 및 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Gmail API 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Gmail API 활성화
3. OAuth 2.0 클라이언트 ID 생성
4. `credentials.json` 파일을 프로젝트 루트에 다운로드

### 4. 애플리케이션 실행
```bash
cd deepmail
streamlit run app.py
```

## 사용법

### 초기 설정
1. 사이드바에서 OpenAI API 키 설정 상태 확인
2. Gmail 로그인 버튼을 클릭하여 인증
3. 메일 목록이 자동으로 로드됩니다

### AI 기능 사용
- **메일 요약**: "최근 5개 메일 요약해줘"
- **피싱 탐지**: "1번 메일이 피싱인지 확인해줘"
- **웹서치 분석**: "2번 메일을 웹서치로 분석해줘"
- **메일 삭제**: "피싱 메일을 찾아서 삭제해줘"

### 메일 관리
- 메일 목록에서 원하는 메일 클릭하여 상세 내용 확인
- 첨부파일 다운로드 및 이미지 미리보기
- 메일 삭제 및 휴지통 이동

## 프로젝트 구조

```
DeepMail_26AI/
├── deepmail/
│   ├── app.py                 # 메인 애플리케이션
│   ├── ui_component.py        # UI 컴포넌트
│   ├── gmail_service.py       # Gmail API 서비스
│   ├── openai_service_clean.py # OpenAI API 서비스
│   └── config.py              # 설정 파일
├── models/
│   ├── rf_phishing_model.pkl  # 피싱 탐지 모델
│   └── phishing_Detecting_model.joblib
├── log/
│   └── deepmail.log          # 로그 파일
├── requirements.txt           # 의존성 패키지
└── README.md                 # 프로젝트 문서
```

## 기술 스택

- **Frontend**: Streamlit
- **AI/ML**: OpenAI GPT, Scikit-learn, Joblib
- **Email**: Gmail API, Google OAuth
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly
- **Web Parsing**: BeautifulSoup

## 주의사항

- **API 비용**: OpenAI API 사용량에 따라 비용이 발생합니다
- **보안**: API 키와 인증 정보를 안전하게 보관하세요
- **요청 한도**: Gmail API와 OpenAI API의 사용량 한도를 확인하세요
- **환경변수**: `.env` 파일이 `.gitignore`에 포함되어 있는지 확인하세요

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.
