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

from OCC.StlAPI import StlAPI_Writer as Stl

from OCC import gp
from OCC.BRepBuilderAPI import BRepBuilderAPI_Transform as BRepTransform

import os
import numpy as N
from slugify import slugify

from .config import *

REFERENCE_SCALING = 0.001


# Manipulate the needle shape, and write out a final STL when ready
class Manipulator:

    def __init__(self, logger, needle_id=None, filename=None):
        self.logger = logger
        self.origin = gp.gp_Pnt(0, 0, 0)

        # A single needle can have multiple shapes, in theory only one or two as
        # there is no defined use for higher numbers and the STLs will be
        # expected to represent individual surfaces.
        self.shapes = []

        # If we have a needle_id, then there is a template needle this should
        # match to
        if needle_id is not None:
            step = os.path.join(template_directory, "needles/STEP", "%s.step" % slugify(unicode(needle_id)))
        # Alternatively, we should have a file containing the needle STEP
        elif filename is not None:
            step = filename
        else:
            self.logger.print_fatal("No needle file defined")

        self.read_step(step)
        self.logger.print_line(step)

    def read_step(self, filename):
        if OCCVersion == "0.16":
                step_importer = STEPControl_Reader()
        else:
                step_importer = STEP.STEPControl_Reader()

        # Required as the STEP importer otherwise segfaults (not kidding)
        if not os.path.exists(filename):
            raise IOError("STEP file missing: %s" % filename)

        step_importer.ReadFile(str(filename))

        # How many possible shapes?
        number_of_roots = step_importer.NbRootsForTransfer()
        self.logger.print_line("Found %d roots" % number_of_roots)
        step_importer.TransferRoots()

        # How many actual shapes?
        number_of_shapes = step_importer.NbShapes()
        self.logger.print_line("Shapes: %d" % number_of_shapes)

        # Add them to our own list
        for i in range(number_of_shapes):
            shape = step_importer.Shape(i + 1)
            self.shapes.append(shape)

        # If two are found, they are treated as a pair describing the 'active'
        # and 'inactive' parts of a needle, with interpretation left to the
        # modelling components of the workflow
        if len(self.shapes) == 0:
            self.logger.print_fatal("No shapes in STEP file")
        elif len(self.shapes) > 2:
            self.logger.print_line("Too many shapes in STEP file")
        elif len(self.shapes) > 1:
            self.logger.print_line("Found active-inactive pair")

    def scale(self, scaling):
        if scaling is None:
            scaling = 1.0

        transform = gp.gp_Trsf()
        transform.SetScale(self.origin, REFERENCE_SCALING / scaling)

        for i, needle in enumerate(self.shapes):
            needle_transform = BRepTransform(needle, transform, False)
            needle_transform.Build()
            self.shapes[i] = needle_transform.Shape()

    def reorient(self, z_target_axis):
        # Note that needles are expected to lie along the z-axis with tip at the
        # origin.
        z_axis = [0, 0, 1]
        rot_axis = N.cross(z_axis, z_target_axis)
        if N.linalg.norm(rot_axis) > 1e-6:
            rotation_axis = gp.gp_Ax1(self.origin, gp.gp_Dir(*rot_axis))
            rotation_angle = N.arccos(N.dot(z_axis, z_target_axis) / (N.linalg.norm(z_axis) * N.linalg.norm(z_target_axis)))

            transform = gp.gp_Trsf()
            transform.SetRotation(rotation_axis, rotation_angle)

            for i, needle in enumerate(self.shapes):
                needle_transform = BRepTransform(needle, transform, False)
                needle_transform.Build()
                self.shapes[i] = needle_transform.Shape()

    def translate(self, target):
        transform = gp.gp_Trsf()
        transform.SetTranslation(gp.gp_Vec(*target))

        for i, needle in enumerate(self.shapes):
            needle_transform = BRepTransform(needle, transform, False)
            needle_transform.Build()
            self.shapes[i] = needle_transform.Shape()

    def write_stl(self, filename):
        # The active component or only component has no special suffix. The
        # inactive component, if it exists, has a '.inactive' component.
        stl_writer = Stl()
        stl_writer.SetASCIIMode(True)
        stl_writer.Write(self.shapes[0], filename + '.stl')
        if len(self.shapes) > 1:
            stl_writer = Stl()
            stl_writer.SetASCIIMode(True)
            stl_writer.Write(self.shapes[1], filename + '.inactive.stl')

        # All shapes (even if more than 2, in principle) are also output with a
        # suffix of their position in the STEP file
        for i, shape in enumerate(self.shapes):
            stl_writer = Stl()
            stl_writer.SetASCIIMode(True)
            stl_writer.Write(shape, filename + ('.%d.stl' % i))
