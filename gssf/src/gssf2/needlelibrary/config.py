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


import os

# Support multiple OCC versions - this module avoids repetition of logic
try:
    from OCC.StlAPI import *
    from OCC.STEPControl import *
    OCCVersion="0.16"
except:
    try:
        from OCC.DataExchange import STL as STL
        from OCC.DataExchange import STEP as STEP
    except:
        from OCC.Utils.DataExchange import STL as STL
        from OCC.Utils.DataExchange import STEP as STEP
    OCCVersion="0.12"

template_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
