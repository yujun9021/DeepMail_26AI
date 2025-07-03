### 1. 가상환경 생성 및 활성화

------python 3.13.4------

### 2. 필요한 라이브러리 설치

```bash
# pip 업그레이드
python -m pip install --upgrade pip

# requirements.txt로 모든 패키지 설치
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# OpenAI API 키 설정
# OpenAI 웹사이트(https://platform.openai.com/api-keys)에서 발급받은 API 키를 입력하세요
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. 클라이언트 인증 정보

yujun_test폴더에 credentials.json 파일 생성
