#!/usr/bin/python2

# This file is part of the Go-Smart Simulation Architecture (GSSA).
# Go-Smart is an EU-FP7 project, funded by the European Commission.
#
# Copyright (C) 2013-  NUMA Engineering Ltd. (see AUTHORS file)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# Go-Smart is an EU-FP7 project, funded by the European Commission.
#
# Copyright (C) 2013-  NUMA Engineering Ltd. (see AUTHORS file)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pickle
import argparse
import vtk

# This script is a disappointing work-around for the fact
# that VTK does not support Python 3
parser = argparse.ArgumentParser(description='This is a Py3-Py2 link program for mesh tests')
parser.add_argument('-i', action="store", dest="filename")

args = parser.parse_args()

if args.filename is None:
    print pickle.dumps(None, 2)

vtu_reader = vtk.vtkXMLUnstructuredGridReader()
vtu_reader.SetFileName(args.filename)
vtu_reader.Update()

data = vtu_reader.GetOutput()

number_of_vertices = data.GetNumberOfPoints()
number_of_cells = data.GetNumberOfCells()

print pickle.dumps({'vertices': number_of_vertices, 'cells': number_of_cells})
