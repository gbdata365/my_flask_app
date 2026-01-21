# -*- coding: utf-8 -*-
"""
LLM 및 Text-to-SQL 테스트 스크립트
"""
import sys
sys.path.insert(0, '.')

from loguru import logger

print("=" * 50)
print("1. LLM 클라이언트 테스트")
print("=" * 50)

from module.llm_client import LLMClient

# API 키 상태 확인
providers = LLMClient.list_providers()
print(f"\n사용 가능한 LLM:")
for name, available in providers.items():
    status = "O 사용가능" if available else "X API키 없음"
    print(f"  - {name}: {status}")

# Claude 테스트
if providers.get('claude'):
    print("\n[Claude 테스트]")
    try:
        client = LLMClient('claude')
        response = client.chat("안녕하세요. 간단히 인사해주세요.")
        print(f"응답: {response[:100]}...")
        print("Claude 연결 성공!")
    except Exception as e:
        print(f"Claude 오류: {e}")
else:
    print("\nClaude API 키가 설정되지 않았습니다.")

# Solar 테스트
if providers.get('solar'):
    print("\n[Solar2 테스트]")
    try:
        client = LLMClient('solar')
        response = client.chat("안녕하세요. 간단히 인사해주세요.")
        print(f"응답: {response[:100]}...")
        print("Solar2 연결 성공!")
    except Exception as e:
        print(f"Solar2 오류: {e}")

print("\n" + "=" * 50)
print("2. Text-to-SQL 테스트")
print("=" * 50)

from module.text_to_sql import TextToSQL

# 사용 가능한 LLM으로 테스트
available = [k for k, v in providers.items() if v]
if available:
    provider = available[0]
    print(f"\n[{provider} 사용]")

    try:
        t2s = TextToSQL(llm_provider=provider)

        question = "고령화율이 높은 시군구 5개"
        print(f"\n질문: {question}")

        result = t2s.ask(question)

        if result['error']:
            print(f"오류: {result['error']}")
        else:
            print(f"\n생성된 SQL:\n{result['sql']}")
            print(f"\n결과 ({len(result['data'])}건):")
            print(result['data'].to_string())

    except Exception as e:
        print(f"Text-to-SQL 오류: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n사용 가능한 LLM이 없습니다. API 키를 확인해주세요.")

print("\n" + "=" * 50)
print("테스트 완료!")
print("=" * 50)
