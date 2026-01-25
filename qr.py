# -*- coding: utf-8 -*-
"""
QR 코드 생성기
==============
주소(URL)를 입력하면 QR 이미지를 생성합니다.

사용법:
    python qr.py

필요 라이브러리:
    pip install qrcode[pil]
    또는
    uv pip install qrcode pillow
"""

import qrcode
from pathlib import Path
from datetime import datetime


def create_qr_code(url: str, filename: str = None, output_dir: str = "output") -> str:
    """
    URL을 QR 코드 이미지로 변환합니다.

    Args:
        url: QR 코드로 변환할 URL 또는 텍스트
        filename: 저장할 파일명 (없으면 자동 생성)
        output_dir: 출력 디렉토리

    Returns:
        생성된 QR 코드 이미지 경로
    """
    # 출력 디렉토리 생성
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # 파일명 자동 생성
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qr_{timestamp}.png"

    # QR 코드 생성
    qr = qrcode.QRCode(
        version=1,  # QR 코드 크기 (1~40, 자동 조절됨)
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 오류 복원 수준 (H: 30%)
        box_size=10,  # 각 박스의 픽셀 크기
        border=4,  # 테두리 두께
    )

    qr.add_data(url)
    qr.make(fit=True)

    # 이미지 생성
    img = qr.make_image(fill_color="black", back_color="white")

    # 저장
    save_path = output_path / filename
    img.save(save_path)

    return str(save_path)


def main():
    """메인 함수 - 대화형으로 QR 코드 생성"""
    print("=" * 50)
    print("  QR 코드 생성기")
    print("=" * 50)
    print()

    while True:
        # 주소 입력
        url = input("QR 코드로 만들 주소를 입력하세요 (종료: q): ").strip()

        if url.lower() == 'q':
            print("프로그램을 종료합니다.")
            break

        if not url:
            print("주소를 입력해주세요.\n")
            continue

        # 파일명 입력 (선택)
        filename = input("파일명 (Enter: 자동생성): ").strip()
        if filename and not filename.endswith('.png'):
            filename += '.png'

        try:
            # QR 코드 생성
            result_path = create_qr_code(
                url=url,
                filename=filename if filename else None
            )
            print(f"\n✅ QR 코드 생성 완료!")
            print(f"   저장 위치: {result_path}")
            print()
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}\n")


if __name__ == "__main__":
    main()
