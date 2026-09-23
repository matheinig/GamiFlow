The Baking Sets are comprised of the Low-Poly set and the High-Poly sets. This is where the meshes used for baking and painting will be generated.

# Side panel

The side panel in the 3D viewport (in object mode) is where you can generate the Low and High-poly sets and export them. 


# Object panel

The object properties panel has a *Gamiflow* section. In its *Bake* subsection, you can control the Low/High poly generation behaviour.

- **Type**: How GamiFlow will deal with this object.
   - Standard: The default state of an object. It will get processed and generate an object in the Low and High sets.
   - Projected: This object is only intended to be projected onto another one. It will not be unwrapped or exported.
   - Decal: Deprecated, only kept for compatibility reasons. Use *Projected* with **Single-Sided** instead.
   - Non-Baked: This object will be exported, but its UVs or materials will not be changed. Used for objects that use pre-made textures.
   - Occluder: Only used to cast AO during the bake. Can be used to 'ground' the material.
   - Ignored: The object will not be processed at all. 
- **Include self**: When disabled, this object's geometry will not be used to generate the high-poly. This is used when you have a custom retopology of a sculpt and you want its highpoly to only contain the original sculpt.
- **Single-sided**: This object will bake in single-sided mode.
- **Projections**: This is a list of objects that will be projected onto this one. Click on the + to add a new object. This is how you can assign one or multiple sculpts to be projected onto a low-poly object.
- **Anchor**: This can be used to teleport this object to another location. Useful if you need to 'explode' the object before baking (either to avoid artifacts, or to simplify the painting process).
- **Leave ghost**: When using an anchor, enabling it means that a copy of the object will be left in its original place as an occluder
- **Bake pose**: The action to be used in the Low and High-poly sets. For example this can be used to make sure a character has their mouth semi-open when baking the inside of their mouth. Newer versions of Blender also require a pose slot to be assigned, but these are not directly selectable, so the *Set Bake Slot* can be used to choose an action and a compatible pose slot.
- **Cage offset**: When using a baking cage, this can be used to override the global cage distance. 
- **Add tightness map**: When using a baking cage, a vertex map can be used for finer control of the cage offset.

# Tips

- You are not supposed to manually fix issues in the generated sets. Fixes should be done in your working set, before regenerating the Low/High sets. If you enter edit mode in a generated set, the background will have a red vignette to remind you that it is probably a mistake.

- You do not usually need to inspect the Low/High sets, and msot of the time, they can be exported directly. But it is useful to have a look at them if you have very unexpected bake results.

- Don't forget to regenerate the Low/High sets when you make changes to the working set.

- Not every change requires both sets to be regenerated. For examples, changes in UVs do not have any impact on the high-poly set. This is probably only relevant if generation takes a significant amount of time.