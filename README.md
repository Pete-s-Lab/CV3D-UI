# CV3D UI

CV3D UI is the desktop workflow manager for CV3D. It guides compound-eye datasets from image-volume or STL input through surface extraction and inspection, facet detection and checking, landmark-based alignment, optical metrics, corneal projection, mirroring, quality control, and analysis-ready export.

The quantitative R analyses are provided by the companion **CV3D** R package.

Step 05A uses CV3D's local tangent-plane neighbour detection before calculating facet size, facet normals, interfacet angles, and derived optical metrics.

## Requirements

The workflow uses:

- Python with PySide6 for the desktop interface;
- R with the CV3D package for quantitative analyses;
- Fiji/ImageJ for image-volume preprocessing and STL extraction when starting from volumetric data; and
- Blender for interactive corneal-surface preparation and facet checking.

The paths to external executables and helper scripts are configured on the **Settings** page of the application.

## Launch

From the `CV3D_UI` directory:

```text
python CV3D_app.py
```

## Spatial units

CV3D currently assumes that mesh and point-cloud coordinates are in **micrometres (µm)**. Length-derived outputs therefore use µm, and Snyder's eye parameter is expressed in **µm·rad**. The corneal-projection sphere diameter is entered in **centimetres (cm)** in the UI and converted internally to µm for geometric calculations.

## Documentation

`CV3D_UI_Tutorial.Rmd` contains the current end-to-end workflow tutorial. It should be rendered again after documentation changes before distributing a PDF version.

## Related repository

The R package is maintained at `Pete-s-Lab/CV3D` on GitHub.
