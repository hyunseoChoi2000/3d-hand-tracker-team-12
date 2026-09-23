"""
카메라 3대를 동시(같은 시각)가 아니라, cam1 -> cam2 -> cam3 순서로
약 0.03초(기본값) 간격을 두고 순차적으로 촬영하는 스크립트.

- 각 라운드(round)마다 cam1 -> 0.03초 대기 -> cam2 -> 0.03초 대기 -> cam3 순으로 촬영
- 촬영된 각 프레임은 실제 촬영 시각(perf_counter 기준, epoch 기준 둘 다)을 기록
- 이미지 파일과 함께 timestamps.csv 로 각 프레임의 정확한 촬영 시각을 저장
  (완벽히 0.03초를 보장하지는 않음. sleep/카메라 read 지연에 따라 오차가 있을 수 있음.
   오차 정도를 확인하고 싶다면 timestamps.csv의 실제 time_epoch 값 차이를 보면 됨)

사용 예:
    python capture_staggered_cameras.py --num-rounds 100 --interval 0.03 \
        --cam-indices 0 1 2 --out-dir ./captured_data
"""

import argparse
import csv
import os
import time
from datetime import datetime

import cv2


def open_cameras(cam_indices):
    caps = []
    for idx in cam_indices:
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            for opened in caps:
                opened.release()
            raise RuntimeError(f"카메라 인덱스 {idx} 를 열 수 없습니다.")
        caps.append(cap)
    return caps


def capture_one(cap, cam_id, round_idx, out_dir):
    ok, frame = cap.read()
    t_epoch = time.time()
    t_perf = time.perf_counter()

    if not ok:
        return None

    filename = f"cam{cam_id}_round{round_idx:05d}.jpg"
    filepath = os.path.join(out_dir, filename)
    cv2.imwrite(filepath, frame)

    return {
        "round": round_idx,
        "cam_id": cam_id,
        "filename": filename,
        "time_epoch": t_epoch,
        "time_readable": datetime.fromtimestamp(t_epoch).strftime("%H:%M:%S.%f"),
        "time_perf_counter": t_perf,
    }


def main():
    parser = argparse.ArgumentParser(description="3대 카메라를 0.03초 간격으로 순차 촬영")
    parser.add_argument("--cam-indices", type=int, nargs=3, default=[0, 1, 2],
                         help="OpenCV 카메라 인덱스 3개 (기본: 0 1 2)")
    parser.add_argument("--interval", type=float, default=0.03,
                         help="카메라 간 촬영 간격(초), 기본 0.03")
    parser.add_argument("--num-rounds", type=int, default=50,
                         help="총 몇 라운드(3대 모두 1번씩 찍는 것을 1라운드) 촬영할지")
    parser.add_argument("--round-interval", type=float, default=0.0,
                         help="한 라운드가 끝난 뒤 다음 라운드 시작 전 대기 시간(초)")
    parser.add_argument("--out-dir", type=str, default="./captured_data",
                         help="이미지와 timestamps.csv 를 저장할 폴더")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, "timestamps.csv")

    caps = open_cameras(args.cam_indices)

    fieldnames = ["round", "cam_id", "filename", "time_epoch", "time_readable", "time_perf_counter"]

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for round_idx in range(args.num_rounds):
                for order, (cap, cam_id) in enumerate(zip(caps, args.cam_indices)):
                    record = capture_one(cap, cam_id, round_idx, args.out_dir)
                    if record is None:
                        print(f"[경고] round {round_idx}, cam {cam_id} 프레임 읽기 실패")
                        continue

                    writer.writerow(record)
                    print(f"round={round_idx} cam={cam_id} time={record['time_readable']}")

                    is_last_cam_in_round = (order == len(caps) - 1)
                    if not is_last_cam_in_round:
                        time.sleep(args.interval)

                if args.round_interval > 0:
                    time.sleep(args.round_interval)

    finally:
        for cap in caps:
            cap.release()

    print(f"\n촬영 완료. 이미지 및 timestamps.csv 저장 위치: {os.path.abspath(args.out_dir)}")


if __name__ == "__main__":
    main()
