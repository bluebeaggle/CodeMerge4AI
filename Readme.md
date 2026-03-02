모드	설명
FULL	전체 프로젝트
MODULE	특정 폴더만
DEPENDENCY_EXPAND	특정 모듈 + 그 모듈이 import 하는 파일


python code4Gemini.py --mode full --target backend/

python code4Gemini.py --mode module --target service/

python code4Gemini.py --mode dependency --target main.py