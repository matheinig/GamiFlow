GamiFlow enables a non-destructive workflow when creating game assets. It adds meta-data to your objects so that low and high poly meshes can be automatically generated and sent to Substance Painter for baking.

# How to

## Sets
Gamiflow works with multiple *sets* (which really just means "collection") which all have a specific use:
- Working set: what you will be interacting with. this is where you will model and unwrap your objects.
- Bake sets: geometry generated automatically from the Working Set.
  - Low: what is used as base mesh in Substance Painter
  - High: what is used to bake normals, AO, and id masks.
- Export set: the final optimised geometry, also auto-generated.
You technically only ever need to look at the Bake and Export sets to check that everything is correct.

Before you can begin working with Gamiflow, you need to set your **Working Set** in the side panel.
Later on, once you've generated the other sets, you can easily navigate between sets using the buttons at the top: click to jump to the set, and ctrl-click to toggle a set.

## Non-destructive workflow
The idea is that you should be able to model once, tag some edges or modifiers, set your uv seams, and then automatically generate your low and high poly meshes. You should never have to manually duplicate meshes and dissolve some edges to make your low-poly.

### High-poly modifiers
Some modifiers, (such as subdivision or bevel modifiers) are usually not desirable for a game asset, but crucial for the high-poly mesh used during the bake process. As such there is a (albeit hacky) way to tag modifiers as being intended for high-poly only. Untick the modifier's *Render* button (the camera icon), and it will be ignored when generating low-poly meshes.
There is a shortcut to create a quick high-poly bevel in the Shift-V pie menu (in object mode).

### Dissolving edges
In edit mode, select edges you only want to see in the high-poly, and press Shift-V to bring up the pie menu. Select *Mark High Detail*, and the edges should now be marked in yellow. If you want to revert the edges to their standard state, select *Mark Regular Detail*.

### Custom High-Poly
Sometimes a simple edge dissolve won't do it and you do need two very different meshes (e.g. a super dense sculpt and its retopo). In this case, you can change the object's bake settings. First, disable *Include self* (this means this object won't get pushed to the bake sets), then click the + icon and pick your sculpt. Make sure the high-poly object type is set to **Projected**.

### Auto-UVs
**!!!OPINION WARNING!!!**
You should (almost) never have to manually pack your UV islands, this is a waste of time and will only make you scared of modifying your assets later on. My preferred workflow is to manually place UV seams as usual, but then let the unwrapper and packer do everything for me. There are ways to tag edges that need to have a specific alignment in UV space, or to tag faces that need to be neatly "gridified", or to tweak the size of some UV islands. And if you're adamant that your manually unwrapping is superior than the automatic one, you can always tell Gamiflow to keep it as is. This should be enough to deal with the vast majority of needs.

Each object has a UDIM assigned. All objects sharing a UDIM will be packed together in the same [0,1[ UV square. Each UDIM will essentially become a distinct material in the game engine with its own set of textures. The UDIM name is what Substance Painter will use as name for its texture set.

### Anchors
Sometimes, things get in the way. Imagine you modelled a gun with its ammo magazine inside, making it difficult to texture it. You can set a *Bake Anchor* on the magazine. When generating the Bake Sets, the magazine will be teleported to its anchor.


