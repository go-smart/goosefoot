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

from .config import *
from OCC import gp

from OCC.BRepBuilderAPI import BRepBuilderAPI_Transform as BRepTransform


# Define a simulation extent, based on case-specific parameters, with methods to
# transform to the required target. Derived classes implement specific shapes.
class ExtentBuilder:

    def __init__(self, logger, centre, radius, **parameters):
        # We nearly always need a centre (focal point in some sense) and radius
        self.logger = logger
        self.centre = centre
        self.radius = radius
        self.origin = gp.gp_Pnt(0, 0, 0)
        self.parameters = parameters

    def make_reference(self, **parameters):
        raise RuntimeError("Implement this - derived from ExtentBuilder")

    def build(self):
        # Get the subclass-specific reference shape
        shape = self.make_reference(**self.parameters)

        # Transform it as required by our initializing parameters
        transform = gp.gp_Trsf()
        transform.SetScale(self.origin, self.radius)

        shape_transform = BRepTransform(shape, transform, False)
        shape_transform.Build()
        shape = shape_transform.Shape()

        transform = gp.gp_Trsf()
        transform.SetTranslation(gp.gp_Vec(*self.centre))

        shape_transform = BRepTransform(shape, transform, False)
        shape_transform.Build()
        self.shape = shape_transform.Shape()

    def translate(self, target):
        transform = gp.gp_Trsf()
        transform.SetTranslation(gp.gp_Vec(*target))

        # FIXME: this needs some explanation... should it be here?
        needle_transform = BRepTransform(self.needle, transform, False)
        needle_transform.Build()
        self.needle = needle_transform.Shape()

    def write_stl(self, filename):
        if OCCVersion == "0.16":
                stl_writer = StlAPI_Writer()
                stl_writer.Write(self.shape, filename)
        else:
                stl_writer = STL.STLExporter(filename, True)
                stl_writer.set_shape(self.shape)
                stl_writer.write_file()
