The Export Set contains the final mesh ready to be exported to a game engine. In simple cases it should be (geometrically speaking) identical to the Low Poly set that was used for baking. There will be differences in how the object hierarchy is organised because objects can be merged. Levels of detail can also be automatically generated.

# Side panel
The side panel in the 3D viewport (in object mode) is where you can generate the Export set and export it.

## Export presets
The target dropdown lets you choose between multiple applications. These presets are primarily aimed at exporting with the right orientation.
The format dropdown lets you choose between file formats. The Custom option lets you use your own settings based on the export collection export settings. After having generated the Export Set, select the collection, go to its settings, and add an exporter that suits you. Then if the Gamiflow export is set to custom, click on the **Export** button will be equivalent to clicking on the collection's **Export All** button.
## Extra generation settings
- Lightmap UVs: a new UV layer will be created for lightmap UVs. All objects will be reunwrapped after their geometry have been processed (this means mirrors and array modifiers will no longer have stacked UVs)
- Generate vertex colors: lets you choose what happens to the R, G, and B channels individually. You can force the values to be 0, 1, whatever is currently stored in the mesh, but also bake custom values such as ambient occlusion, a random per-object value, or a random per-island value.
## Extra export settings
- Reversed lets you flip the front and back directions when exporting
- Animation lets you enable/disable animations
- Export method: choose between single file (the entire set is exported in one file) and kit (each root gets exported to a separate file)

# Object panel
The object properties panel has a *Gamiflow* section. In its *Export* subsection, you can control the per-object export behaviour.

## Level of detail
- **Final LOD**: Level after which this object and its children will stop appearing.
- **Allow decimation**: Controls whether this object can get decimated during LOD generation.

## Export anchors
The current object will be moved to the defined **Export Anchor**.  This is useful if the object was modeled in the 'wrong' place and you want to correct it when exporting, but without breaking your scene. Multiple anchors can be added, each creating an instance of the object (for example for creating the 4 wheels of a car from one source object).

## Export pose
This is used to define which action the object will use in the export set. The interface is a bit awkward because of Blender's new animation slot. 

## Mesh options
- **Merge with parents**: when enabled, this object will be merged with its parents. This should be disabled if an object is supposed to be animated independantly
- **Double-sided**: when enabled, the mesh geometry will be duplicated and flipped. Useful when a game engine doesn't handle double-sided shaders gracefully or when you don't want to use a double-sided shader on a tiny part of a larger model.