#! /home/bogeun1007/anaconda3/bin/python

import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
import os

print("KPOINTS 파일과 vasprun.xml 파일을 분석 중입니다...")

# 1. KPOINTS 파일 읽어서 라벨 및 분할 수(ndiv) 추출
ndiv = 0
labels = []
if os.path.exists("KPOINTS"):
    with open("KPOINTS", "r") as f:
        lines = f.readlines()
        ndiv = int(lines[1].strip()) # 2번째 줄에 있는 분할 수 (20)
        for line in lines[4:]:       # 5번째 줄부터 K-point 데이터
            parts = line.split()
            if len(parts) >= 4:
                labels.append(parts[3])
else:
    print("에러: KPOINTS 파일이 없습니다.")
    exit()

# 2. vasprun.xml 파일 읽기
tree = ET.parse('vasprun.xml')
root = tree.getroot()

# 페르미 에너지 추출
efermi = 0.0
for i in root.iter('i'):
    if i.get('name') == 'efermi':
        efermi = float(i.text)
        break

# K-point 좌표 추출
kpoints = []
for varray in root.iter('varray'):
    if varray.get('name') == 'kpointlist':
        for v in varray.findall('v'):
            kpoints.append([float(x) for x in v.text.split()])
        break
kpoints = np.array(kpoints)

# 3. K-path 거리 계산 및 라벨 위치 매핑
k_dist = np.zeros(len(kpoints))
tick_locs = []
tick_labels = []

tick_locs.append(0.0)
tick_labels.append(labels[0])

label_idx = 0
for i in range(1, len(kpoints)):
    if i % ndiv == 0:
        # 경로가 끊어지고 점프하는 구간 (거리를 늘리지 않음)
        k_dist[i] = k_dist[i-1]

        # 라벨 처리 (예: U 끝, K 시작 -> 위치는 같은데 라벨은 U|K 로 표시)
        prev_label = labels[label_idx + 1]
        next_label = labels[label_idx + 2]
        if prev_label != next_label:
            tick_labels[-1] = f"{prev_label}|{next_label}"

        label_idx += 2
    else:
        # 연속된 경로의 거리는 피타고라스 정리로 누적 계산
        diff = kpoints[i] - kpoints[i-1]
        k_dist[i] = k_dist[i-1] + np.linalg.norm(diff)

    # 각 선분의 끝점인 경우 눈금 위치와 라벨 저장
    if (i + 1) % ndiv == 0:
        tick_locs.append(k_dist[i])
        tick_labels.append(labels[label_idx + 1])

# GAMMA 문자를 보기 좋게 일반 텍스트 Γ 로 변경
tick_labels = [lbl.replace("GAMMA", "Γ") for lbl in tick_labels]

# 4. 밴드 에너지(Eigenvalues) 추출
bands_spin_up = []
bands_spin_down = []

eigenvalues_block = root.find('.//calculation/eigenvalues')
if eigenvalues_block is not None:
    for set_elem in eigenvalues_block.iter('set'):
        if set_elem.get('comment') == 'spin 1':
            for kpt_set in set_elem.findall('set'):
                bands_spin_up.append([float(r.text.split()[0]) for r in kpt_set.findall('r')])
        elif set_elem.get('comment') == 'spin 2':
            for kpt_set in set_elem.findall('set'):
                bands_spin_down.append([float(r.text.split()[0]) for r in kpt_set.findall('r')])

bands_spin_up = np.array(bands_spin_up).T - efermi
if len(bands_spin_down) > 0:
    bands_spin_down = np.array(bands_spin_down).T - efermi

# 5. 그래프 그리기
plt.figure(figsize=(8, 6))

# 스핀 업/다운 그리기
for i in range(bands_spin_up.shape[0]):
    plt.plot(k_dist, bands_spin_up[i], color='royalblue', linewidth=1.5,
             label='Spin Up' if i == 0 else "")

if len(bands_spin_down) > 0:
    for i in range(bands_spin_down.shape[0]):
        plt.plot(k_dist, bands_spin_down[i], color='crimson', linewidth=1.5, linestyle='--',
                 label='Spin Down' if i == 0 else "")

# 6. 디자인 및 축 설정
plt.axhline(y=0, color='black', linestyle=':', linewidth=1.5, label='Fermi Energy')

# 대칭점(High-symmetry points) 위치에 세로선 그어주기
for loc in tick_locs:
    plt.axvline(x=loc, color='black', linestyle='-', linewidth=0.5)

plt.xlim(tick_locs[0], tick_locs[-1])
plt.ylim(-10, 10)
plt.ylabel("Energy - Fermi Energy (eV)", fontsize=14)
plt.title("Band Structure", fontsize=16)

# ★ 여기가 핵심: X축에 계산된 거리 위치마다 KPOINTS 라벨 달아주기
plt.xticks(tick_locs, tick_labels, fontsize=14)

# 범례 정리
handles, labels = plt.gca().get_legend_handles_labels()
by_label = dict(zip(labels, handles))
plt.legend(by_label.values(), by_label.keys(), loc='upper right')

plt.tight_layout()
plt.savefig("band_structure.png", dpi=300)
print("성공! K-path 문자가 예쁘게 들어간 band_structure.png 파일이 생성되었습니다.")
