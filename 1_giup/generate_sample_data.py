import pandas as pd
import numpy as np
import random
from datetime import datetime

def generate_sample_data():
    """200건의 샘플 기업통계등록부 데이터 생성"""

    # 기본 설정
    np.random.seed(42)
    random.seed(42)

    # 시도/시군구 데이터
    regions = [
        ('서울특별시', ['종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구']),
        ('부산광역시', ['중구', '서구', '동구', '영도구', '부산진구', '동래구', '남구', '북구', '해운대구', '사하구']),
        ('대구광역시', ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군']),
        ('인천광역시', ['중구', '동구', '미추홀구', '연수구', '남동구', '부평구', '계양구', '서구']),
        ('경기도', ['수원시', '성남시', '안양시', '안산시', '용인시', '평택시', '시흥시', '김포시', '광주시', '하남시']),
        ('강원도', ['춘천시', '원주시', '강릉시', '동해시', '태백시', '속초시', '삼척시']),
        ('충청북도', ['청주시', '충주시', '제천시', '보은군', '옥천군', '영동군']),
        ('충청남도', ['천안시', '공주시', '보령시', '아산시', '서산시', '논산시']),
        ('전라북도', ['전주시', '군산시', '익산시', '정읍시', '남원시', '김제시']),
        ('전라남도', ['목포시', '여수시', '순천시', '나주시', '광양시']),
        ('경상북도', ['포항시', '경주시', '김천시', '안동시', '구미시', '영주시']),
        ('경상남도', ['창원시', '진주시', '통영시', '사천시', '김해시', '밀양시']),
        ('제주특별자치도', ['제주시', '서귀포시'])
    ]

    # 산업분류코드 1차 (주요 산업)
    industry_codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S']
    industry_weights = [0.05, 0.02, 0.25, 0.03, 0.02, 0.08, 0.15, 0.06, 0.08, 0.05, 0.03, 0.04, 0.08, 0.05, 0.02, 0.03, 0.04, 0.02, 0.01]
    # 가중치 정규화
    industry_weights = np.array(industry_weights)
    industry_weights = industry_weights / industry_weights.sum()

    # 법인구분코드 (1:개인사업자, 2:회사법인, 3:회사외법인, 4:기관및단체, 5:국가.지방자치단체)
    org_codes = [1, 2, 3, 4, 5]
    org_weights = [0.6, 0.3, 0.06, 0.03, 0.01]

    # 폐업구분코드 (1:정상영업, 2:휴업중, 3:폐업중, 4:주소변환, 99:기타)
    closure_codes = [1, 2, 3, 4, 99]
    closure_weights = [0.85, 0.05, 0.03, 0.02, 0.05]

    # 성별코드 (1:남성, 2:여성)
    gender_codes = [1, 2]
    gender_weights = [0.65, 0.35]

    # 영리구분코드 (1:영리, 2:비영리)
    profit_codes = [1, 2]
    profit_weights = [0.9, 0.1]

    data = []

    for i in range(200):
        # 지역 선택
        sido_info = random.choice(regions)
        sido = sido_info[0]
        sigungu = random.choice(sido_info[1])

        # 기본 정보
        year = 2024
        month = 12

        # 사업자등록번호 생성 (임의)
        biznum_gap = f"A{random.randint(10000000000, 99999999999)}"
        biznum_eul = f"B{random.randint(10000000000, 99999999999)}" if random.random() > 0.3 else None

        # 코드 선택 (가중치 기반)
        org_code = np.random.choice(org_codes, p=org_weights)
        closure_code = np.random.choice(closure_codes, p=closure_weights)
        industry_code = np.random.choice(industry_codes, p=industry_weights)
        gender_code = np.random.choice(gender_codes, p=gender_weights)
        profit_code = np.random.choice(profit_codes, p=profit_weights)

        # 종사자수 (규모에 따라)
        if org_code == 1:  # 개인사업자
            emp_total = random.randint(1, 5)
        elif org_code == 2:  # 회사법인
            emp_total = random.randint(5, 100)
        else:  # 기타
            emp_total = random.randint(1, 50)

        emp_male = int(emp_total * random.uniform(0.4, 0.8))
        emp_female = emp_total - emp_male

        emp_regular_male = int(emp_male * random.uniform(0.7, 0.9))
        emp_regular_female = int(emp_female * random.uniform(0.7, 0.9))

        emp_temp_male = emp_male - emp_regular_male
        emp_temp_female = emp_female - emp_regular_female

        # 자본금액 (조직형태에 따라)
        if org_code == 1:  # 개인사업자
            capital = random.randint(1000000, 50000000)
        elif org_code == 2:  # 회사법인
            capital = random.randint(10000000, 1000000000)
        else:
            capital = random.randint(5000000, 100000000)

        # 사업체수 (기본 1개)
        business_count = 1

        row = {
            '기준년도': year,
            '기준월': month,
            '사업자등록번호_갑': biznum_gap,
            '사업자등록번호_을': biznum_eul,
            '법인구분코드': org_code,
            '영리구분코드': profit_code,
            '대표자성별코드': gender_code,
            '대표자생년월일': f"{random.randint(1950, 1990)}{random.randint(1, 12):02d}{random.randint(1, 28):02d}",
            '개업일자': f"{random.randint(2010, 2023)}{random.randint(1, 12):02d}{random.randint(1, 28):02d}",
            '최종일자': f"{year}{month:02d}{random.randint(1, 28):02d}",
            '폐업일자': None,
            '활동여부': 'Y',
            '폐업사유': None,
            '폐업구분코드': closure_code,
            '시도명': sido,
            '시군구명': sigungu,
            '우편번호': f"{random.randint(10000, 99999)}",
            '소재지전화번호': f"0{random.randint(2, 9)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
            '사업체한국표준산업분류1차코드': industry_code,
            '사업체한국표준산업분류5차코드': f"{industry_code}{random.randint(10, 99)}",
            '사업체한국표준산업분류11차1차코드': f"{industry_code}{random.randint(1000, 9999)}",
            '사업체한국표준산업분류11차5차코드': f"{industry_code}{random.randint(10000, 99999)}",
            '사업체수': business_count,
            '대표사업체여부': 'Y',
            '법인등록번호': f"{random.randint(100000000000, 999999999999)}",
            '자본금액': capital,
            '종사자수_계': emp_total,
            '종사자수_남자': emp_male,
            '종사자수_여자': emp_female,
            '종사자수_상용남자': emp_regular_male,
            '종사자수_상용여자': emp_regular_female,
            '종사자수_임시일용남자': emp_temp_male,
            '종사자수_임시일용여자': emp_temp_female,
            '종사자수_기타임시일용남자': 0,
            '조직한국표준산업분류1차코드': industry_code,
            '조직한국표준산업분류2차코드': f"{industry_code}{random.randint(1, 9)}",
            '조직한국표준산업분류3차코드': f"{industry_code}{random.randint(10, 99)}",
            '자료생성일자': f"{year}{month:02d}{random.randint(1, 28):02d}"
        }

        data.append(row)

    # DataFrame 생성
    df = pd.DataFrame(data)

    # CSV 파일로 저장
    output_path = 'data/giup_source_sample.csv'
    df.to_csv(output_path, index=False, encoding='cp949')

    print(f"샘플 데이터 생성 완료: {output_path}")
    print(f"총 {len(df)}건의 데이터")
    print(f"시도 분포: {df['시도명'].value_counts().head()}")
    print(f"법인구분코드 분포: {df['법인구분코드'].value_counts()}")
    print(f"산업분류코드 분포: {df['사업체한국표준산업분류1차코드'].value_counts()}")
    print(f"폐업구분코드 분포: {df['폐업구분코드'].value_counts()}")

    return df

if __name__ == "__main__":
    generate_sample_data()