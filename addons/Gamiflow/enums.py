gUV_UNWRAP_METHODS = [
        ("ANGLE_BASED", "Angle Based", "", 1),
        ("CONFORMAL", "Conformal", "", 2),
        ("MINIMUM_STRETCH", "Minimum stretch", "", 3),
    ]
gUV_RESOLUTION = [        
        ("512",  "512",  "", 512),
        ("1024", "1024", "", 1024),
        ("2048", "2048", "", 2048),
        ("4096", "4096", "", 4096),
        ("8192", "8192", "", 8192),
    ]
gUV_MARGIN = [        
        ("2",  "2",  "", 2),
        ("4",  "4",  "", 4),
        ("8",  "8",  "", 8),
        ("16", "16", "", 16),
        ("32", "32", "", 32),
        ("64", "64", "", 64)
    ]   
gVERTEX_CHANNEL = [
        ("ZERO", "0", "Value is set to 0", 0),
        ("ONE", "1", "Value is set to 1", 1),
        ("CURRENT", "Current", "Whatever value exists in the currently active vertex color attribute", 2),
        ("AO", "AO", "AO is baked into the channel", 3),
        ("OBJECT_RAND", "Random (Object)", "Random value per object", 4),
        ("ISLAND_RAND", "Random (Island)", "Random value per geometry island", 5),
    ]

gPROJECTION_MODES = [
        ("STANDARD", "Standard", "", 0),
        ("PROJECTED", "Projected", "An object used exclusively for baking, for example a sculpt", 1),
        ("DECAL", "Decal (Deprecated ⚠️)", "Use Projected with single-sided faces instead.", 2),
        ("NON_BAKED", "Non-Baked", "Object whose material already exists and isn't supposed to get baked (a generic tiled texture, trim sheet). \nThis object is not processed as much by GamiFlow (UVs and materials are not modified) but will get exported.", 5),
        ("OCCLUDER", "Occluder", "An object used exclusively for baking, but only as a shadow caster", 3),
        ("IGNORED", "Ignored", "This object will be completely ignored", 4),
    ]    