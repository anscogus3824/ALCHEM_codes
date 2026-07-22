#! /home/bogeun1007/anaconda3/bin/python

import numpy as np
import matplotlib.pyplot as plt

# DOSCAR 읽기
with open("DOSCAR", "r") as f:
    lines = f.readlines()

# 페르미 에너지 및 NEDOS 추출
nedos = int(lines[5].split()[2])
e_fermi = float(lines[5].split()[3])

# 데이터 파싱
data = np.loadtxt(lines[6:6+nedos])
energy = data[:, 0] - e_fermi

# 그림 설정
plt.figure(figsize=(8, 6))

if data.shape[1] == 5:
    # 스핀 분극 (Spin-polarized)
    dos_up = data[:, 1]
    dos_down = data[:, 2]
    plt.fill_between(energy, dos_up, 0, color='royalblue', alpha=0.5, label='Spin Up')
    plt.fill_between(energy, -dos_down, 0, color='crimson', alpha=0.5, label='Spin Down')
else:
    # 비분극 (Non-spin-polarized)
    dos = data[:, 1]
    plt.fill_between(energy, dos, 0, color='royalblue', alpha=0.5, label='Total DOS')

# 페르미 기준선 추가 및 축 설정
plt.axvline(x=0, color='black', linestyle='--')
plt.axhline(y=0, color='black', linewidth=1)
plt.xlim(-10, 10)
plt.xlabel("Energy - Fermi Energy (eV)", fontsize=14)
plt.ylabel("DOS (states/eV)", fontsize=14)
plt.title("Density of States", fontsize=16)
plt.legend()
plt.tight_layout()

# 고해상도로 이미지 저장
plt.savefig("dos_python_result.png", dpi=300)
print("dos_python_result.png 저장 완료!")
