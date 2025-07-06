# DeepMail - AI 기반 메일 관리 시스템

Gmail과 OpenAI API를 연동한 지능형 메일 관리 시스템입니다. 피싱 메일 탐지, 메일 요약, 웹서치 분석 등 다양한 AI 기능을 제공하며, 멀티 에이전트 시스템을 통해 고급 작업을 처리합니다.

## 주요 기능

### 메일 관리
- **Gmail 연동**: OAuth 2.0 기반 안전한 Gmail 연동
- **메일 목록 조회**: 최근 메일들을 효율적으로 로드 및 표시
- **메일 상세 확인**: 제목, 발신자, 내용, 첨부파일 확인
- **메일 삭제**: 개별 또는 일괄 메일 삭제 (휴지통 이동)
- **페이지네이션**: 설정 가능한 페이지당 메일 개수

### AI 분석 기능
- **피싱 메일 탐지**: 머신러닝 모델 기반 자동 탐지
- **메일 요약**: OpenAI GPT를 활용한 메일 내용 요약
- **웹서치 분석**: 실시간 웹 검색을 통한 메일 신뢰도 분석
- **링크 위험도 분석**: 메일 내 링크의 안전성 검사
- **메일 검색**: 키워드 기반 메일 검색
- **통계 분석**: 메일 패턴 및 인사이트 분석

### 멀티 에이전트 시스템
- **6개 전문 에이전트**: Coordinator, Classifier, Predictor, Searcher, Analyzer, Executor
- **자동 작업 분배**: 요청에 따른 최적 에이전트 선택
- **워크플로우 실행**: 복잡한 작업의 단계별 처리
- **실시간 협업**: 에이전트 간 실시간 통신 및 결과 통합

### 챗봇 인터페이스
- **자연어 처리**: 자연스러운 한국어 대화
- **Function Calling**: OpenAI Function Calling 기반 정확한 작업 실행
- **실시간 응답**: 즉시적인 피드백 및 결과 제공
- **멀티 모드**: 기본 모드와 멀티 에이전트 모드 선택 가능

## 설치 및 설정

### 1. 저장소 클론
```bash
git clone <repository-url>
cd DeepMail_26AI
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Gmail API 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Gmail API 활성화
3. OAuth 2.0 클라이언트 ID 생성
4. `credentials.json` 파일을 프로젝트 루트에 다운로드

### 5. 애플리케이션 실행
```bash
cd deepmail
streamlit run app.py
```

## 사용법

### 초기 설정
1. 사이드바에서 OpenAI API 키 설정 상태 확인
2. Gmail 로그인 버튼을 클릭하여 인증
3. 메일 설정에서 로드할 메일 개수와 페이지당 메일 개수 설정
4. AI 시스템 설정에서 멀티 에이전트 모드 선택

### AI 기능 사용 예시

#### 기본 모드 (Function Calling)
```
- "최근 5개 메일 요약해줘"
- "1번 메일이 피싱인지 확인해줘"
- "2번 메일을 웹서치로 분석해줘"
- "피싱 메일을 찾아서 삭제해줘"
- "회사 관련 메일 검색해줘"
- "메일 통계 보여줘"
```

#### 멀티 에이전트 모드
```
- "최근 메일들을 분석하고 피싱 메일을 찾아서 삭제해줘"
- "링크가 포함된 메일들을 위험도 분석해줘"
- "스팸 메일들을 정리해줘"
- "중요한 메일들을 분류해줘"
```

### 메일 관리
- 메일 목록에서 원하는 메일 클릭하여 상세 내용 확인
- 첨부파일 다운로드 및 이미지 미리보기
- 메일 삭제 및 휴지통 이동
- 페이지네이션을 통한 메일 탐색

## 프로젝트 구조

```
DeepMail_26AI/
├── deepmail/
│   ├── app.py                    # 메인 애플리케이션 (Streamlit)
│   ├── ui_component.py           # UI 컴포넌트 및 레이아웃
│   ├── gmail_service.py          # Gmail API 서비스
│   ├── openai_service_clean.py   # OpenAI API 서비스 (Function Calling)
│   ├── agent_system.py           # 멀티 에이전트 시스템
│   ├── mail_utils.py             # 메일 유틸리티 함수
│   └── config.py                 # 설정 및 상수
├── models/
│   ├── rf_phishing_model.pkl     # 피싱 탐지 모델
│   └── phishing_Detecting_model.joblib
├── cache/                        # 캐시 파일들
├── log/
│   └── deepmail.log             # 로그 파일
├── requirements.txt              # 의존성 패키지
└── README.md                    # 프로젝트 문서
```

## 멀티 에이전트 시스템

### 에이전트 구성

1. **Coordinator Agent (조율 에이전트)**
   - 다른 에이전트들을 관리하고 작업을 분배
   - 워크플로우 생성 및 실행
   - 에이전트 간 협업 조율

2. **Classifier Agent (분류 에이전트)**
   - 메일 분류 및 우선순위 결정
   - 카테고리 감지 (긴급, 스팸, 중요, 개인)
   - 추천 액션 생성

3. **Predictor Agent (예측 에이전트)**
   - 피싱 메일 예측
   - 스팸 메일 예측
   - 위험도 평가

4. **Searcher Agent (검색 에이전트)**
   - 메일 검색
   - 웹 검색 및 정보 수집
   - 링크 위험도 분석

5. **Analyzer Agent (분석 에이전트)**
   - 통계 분석
   - 패턴 인식
   - 트렌드 분석

6. **Executor Agent (실행 에이전트)**
   - 메일 삭제
   - 일괄 작업 수행
   - 실제 작업 실행

### 에이전트 간 협업 예시

```
사용자: "최근 메일들을 분석하고 피싱 메일을 찾아서 삭제해줘"

