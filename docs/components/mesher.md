# Meshing Components in GSSF

These wrap the two primary meshing tools in GSSF: [mesher-cgal](../tools/mesher-cgal.md) and
[GMSH](http://gmsh.info). This gives rise to two (current) subclasses of
`GoSmartMesher`, each providing a component class: [3D-CGAL](#cgal) and
[2D-GMSH](#gmsh). The specific type of component is specified using
the `type` parameter in the XML.

While most applications will use a single volumetric mesh, in certain cases it
may be necessary to use more than one mesh. Both (or more) will then be
available to the SIF template. Particular applications are: a highly detailed
volumetric mesh geometrically embedded in a simplified outer mesh; an
axisymmetric mesh representing a portion of a larger Cartesian problem.

At least at present, meshing components are expected to output an MSH file. This
makes linkage more straightforward to the [ElmerGrid](elmergrid.md) component.

## Configuration

The relevant second-level element in GSSF-XML is:

```xml
    <mesher [ skip="SKIP:false" ] type="(CGAL|axisymmetric)">
        [ <inner type="(CGAL|axisymmetric)" name="INNERNAME" template="TEMPLATE"
                 [ region="INNERREGION" ] [ needle="(inner_only|outer_only|both):both" ]>
              <!-- see CGAL/axisymmetric-specific sections -->
          </inner> ]
          <!-- see CGAL/axisymmetric-specific sections -->
    </mesher>
```

As a workaround for incomplete re-use of existing 2D meshes, `SKIP` may be
`outer` instead of a boolean, to re-use an existing primary 3D mesh, but
regenerate any inner (usu. 2D) meshes. In the case that there are no inner
meshes (most cases), this is equivalent to `true`.

The `inner` parameter `template`, allows you to specify the template used for
the inner mesh - this is normally an axisymmetric needle geometry from the GSSF
library. The `needle` attribute allows you to indicate in which mesh the needle
should be embedded, (although axisymmetric templates may not always adjust for
this parameter). The `INNERREGION` allows you to specify a [region](../regions.md)
that should form an outer boundary for the inner mesh - this is currently implemented
only in the case of volumetric meshes, but strictly it could be extended to both.

**TODO**: Allow user-supplied inner templates. Account for multiple needles when using inner meshes.

## 3D-CGAL

This is a component wrapping [mesher-cgal](../tools/mesher-cgal.md).

### Configuration

This is configured, extending the `<mesher>` or `<inner>` sections, as follows:

```xml
   <mesher|inner zone_boundaries="BOOL:false">
     <!-- as in general configuration then -->
       <lengthscales nearfield="NF" farfield="FF" [ zonefield="ZF:(float|'ignore')" ]
                     [ needlezonefield="NZF" ] [ granularity="GRANULARITY:float" ]
                     [ vessels="(near|far)" ] [ needles="near" ] [ zones="solid" ]
                     [ zone_radius="ZONERADIUS:float" ] />
     ( <extent radius="EXTENTRADIUS" /> | <extent region="REGIONNAME" /> )
     [ <centre x="CX" y="CY" z="CZ" radius="CR" /> ]
       <zone|needle region="REGIONNAME" [ characteristic_length="ZCL" ] [ priority="ZP" ]>
         [ <activity x="AX" y="AY" z="AZ" r="AR" /> ]
       </zone|needle>
       ...
     [ <organ region="REGIONNAME"/> ]
       <surface region="REGIONNAME"/>
       ...
   </mesher|inner>
```

The `surface` is any boundary region (was previously `vessel`) and requires only
the name of the `region` as expressed in the [regions](../regions.md) section. All
global discretization information is contained in the lengthscales tag, which
provides parameters for the characteristic length field. The `extent` may be
supplied as a radius about the `centre` or as a region. The `organ`, which is
intersected with the `extent`, may be supplied separately as a region. Needles,
if simply surfaces, only need a `REGIONNAME` but if a zone, or both, may use the
extended zone attribute set.

Zones have, at least, a `REGIONNAME` but they may also have their own
characteristic length field and priority, which indicates which zones obscure
which in an overlap. Optionally, there may be a child `activity` node,
specifying a sphere of activity. The inactive region will be added as a new
region to the global regions map.

## 2D-GMSH

[GMSH](http://gmsh.info) is used to mesh 2D domains, primarily for use in
axisymmetric problems.

### Configuration

This is configured, extending the `<mesher>` or `<inner>` sections, as follows:

```xml
   <mesher|inner>
     <!-- as in general configuration then -->
     <template name="TEMPLATENAME" height="HEIGHT" width="WIDTH">
        <dimension name="DIMENSIONNAME" value="DIMENSIONVALUE:float" />
     </template>
     <lengthscales nearfield="NEARFIELD" farfield="FARFIELD" />
   </mesher|inner>
```

The `TEMPLATENAME` parameter indicates a library template to use (effectively a
GMSH *.geo* template). The template may use `$CONSTANT_XYZ` to refer to
dimension `XYZ` and `$INNERHEIGHT` or `$INNERWIDTH` to refer to `HEIGHT` or
`WIDTH`, respectively. It may use `$NEARFIELD` and `$FARFIELD` to get the
`NEARFIELD` and `FARFIELD` parameters, which should together be sufficient to
set the characteristic lengths for GMSH. The template also has access to the
[region](../regions.md) IDs, which is prior to renumbering, but allows multiple
mesher components to number consistently. These use the same constant naming
scheme as the [Elmer](elmer.md) SIF template (`REGION_ORGAN`, etc.). To parse
the template,
[string.Template](https://docs.python.org/3/library/string.html#template-strings)
is used.

**TODO**: Confirm this has no axisymmetric-specific behaviour and rename it to GMSH. Add support for supplied (non-library) templates.

## Renumbering

For Elmer to process a SIF file, numbering of bodies (volumetric subdomains)
must be contiguous. We use a application-level routine,
`GSSF.renumber_bodies(msh_files)`, to achieve this,
after all other preliminary steps have been performed and we know exactly
which subdomains appear in the simulation mesh. After this,
[ElmerGrid](elmergrid.md) is applied to convert to Elmer's meshing format. The output of
this step, not itself a full component, is in `meshes-reordered/`. Other than
numbering, these meshes should match those output by the optimizer in `optimizer/`.

**TODO**: to renumber in two steps, the mesh indices are temporarily replaced with characters using an ASCII mapping. This creates an artifical restriction to 26 subdomains, which could be avoided by a more elegant solution.
