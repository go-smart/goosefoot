// Copyright (C) 2012 Benjamin Kehlet
//
// This file is part of DOLFIN.
//
// DOLFIN is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// DOLFIN is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with DOLFIN. If not, see <http://www.gnu.org/licenses/>.
//
// First added:  2012-10-31
// Last changed: 2012-11-14

// Some utilities for working with cgal polyhedrons


#ifndef __POLYHEDRON_UTILS_H
#define __POLYHEDRON_UTILS_H

#include "self_intersect.h"

class PolyhedronUtils 
{
  static bool _compare_ending(std::string filename, const char* ending);

public:
  static void readSurfaceFile(std::string filename, Exact_polyhedron& p);
  static void readSTLFile(std::string filename, Exact_polyhedron& p);
  static void readVTKFile(std::string filename, Exact_polyhedron& p);
  static void readVTKXMLFile(std::string filename, Exact_polyhedron& p);
  static CGAL::Bbox_3 getBoundingBox(Polyhedron& polyhedron);
  static double getBoundingSphereRadius(Polyhedron& polyhedron);
  static bool has_degenerate_facets(Exact_polyhedron& p, double threshold);
  static void remove_degenerate_facets(Exact_polyhedron& p, const double threshold);

  template <typename Polyhedron>
  bool has_self_intersections(Polyhedron& p)
  {
    typedef typename Polyhedron::Triangle_3 Triangle;
    typedef typename std::list<Triangle>::iterator Iterator;
    typedef typename CGAL::Box_intersection_d::Box_with_handle_d<double,3,Iterator> Box;
    typedef typename std::back_insert_iterator<std::list<Triangle> > OutputIterator;
    
    std::list<Triangle> triangles; // intersecting triangles
    ::self_intersect<Polyhedron::Polyhedron_3, Polyhedron::Kernel, OutputIterator>(p, std::back_inserter(triangles));
    
    // if(triangles.size() != 0)
    //   cout << triangles.size() << " found." << endl;
    // else 
    //   cout << "The polyhedron does not self-intersect." << endl;
    
    return triangles.size() > 0;
  }
};


#endif 

#include "PolyhedronUtils.imp.h"
