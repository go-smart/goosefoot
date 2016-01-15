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

from OCC.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC import gp
from OCC.BRepBuilderAPI import BRepBuilderAPI_Transform as BRepTransform

from . import extentbuilder


# Create an OCC box of given length, width and height
class CuboidBuilder(extentbuilder.ExtentBuilder):

    def make_reference(self, **parameters):
        l = parameters['length']
        w = parameters['width']
        h = parameters['height']
        box_shape = BRepPrimAPI_MakeBox(l, w, h)

        transform = gp.gp_Trsf()
        transform.SetTranslation(gp.gp_Vec(-l / 2, -w / 2, -h / 2))

        shape_transform = BRepTransform(box_shape.Shape(), transform, False)
        shape_transform.Build()
        shape = shape_transform.Shape()

        return shape