1. Classifier Agent → 요청 분류 및 우선순위 평가
2. Predictor Agent → 피싱 메일 예측
3. Analyzer Agent → 메일 패턴 분석
4. Executor Agent → 피싱 메일 삭제
5. Coordinator Agent → 결과 통합 및 사용자 응답
```

## 보안 및 성능 최적화

### API 요청 최적화
- **배치 처리**: Gmail API 배치 요청으로 효율적인 메일 로드
- **지연 로딩**: 메일 상세 내용은 필요시에만 로드
- **캐싱**: 자주 사용되는 데이터 캐싱으로 성능 향상

### 에러 처리
- **429 에러 방지**: API 요청 한도 관리
- **재시도 로직**: 일시적 오류에 대한 자동 재시도
- **사용자 친화적 오류 메시지**: 명확한 오류 안내

## 대시보드 기능

### 피싱/스팸 대시보드
- 실시간 피싱 메일 탐지 결과
- 스팸 메일 통계
- 위험도 시각화

### 메일 통계
- 발신자별 메일 분포
- 시간대별 메일 패턴
- 키워드 분석

## 기술 스택

- **Frontend**: Streamlit
- **AI/ML**: OpenAI GPT-4, Scikit-learn, Joblib
- **Email**: Gmail API, Google OAuth 2.0
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly
- **Web Parsing**: BeautifulSoup
- **Async Processing**: Asyncio (멀티 에이전트)

## 주의사항

- **API 비용**: OpenAI API 사용량에 따라 비용이 발생합니다
- **보안**: API 키와 인증 정보를 안전하게 보관하세요
- **요청 한도**: Gmail API와 OpenAI API의 사용량 한도를 확인하세요
- **환경변수**: `.env` 파일이 `.gitignore`에 포함되어 있는지 확인하세요
- **메모리 사용량**: 대량의 메일 처리 시 메모리 사용량을 모니터링하세요

## 설정 옵션

### 메일 설정
- **로드할 메일 개수**: 10, 30, 50, 100, 200, 500개 선택 가능
- **페이지당 메일 개수**: 10, 15, 20, 25, 30개 선택 가능

### AI 시스템 설정
- **기본 모드**: OpenAI Function Calling 사용
- **멀티 에이전트 모드**: 6개 전문 에이전트 협업

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 지원

문제가 발생하거나 기능 요청이 있으시면 이슈를 생성해주세요.
