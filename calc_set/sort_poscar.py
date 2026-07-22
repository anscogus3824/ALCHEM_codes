#!/usr/bin/env python3

from ase import io
structure = io.read('POSCAR')
structure.write('POSCAR_atom_sorted', sort=True)
