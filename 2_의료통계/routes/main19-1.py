import folium
import os

def main():
    try:
        # 현재 작업 디렉토리 출력
        print(f"Current working directory: {os.getcwd()}")
        
        # 맵 생성
        map = folium.Map(location=[37, 127], zoom_start=7)

        # 마커 추가
        marker = folium.Marker(
            [37.501087, 127.043069], popup="역삼아레나빌딩", icon=folium.Icon(color="blue")
        )
        marker.add_to(map)

        # HTML 저장 디렉토리 생성 (필요한 경우)
        html_dir = 'static/maps'
        os.makedirs(html_dir, exist_ok=True)

        # HTML 파일 경로 설정
        html_path = os.path.join(html_dir, 'star_map.html')
        
        # 맵 저장
        map.save(html_path)

        # 저장 경로 확인
        print(f"Map saved at: {os.path.abspath(html_path)}")
        print(f"Map file exists: {os.path.exists(html_path)}")

        # 더 명확한 HTML 반환
        return f'''
        <h2>지도 보기</h2>
        <div class="map-container">
            <iframe src="/static/maps/star_map.html" width="100%" height="500px" allowfullscreen></iframe>
        </div>
        <p>지도가 {os.path.abspath(html_path)}에 저장되었습니다.</p>
        '''
    except Exception as e:
        # 예외 상세 정보 출력
        print("예외 발생:")
        print(traceback.format_exc())
        return f"<p>오류 발생: {str(e)}</p>"