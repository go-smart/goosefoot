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
from OCC.TopoDS import TopoDS_Shape
import os

from . import extentbuilder


# Create an OCC sphere of given radius
class SphereBuilder(extentbuilder.ExtentBuilder):

    def make_reference(self, **parameters):
        filename = os.path.join(template_directory, "needles", "sphere.stl")
        if OCCVersion == "0.16":
                shape = TopoDS_Shape()
                stl_importer = StlAPI_Reader()
                stl_importer.Read(shape, filename)
                return shape
        else:
                stl_importer = STL.STLImporter(filename)
                stl_importer.read_file()
                shape = stl_importer.get_shape()
                return shape
