#!/bin/bash

# POTCAR
POTCAR_DIR="/home/shared/pot/PBE54"
OUTPUT_POTCAR="POTCAR"

#maping
declare -A POTCAR_MAP
POTCAR_MAP=(
    ["H"]="H"
    ["He"]="He"
    ["Li"]="Li_sv"
    ["Be"]="Be"
    ["B"]="B"
    ["C"]="C"
    ["N"]="N"
    ["O"]="O"
    ["F"]="F"
    ["Ne"]="Ne"
    ["Na"]="Na_pv"
    ["Mg"]="Mg"
    ["Al"]="Al"
    ["Si"]="Si"
    ["P"]="P"
    ["S"]="S"
    ["Cl"]="Cl"
    ["Ar"]="Ar"
    ["K"]="K_sv"
    ["Ca"]="Ca_sv"
    ["Sc"]="Sc_sv"
    ["Ti"]="Ti_sv"
    ["V"]="V_sv"
    ["Cr"]="Cr_pv"
    ["Mn"]="Mn_pv"
    ["Fe"]="Fe"
    ["Co"]="Co"
    ["Ni"]="Ni"
    ["Cu"]="Cu"
    ["Zn"]="Zn"
    ["Ga"]="Ga_d"
    ["Ge"]="Ge_d"
    ["As"]="As"
    ["Se"]="Se"
    ["Br"]="Br"
    ["Kr"]="Kr"
    ["Rb"]="Rb_sv"
    ["Sr"]="Sr_sv"
    ["Y"]="Y_sv"
    ["Zr"]="Zr_sv"
    ["Nb"]="Nb_sv"
    ["Mo"]="Mo_sv"
    ["Tc"]="Tc_pv"
    ["Ru"]="Ru_pv"
    ["Rh"]="Rh_pv"
    ["Pd"]="Pd"
    ["Ag"]="Ag"
    ["Cd"]="Cd"
    ["In"]="In_d"
    ["Sn"]="Sn_d"
    ["Sb"]="Sb"
    ["Te"]="Te"
    ["I"]="I"
    ["Xe"]="Xe"
    ["Cs"]="Cs_sv"
    ["Ba"]="Ba_sv"
    ["La"]="La"
    ["Ce"]="Ce"
    ["Pr"]="Pr_3"
    ["Nd"]="Nd_3"
    ["Pm"]="Pm_3"
    ["Sm"]="Sm_3"
    ["Eu"]="Eu_2"
    ["Gd"]="Gd_3"
    ["Tb"]="Tb_3"
    ["Dy"]="dy_3"
    ["Ho"]="Ho_3"
    ["Er"]="Er_3"
    ["Tm"]="Tm_3"
    ["Yb"]="Yb_2"
    ["Lu"]="Lu_3"
    ["Hf"]="Hf_pv"
    ["Ta"]="Ta_pv"
    ["W"]="W_sv"
    ["Re"]="Re"
    ["Os"]="Os"
    ["Ir"]="Ir"
    ["Pt"]="Pt"
    ["Au"]="Au"
    ["Hg"]="Hg"
    ["Tl"]="Tl_d"
    ["Pb"]="Pb_d"
    ["Bi"]="Bi_d"
    ["Po"]="Po_d"
    ["At"]="At"
    ["Rn"]="Rn"
    ["Fr"]="Fr_sv"
    ["Ra"]="Ra_sv"
    ["Ac"]="Ac"
    ["Th"]="Th"
    ["Pa"]="Pa"
    ["U"]="U"
    ["Np"]="Np"
    ["Pu"]="Pu"
    ["Am"]="Am"
    ["Cm"]="Cm"
)

if [[ ! -f "POSCAR" ]]; then
    echo "No POSCAR"
    exit 1
fi

sed -i 's/\r$//' POSCAR

LINE=$(sed -n '6p' POSCAR)

if [[ "${LINE: -1}" != " " ]]; then
    sed -i "6s/$/ /" POSCAR
fi

ELEMENTS=$(sed -n '6p' POSCAR)

POTCAR_FILES=()
for ELEMENT in $ELEMENTS; do
    POTCAR_NAME=${POTCAR_MAP[$ELEMENT]}
    if [[ -z "$POTCAR_NAME" ]]; then
        echo "No $ELEMENT maping"
        continue
    fi

    ELEMENT_POTCAR="$POTCAR_DIR/$POTCAR_NAME/POTCAR"
    if [[ -f "$ELEMENT_POTCAR" ]]; then
        POTCAR_FILES+=("$ELEMENT_POTCAR")
    else
        echo "No $ELEMENT_POTCAR file"
    fi
done

# 병합된 POTCAR 파일 생성
if [[ ${#POTCAR_FILES[@]} -eq 0 ]]; then
    echo "No POTCAR file"
    exit 1
fi

cat "${POTCAR_FILES[@]}" > "$OUTPUT_POTCAR"
echo "finish: $OUTPUT_POTCAR"
