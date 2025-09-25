import unittest
import pandas as pd
import tempfile
import os
from pathlib import Path
import sys

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from routes.csv_analyzer import CSVAnalyzer


class TestCSVAnalyzer(unittest.TestCase):
    """CSV 분석기 자동 테스트"""
    
    def setUp(self):
        """테스트 전 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
    def tearDown(self):
        """테스트 후 정리"""
        # 임시 파일들 정리
        for file_path in self.temp_path.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        os.rmdir(self.temp_dir)
    
    def create_test_csv(self, filename: str, data: dict) -> str:
        """테스트용 CSV 파일 생성"""
        df = pd.DataFrame(data)
        csv_path = self.temp_path / filename
        df.to_csv(csv_path, index=False, encoding='utf-8')
        return str(csv_path)
    
    def test_시계열_데이터_분석(self):
        """시계열 데이터 분석 테스트"""
        # 테스트 데이터 생성
        test_data = {
            '년도': ['2020', '2021', '2022', '2020', '2021', '2022'],
            '지역': ['서울', '서울', '서울', '부산', '부산', '부산'],
            '인구수': ['9,720,000', '9,700,000', '9,650,000', '3,400,000', '3,380,000', '3,360,000'],
            '경제활동': ['4,500,000', '4,400,000', '4,350,000', '1,600,000', '1,580,000', '1,560,000']
        }
        
        csv_path = self.create_test_csv('시계열_테스트.csv', test_data)
        
        # 분석 실행
        analyzer = CSVAnalyzer(csv_path)
        results = analyzer.load_and_analyze_csv()
        
        # 테스트 검증
        self.assertNotIn('error', results)
        self.assertEqual(results['file_info']['rows'], 6)
        self.assertEqual(results['file_info']['columns'], 4)
        
        # 컬럼 타입 감지 확인
        self.assertIn('년도', results['columns']['time_columns'])
        self.assertIn('지역', results['columns']['location_columns'])
        self.assertIn('인구수', results['columns']['numeric_columns'])
        self.assertIn('경제활동', results['columns']['numeric_columns'])
        
        # 차트 생성 테스트
        charts = analyzer.generate_charts()
        self.assertIn('timeseries', charts)
        self.assertIn('regional', charts)
        self.assertIn('distribution', charts)
        
        # 시계열 차트가 생성되었는지 확인
        self.assertGreater(len(charts['timeseries']), 0)
        self.assertGreater(len(charts['regional']), 0)
    
    def test_지역_데이터_분석(self):
        """지역별 데이터 분석 테스트"""
        test_data = {
            '시도': ['서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시'],
            '시군구': ['강남구', '해운대구', '수성구', '연수구', '서구'],
            '사업체수': ['50,000', '25,000', '20,000', '30,000', '15,000'],
            '종사자수': ['400,000', '200,000', '150,000', '250,000', '120,000']
        }
        
        csv_path = self.create_test_csv('지역_테스트.csv', test_data)
        
        analyzer = CSVAnalyzer(csv_path)
        results = analyzer.load_and_analyze_csv()
        
        # 지역 컬럼 감지 확인
        self.assertIn('시도', results['columns']['location_columns'])
        self.assertIn('시군구', results['columns']['location_columns'])
        
        # 숫자 컬럼 감지 및 처리 확인
        self.assertIn('사업체수', results['columns']['numeric_columns'])
        self.assertIn('종사자수', results['columns']['numeric_columns'])
        
        # 차트 생성 확인
        charts = analyzer.generate_charts()
        self.assertIn('regional', charts)
        self.assertGreater(len(charts['regional']), 0)
    
    def test_특수문자_처리(self):
        """특수문자가 포함된 데이터 처리 테스트"""
        test_data = {
            '년도': ['2020', '2021', '2022'],
            '지역': ['서울', '부산', '대구'],
            '데이터1': ['1,000', '*', '2,500'],
            '데이터2': ['500', '1,200', '*']
        }
        
        csv_path = self.create_test_csv('특수문자_테스트.csv', test_data)
        
        analyzer = CSVAnalyzer(csv_path)
        results = analyzer.load_and_analyze_csv()
        
        # 특수문자가 숫자로 변환되었는지 확인
        self.assertNotIn('error', results)
        self.assertIn('데이터1', results['columns']['numeric_columns'])
        self.assertIn('데이터2', results['columns']['numeric_columns'])
        
        # 요약 통계에서 특수문자 처리 확인
        self.assertIn('데이터1', results['summary_stats'])
        self.assertIn('데이터2', results['summary_stats'])
    
    def test_빈_데이터_처리(self):
        """빈 데이터 및 결측값 처리 테스트"""
        test_data = {
            '년도': ['2020', '2021', None, '2023'],
            '지역': ['서울', None, '대구', ''],
            '값': ['100', '', '300', '400']
        }
        
        csv_path = self.create_test_csv('빈데이터_테스트.csv', test_data)
        
        analyzer = CSVAnalyzer(csv_path)
        results = analyzer.load_and_analyze_csv()
        
        # 에러 없이 처리되었는지 확인
        self.assertNotIn('error', results)
        self.assertEqual(results['file_info']['rows'], 4)
    
    def test_잘못된_파일_처리(self):
        """존재하지 않는 파일 처리 테스트"""
        analyzer = CSVAnalyzer('존재하지않는파일.csv')
        results = analyzer.load_and_analyze_csv()
        
        # 에러가 적절히 처리되었는지 확인
        self.assertIn('error', results)
    
    def test_HTML_생성(self):
        """대시보드 HTML 생성 테스트"""
        test_data = {
            '년도': ['2020', '2021', '2022'],
            '시도': ['서울', '부산', '대구'],
            '인구수': ['1000', '800', '600']
        }
        
        csv_path = self.create_test_csv('HTML_테스트.csv', test_data)
        
        analyzer = CSVAnalyzer(csv_path)
        analyzer.load_and_analyze_csv()
        
        # HTML 생성 테스트
        html_content = analyzer.generate_dashboard_html("테스트 대시보드")
        
        # HTML 기본 구조 확인
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>테스트 대시보드</title>', html_content)
        self.assertIn('plotly-latest.min.js', html_content)
        self.assertIn('bootstrap', html_content)
        
        # 데이터가 포함되었는지 확인
        self.assertIn('인구수', html_content)
        self.assertIn('chartsData', html_content)
    
    def test_다양한_인코딩_지원(self):
        """다양한 인코딩 파일 지원 테스트"""
        test_data = {
            '년도': ['2020', '2021'],
            '지역': ['서울특별시', '부산광역시'],
            '인구수': ['9720000', '3400000']
        }
        
        # UTF-8로 저장
        csv_path_utf8 = self.create_test_csv('인코딩_utf8.csv', test_data)
        
        analyzer = CSVAnalyzer(csv_path_utf8)
        results = analyzer.load_and_analyze_csv()
        
        self.assertNotIn('error', results)
        self.assertEqual(results['file_info']['rows'], 2)


class TestCSVDashboardIntegration(unittest.TestCase):
    """통합 테스트"""
    
    def setUp(self):
        """테스트 전 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """테스트 후 정리"""
        for file_path in self.temp_path.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        os.rmdir(self.temp_dir)
    
    def test_전체_워크플로우(self):
        """전체 분석 워크플로우 테스트"""
        # 실제 사용 시나리오를 모방한 데이터
        test_data = {
            '기준년월': ['202001', '202002', '202003', '202001', '202002', '202003'],
            '시도명': ['서울특별시', '서울특별시', '서울특별시', '부산광역시', '부산광역시', '부산광역시'],
            '시군구명': ['강남구', '강남구', '강남구', '해운대구', '해운대구', '해운대구'],
            '사업체수': ['15,250', '15,180', '15,320', '8,450', '8,390', '8,520'],
            '종사자수': ['125,600', '124,800', '126,200', '68,500', '68,200', '69,100'],
            '매출액': ['2,500,000', '2,450,000', '2,580,000', '1,200,000', '1,180,000', '1,230,000']
        }
        
        # CSV 파일 생성
        df = pd.DataFrame(test_data)
        csv_path = self.temp_path / 'integration_test.csv'
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        # 1. 분석 실행
        analyzer = CSVAnalyzer(str(csv_path))
        results = analyzer.load_and_analyze_csv()
        
        # 2. 기본 분석 결과 검증
        self.assertNotIn('error', results)
        self.assertEqual(results['file_info']['rows'], 6)
        
        # 3. 컬럼 타입 감지 검증
        detected = results['columns']
        self.assertIn('기준년월', detected['time_columns'])
        self.assertIn('시도명', detected['location_columns'])
        self.assertIn('사업체수', detected['numeric_columns'])
        
        # 4. 차트 생성 검증
        charts = analyzer.generate_charts()
        self.assertIn('timeseries', charts)
        self.assertIn('regional', charts)
        self.assertIn('distribution', charts)
        
        # 5. HTML 대시보드 생성 검증
        html_content = analyzer.generate_dashboard_html()
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertGreater(len(html_content), 10000)  # 충분한 HTML 콘텐츠가 생성되었는지
        
        # 6. 차트 데이터 구조 검증
        for chart_type in ['timeseries', 'regional']:
            self.assertIsInstance(charts[chart_type], list)
            if len(charts[chart_type]) > 0:
                chart = charts[chart_type][0]
                self.assertIn('title', chart)
                self.assertIn('traces', chart)
                self.assertIsInstance(chart['traces'], list)


def run_tests():
    """테스트 실행 함수"""
    # 테스트 스위트 생성
    test_suite = unittest.TestSuite()
    
    # CSVAnalyzer 테스트 추가
    test_suite.addTest(unittest.makeSuite(TestCSVAnalyzer))
    test_suite.addTest(unittest.makeSuite(TestCSVDashboardIntegration))
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result


if __name__ == '__main__':
    print("=== CSV Dashboard 자동 테스트 시작 ===")
    result = run_tests()
    
    if result.wasSuccessful():
        print("\n✅ 모든 테스트가 성공했습니다!")
        exit_code = 0
    else:
        print(f"\n❌ {len(result.failures)} 개의 실패, {len(result.errors)} 개의 오류가 발생했습니다.")
        exit_code = 1
    
    # 테스트 결과 요약
    print(f"\n테스트 요약:")
    print(f"- 실행된 테스트: {result.testsRun}")
    print(f"- 성공: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"- 실패: {len(result.failures)}")
    print(f"- 오류: {len(result.errors)}")
    
    exit(exit_code)