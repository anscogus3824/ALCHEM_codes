from pymatgen.io.vasp import Poscar
from pymatgen.symmetry.bandstructure import HighSymmKpath

# Structure loading
structure = Poscar.from_file("POSCAR").structure
kpath = HighSymmKpath(structure)

kpts = kpath.kpath["kpoints"]
paths = kpath.kpath["path"]

# Vasp format
lines = [
    "k points along high symmetry lines",
    " 40              ! number of points per line",
    "line mode",
    "Reciprocal"
]

# Path
for segment in paths:
    for i in range(len(segment) - 1):
        start_label = segment[i]
        end_label = segment[i + 1]
        start_kpt = kpts[start_label]
        end_kpt = kpts[end_label]

        s_coord = " ".join(f"{v:.10f}" for v in start_kpt)
        e_coord = " ".join(f"{v:.10f}" for v in end_kpt)

        lines.append(f"{s_coord}    {start_label}")
        lines.append(f"{e_coord}    {end_label}")
        lines.append("")  # seperate each segment 

# Save
with open("KPOINTS", "w") as f:
    f.write("\n".join(lines).strip() + "\n")

print("[OK] KPOINTS was saved for band structure calculation.")
