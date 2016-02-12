# Lesion-Extracting GSSF Component

This component wraps a separate tool, [go-smart-lesion](#go-smart-lesion), which uses
[VTK](http://www.vtk.org) routines to extract a lesion surface. More generally,
this component extracts an isosurface based on certain criteria.

## Configuration

When running *go-smart-lesion* as part of the GSSF workflow, the Python component can be configured as follows:

```xml
    <lesion field="FIELD"
            [ threshold_lower="THRESHOLDLOWER" ] [ threshold_upper="THRESHOLDUPPER" ] 
            [ selection="(most-recent|largest-time):most-recent" ]
            [ connectivity="BOOL:false" ]
            [ scaling="FLOAT" ] />
```

If `scaling` is omitted, the inverse of
[`simulationscaling`](../regions.md#geometry) is used. This returns the simulation
to the original, input length scale. If `connectivity` is `true`, the largest
component only will be extracted. To choose a specific simulation timeslice for
input, the `selection` attribute can be set to either `most-recent`, for the
most recently modified file in the [Elmer](elmer.md) output directory, or
`largest-time` to choose the timeslice with the highest timestep suffix. On a
clean run, these should pick the same output VTU file. The `THRESHOLDUPPER` and
`THRESHOLDLOWER` values, if provided, will be used in a VTK `ThresholdBetween`
call. If only one is provided, `ThresholdUpper` or `ThresholdLower` will be
used. Note that this is the reverse of the VTK definition - we treat
`THRESHOLDUPPER` as the maximum accepted value within the lesion, and
`THRESHOLDLOWER` as the minimum. `FIELD` should be a field present in the VTU
file, which should correspond to variables output from the SIF template. Note
that Elmer seems to lowercase variable names before output, so `FIELD` should
also be lowercase even if the SIF template uses mixed/uppercase.

## go-smart-lesion

*go-smart-lesion* may be run standalone from the shell. If so, the syntax is as follows:

    go-smart-lesion OPTIONS

### Optional arguments

Argument                                      | Description
----------------------------------------------|------------
    `-h [ --help ] `                          | produce help message
    `-t [ --threshold-lower ] arg`            | threshold for chosen variable (remove cells with values below this limit)
    `-T [ --threshold-upper ] arg`            | threshold for chosen variable (remove cells with values above this limit)
    `-S [ --scale ] arg (=1)`                 | pre-scaling of results; default 1
    `-f [ --field ] arg`                      | field to threshold on
    `-p [ --parallel ]`                       | assume input data is PVTU not VTU
    `-x [ --threshold ]`                      | switch from using an IsoVolume to using a Threshold
    `-c [ --connectivity ]`                   | extract largest connected component of thresholded surface
    `-s [ --subdivide ]`                      | subdivide before thresholding
    `-i [ --smoothing-iterations ] arg (=0)`  | number of iterations in smoother (0 to skip)
    `-e [ --exclude-subdomain ] arg (=-1)`    | exclude subdomain of given index
    `-i [ --input ] arg`                      | input volume mesh file
    `-a [ --analysis ] arg`                   | analysis output file
    `-o [ --output ] arg`                     | output file
    `-r [ --retain-subdomain-boundaries ]`    | retain all internal inter-zone boundary facets
    `-g [ --geometry-filter ]`                | use geometry filter instead of vtkDataSetSurfaceFilter to extract surface
