"""앱 아이콘(app_icon.ico)을 코드로 그린다.

이미지를 가져다 쓰지 않고 도형으로 직접 그려 저작권 문제를 만들지 않는다
(arrow_down.png도 같은 방식으로 만들었다).

그림: 세이지 그린 둥근 사각형 위에, 왼쪽 뒤로 노란 해가 살짝 보이고 그
앞을 회색 구름이 가린다. 흐린 날과 맑은 날이 함께 있는 모습이라 감정의
기복을 다루는 앱과 어울린다.

작은 크기(16px)에서도 알아볼 수 있도록 광선 같은 잔 장식은 넣지 않고,
덩어리 셋(바탕·해·구름)만으로 실루엣을 만든다.

실행: python tools/make_icon.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QImage, QPainter, QPainterPath)
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config, theme  # noqa: E402

# 아이콘 안에서만 쓰는 색 — 세이지 그린 바탕 위에서 또렷하도록 고른 톤
SUN = "#F5C64B"           # 노란 해 (STAR_ON 계열, 조금 더 밝게)
CLOUD_LIGHT = "#F2F1EE"   # 구름 윗면
CLOUD_SHADE = "#D2D5D6"   # 구름 아랫면 — 회색 기를 준다

# ICO에 함께 담을 크기들. Windows가 상황에 따라 골라 쓴다.
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _cloud_path(size: float) -> QPainterPath:
    """원 세 개와 바닥 둥근 사각형을 합쳐 만든 구름 실루엣.

    기본 채우기 규칙(OddEven)은 도형이 겹친 자리를 도로 비워 원의 윤곽이
    드러난다. Winding으로 바꿔야 하나의 덩어리가 된다.
    """
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    # 좌표는 1.0 기준 비율로 잡고 마지막에 size를 곱한다
    path.addEllipse(QPointF(0.46 * size, 0.62 * size), 0.13 * size,
                    0.13 * size)
    path.addEllipse(QPointF(0.63 * size, 0.57 * size), 0.17 * size,
                    0.17 * size)
    path.addEllipse(QPointF(0.78 * size, 0.65 * size), 0.12 * size,
                    0.12 * size)
    path.addRoundedRect(
        QRectF(0.34 * size, 0.64 * size, 0.56 * size, 0.15 * size),
        0.075 * size, 0.075 * size)
    return path.simplified()


def draw_icon(size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)

    # 바탕: 둥근 사각형 (모서리는 크기에 비례)
    painter.setBrush(QColor(theme.LIGHT["PRIMARY"]))
    margin = size * 0.04
    painter.drawRoundedRect(
        QRectF(margin, margin, size - margin * 2, size - margin * 2),
        size * 0.22, size * 0.22)

    # 해: 구름보다 뒤에 오도록 먼저 그린다 (왼쪽 위, 구름에 살짝 가리게)
    painter.setBrush(QColor(SUN))
    painter.drawEllipse(QPointF(0.36 * size, 0.36 * size), 0.155 * size,
                        0.155 * size)

    # 구름: 아래쪽 그림자를 먼저 깔고 그 위에 밝은 면을 조금 올려 입체감
    cloud = _cloud_path(size)
    painter.setBrush(QColor(CLOUD_SHADE))
    painter.drawPath(cloud)
    painter.translate(0, -size * 0.03)
    painter.setBrush(QColor(CLOUD_LIGHT))
    painter.drawPath(cloud)

    painter.end()
    return image


def main() -> None:
    app = QApplication([])   # QImage·QPainter를 쓰려면 필요
    folder = config.asset_path("app_icon.ico").parent
    folder.mkdir(parents=True, exist_ok=True)

    images = [draw_icon(size) for size in SIZES]
    # 가장 큰 것을 대표로 저장하면 Qt가 나머지 크기를 함께 담는다
    biggest = images[-1]

    # 두 형식을 모두 만든다. Windows는 .ico, macOS는 .icns만 읽는다.
    # 어느 쪽에서 빌드하든 둘 다 있으면 spec이 골라 쓰기만 하면 된다.
    made = []
    for name, fmt in (("app_icon.ico", "ICO"), ("app_icon.icns", "ICNS")):
        path = folder / name
        if biggest.save(str(path), fmt):
            made.append(path)
        else:
            print(f"  건너뜀 {name} — 이 환경의 Qt가 {fmt} 저장을 지원하지 않음")

    if not made:
        raise SystemExit("아이콘을 하나도 저장하지 못했어요")

    # 미리보기(PNG)도 남겨 눈으로 확인하기 쉽게 한다
    preview = folder / "app_icon_preview.png"
    biggest.save(str(preview), "PNG")

    for path in made:
        print(f"아이콘 생성: {path} ({path.stat().st_size:,} bytes)")
    print(f"미리보기   : {preview}")
    del app


if __name__ == "__main__":
    main()
