# -*- coding: utf-8 -*-
"""
기업체현황 테이블 ERD 이미지 생성
- 꺾은선으로 연결 (테이블 가리지 않음)
- 컬럼명 + 한글명
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path
import koreanize_matplotlib


def create_erd():
    """ERD 생성 (꺾은선, 한글명 포함)"""

    fig, ax = plt.subplots(1, 1, figsize=(24, 18))
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 90)
    ax.axis('off')

    # 색상 정의
    header_color = '#4472C4'
    pk_color = '#FFF2CC'
    fk_color = '#E2EFDA'
    normal_color = '#FFFFFF'
    border_color = '#2F5496'
    conditional_color = '#ED7D31'

    def draw_table(x, y, width, title, columns, record_count, is_conditional=False):
        """테이블 박스 그리기"""
        row_height = 1.1
        header_height = 2.2
        height = len(columns) * row_height + header_height

        header_c = conditional_color if is_conditional else header_color

        # 테이블 박스
        rect = FancyBboxPatch((x, y - height), width, height,
                              boxstyle="round,pad=0.02,rounding_size=0.3",
                              facecolor='white', edgecolor=border_color, linewidth=1.5)
        ax.add_patch(rect)

        # 헤더
        header_rect = FancyBboxPatch((x, y - header_height), width, header_height,
                                     boxstyle="round,pad=0.02,rounding_size=0.3",
                                     facecolor=header_c, edgecolor=border_color, linewidth=1.5)
        ax.add_patch(header_rect)

        # 테이블명
        ax.text(x + width/2, y - 0.9, title, ha='center', va='center',
                fontsize=9, fontweight='bold', color='white')
        ax.text(x + width/2, y - 1.7, f'({record_count:,}건)', ha='center', va='center',
                fontsize=7, color='white')

        # 컬럼들
        for i, (col_name, col_type, kor_name, key_type) in enumerate(columns):
            col_y = y - header_height - 0.1 - i * row_height - row_height/2

            # 배경색
            if key_type == 'PK':
                bg_color = pk_color
            elif key_type == 'FK':
                bg_color = fk_color
            else:
                bg_color = normal_color

            col_rect = plt.Rectangle((x + 0.1, col_y - row_height/2 + 0.05),
                                      width - 0.2, row_height - 0.1,
                                      facecolor=bg_color, edgecolor='#DDDDDD', linewidth=0.5)
            ax.add_patch(col_rect)

            # 키 표시
            if key_type:
                ax.text(x + 0.8, col_y, key_type, ha='left', va='center',
                        fontsize=6, fontweight='bold', color='#666666')

            # 컬럼명 + 한글명
            display_name = f'{col_name} ({kor_name})' if kor_name else col_name
            ax.text(x + 2.2, col_y, display_name, ha='left', va='center', fontsize=7)

            # 타입
            ax.text(x + width - 0.5, col_y, col_type, ha='right', va='center',
                    fontsize=6, color='#888888')

        return (x, y - height/2), (x + width, y - height/2), (x + width/2, y - height)

    def draw_elbow_arrow(start, end, direction='down', color='#666666'):
        """꺾은선 화살표 그리기 (테이블 가리지 않음)"""
        sx, sy = start
        ex, ey = end

        if direction == 'down':
            # 아래로 내려간 후 수평 이동 후 다시 아래로
            mid_y = (sy + ey) / 2
            ax.plot([sx, sx], [sy, mid_y], color=color, linewidth=1.2)
            ax.plot([sx, ex], [mid_y, mid_y], color=color, linewidth=1.2)
            ax.plot([ex, ex], [mid_y, ey + 0.3], color=color, linewidth=1.2)
            # 화살표
            ax.annotate('', xy=(ex, ey + 0.3), xytext=(ex, ey + 0.8),
                       arrowprops=dict(arrowstyle='->', color=color, lw=1.2))
        elif direction == 'side':
            # 옆으로 나간 후 아래로
            mid_x = sx + 1.5 if ex > sx else sx - 1.5
            ax.plot([sx, mid_x], [sy, sy], color=color, linewidth=1.2)
            ax.plot([mid_x, mid_x], [sy, ey], color=color, linewidth=1.2)
            ax.plot([mid_x, ex - 0.3], [ey, ey], color=color, linewidth=1.2)
            ax.annotate('', xy=(ex - 0.3, ey), xytext=(ex - 0.8, ey),
                       arrowprops=dict(arrowstyle='->', color=color, lw=1.2))

    # ===== 메인 테이블 (중앙 상단) =====
    main_cols = [
        ('id', 'INT', '', 'PK'),
        ('base_ym', 'VARCHAR(6)', '기준년월', ''),
        ('base_ym1', 'VARCHAR(30)', '원본기준시기', ''),
        ('data_type', 'VARCHAR(15)', '자료유형', ''),
        ('sido_nm', 'VARCHAR(30)', '시도명', ''),
        ('sigun_nm', 'VARCHAR(30)', '시군구명', ''),
        ('sigun_cd', 'VARCHAR(5)', '시군구코드', ''),
        ('created_at', 'TIMESTAMP', '생성일시', ''),
    ]
    main_left, main_right, main_bottom = draw_table(45, 85, 22, 'giup_summary', main_cols, 2006)

    # ===== 1행: 상세 테이블들 =====
    row1_y = 60

    # 조직형태별
    org_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('indiv_biz', 'INT', '개인사업체', ''),
        ('corp', 'INT', '회사법인', ''),
        ('corp_other', 'INT', '회사이외법인', ''),
        ('non_corp', 'INT', '비법인단체', ''),
        ('gov_local', 'INT', '국가지방자치단체', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(2, row1_y, 20, 'giup_detail_org_type\n(조직형태별)', org_cols, 2006)

    # 대표자성별
    gender_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('blank', 'INT', '공백', ''),
        ('male', 'INT', '남자', ''),
        ('female', 'INT', '여자', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(25, row1_y, 18, 'giup_detail_gender\n(대표자성별)', gender_cols, 2006)

    # 폐업여부
    status_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('active', 'INT', '영업중', ''),
        ('closed', 'INT', '폐업', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(68, row1_y, 18, 'giup_detail_status\n(폐업여부)', status_cols, 2006)

    # 대표사업체
    mainbiz_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('blank', 'INT', '공백', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(90, row1_y, 18, 'giup_detail_main_biz\n(대표사업체)', mainbiz_cols, 2006)

    # ===== 2행: 상세 테이블들 =====
    row2_y = 35

    # 산업분류별
    ind_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('blank', 'INT', '공백', ''),
        ('ind_a ~ ind_u', 'INT', '산업분류A~U', ''),
        ('', '', '(21개 산업대분류)', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(2, row2_y, 20, 'giup_detail_industry\n(산업분류별)', ind_cols, 2006)

    # 수치형통계
    stats_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('emp_count/sum/avg', 'INT/BIGINT', '종사자수', ''),
        ('sales_count/sum/avg', 'INT/BIGINT', '매출금액', ''),
        ('regular_*', 'INT/BIGINT', '상용근로자', ''),
        ('temp_*', 'INT/BIGINT', '임시일용', ''),
    ]
    draw_table(25, row2_y, 20, 'giup_detail_stats\n(수치형통계)', stats_cols, 2006)

    # 연령그룹별 (조건부)
    age_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('age_under_19', 'INT', '19세이하', ''),
        ('age_20_early~80_over', 'INT', '20대초~80대이상', ''),
        ('', '', '(15개 연령그룹)', ''),
        ('blank', 'INT', '공백', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(68, row2_y, 22, 'giup_detail_age_group\n(연령그룹) [연간/월간만]', age_cols, 500, is_conditional=True)

    # 기업규모별 (조건부)
    size_cols = [
        ('id', 'INT', '', 'PK'),
        ('summary_id', 'INT', '요약ID', 'FK'),
        ('blank', 'INT', '공백', ''),
        ('large_other', 'INT', '기타대기업', ''),
        ('mid_large', 'INT', '중견기업', ''),
        ('mid', 'INT', '중기업', ''),
        ('small', 'INT', '소기업', ''),
        ('micro', 'INT', '소상공인', ''),
        ('excluded', 'INT', '판정제외', ''),
        ('sangchul', 'INT', '상출기업', ''),
        ('total', 'INT', '합계', ''),
    ]
    draw_table(93, row2_y, 22, 'giup_detail_corp_size\n(기업규모) [연간만]', size_cols, 249, is_conditional=True)

    # ===== 연결선 (꺾은선) =====
    # 메인 테이블 하단 중심
    main_cx = 56
    main_cy = 74

    # 1행 연결
    draw_elbow_arrow((main_cx - 8, main_cy), (12, row1_y), 'down')
    draw_elbow_arrow((main_cx - 3, main_cy), (34, row1_y), 'down')
    draw_elbow_arrow((main_cx + 3, main_cy), (77, row1_y), 'down')
    draw_elbow_arrow((main_cx + 8, main_cy), (99, row1_y), 'down')

    # 2행 연결 (1행 테이블 아래를 통과)
    ax.plot([main_cx - 10, main_cx - 10], [main_cy, 42], color='#666666', linewidth=1.2, linestyle='-')
    ax.plot([main_cx - 10, 12], [42, 42], color='#666666', linewidth=1.2)
    ax.plot([12, 12], [42, row2_y + 0.3], color='#666666', linewidth=1.2)
    ax.annotate('', xy=(12, row2_y + 0.3), xytext=(12, row2_y + 0.8),
               arrowprops=dict(arrowstyle='->', color='#666666', lw=1.2))

    ax.plot([main_cx - 5, main_cx - 5], [main_cy, 43], color='#666666', linewidth=1.2)
    ax.plot([main_cx - 5, 35], [43, 43], color='#666666', linewidth=1.2)
    ax.plot([35, 35], [43, row2_y + 0.3], color='#666666', linewidth=1.2)
    ax.annotate('', xy=(35, row2_y + 0.3), xytext=(35, row2_y + 0.8),
               arrowprops=dict(arrowstyle='->', color='#666666', lw=1.2))

    # 조건부 테이블 연결 (주황색)
    ax.plot([main_cx + 5, main_cx + 5], [main_cy, 44], color=conditional_color, linewidth=1.2)
    ax.plot([main_cx + 5, 79], [44, 44], color=conditional_color, linewidth=1.2)
    ax.plot([79, 79], [44, row2_y + 0.3], color=conditional_color, linewidth=1.2)
    ax.annotate('', xy=(79, row2_y + 0.3), xytext=(79, row2_y + 0.8),
               arrowprops=dict(arrowstyle='->', color=conditional_color, lw=1.2))

    ax.plot([main_cx + 10, main_cx + 10], [main_cy, 45], color=conditional_color, linewidth=1.2)
    ax.plot([main_cx + 10, 104], [45, 45], color=conditional_color, linewidth=1.2)
    ax.plot([104, 104], [45, row2_y + 0.3], color=conditional_color, linewidth=1.2)
    ax.annotate('', xy=(104, row2_y + 0.3), xytext=(104, row2_y + 0.8),
               arrowprops=dict(arrowstyle='->', color=conditional_color, lw=1.2))

    # ===== 범례 =====
    legend_y = 6
    ax.add_patch(plt.Rectangle((5, legend_y), 2.5, 1.3, facecolor=pk_color, edgecolor='#CCCCCC'))
    ax.text(8.5, legend_y + 0.65, 'PK (Primary Key)', va='center', fontsize=8)

    ax.add_patch(plt.Rectangle((25, legend_y), 2.5, 1.3, facecolor=fk_color, edgecolor='#CCCCCC'))
    ax.text(28.5, legend_y + 0.65, 'FK (Foreign Key) -> summary_id', va='center', fontsize=8)

    ax.add_patch(plt.Rectangle((55, legend_y), 2.5, 1.3, facecolor=conditional_color, edgecolor='#CCCCCC'))
    ax.text(58.5, legend_y + 0.65, '조건부 테이블 (일부 data_type만 데이터 존재)', va='center', fontsize=8)

    # ===== 제목 =====
    ax.text(60, 88.5, '기업체현황 데이터베이스 ERD', ha='center', va='center',
            fontsize=14, fontweight='bold')
    ax.text(60, 87, 'giup_summary (1) <-> (1) giup_detail_* 관계 | FK: summary_id', ha='center', va='center',
            fontsize=9, color='#666666')

    # ===== 외부 연결 정보 =====
    ax.text(60, 3, '[외부 테이블 연결] sigun_cd(시군구코드) -> gb_address, fact_population_basic 등 | base_ym(기준년월) -> 인구/가구 테이블',
            ha='center', va='center', fontsize=8, color='#444444', style='italic')

    plt.tight_layout()

    # 저장
    output_path = Path(__file__).parent / 'giup_erd.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f'ERD 이미지 생성 완료: {output_path}')
    return output_path


if __name__ == '__main__':
    create_erd()
