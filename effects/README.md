# Effects Folder

This folder contains custom effects, LUTs, and presets for the TikTok Video Editor.

## Folder Structure

```
effects/
├── luts/           # Color grading LUT files (.cube, .3dl)
│   ├── cinematic/  # Cinematic color grades
│   ├── vintage/    # Vintage and retro looks
│   └── modern/     # Modern, vibrant looks
├── presets/        # Effect preset JSON files
└── overlays/       # Video overlay files (future use)
```

## How to Add Effects

### Adding LUTs (Coming Soon)
1. Download LUT files in .cube or .3dl format
2. Place them in the appropriate subfolder under `luts/`
3. LUT support will be added in a future update

### Adding Presets
Create JSON files with effect combinations:

Example `my_preset.json`:
```json
{
  "name": "Social Media Boost",
  "description": "Perfect for TikTok and Instagram",
  "effects": {
    "effect_sharpness": true,
    "effect_sharpness_intensity": 1.6,
    "effect_saturation": true,
    "effect_saturation_intensity": 1.4,
    "effect_contrast": true,
    "effect_contrast_intensity": 1.2,
    "effect_brightness": false,
    "effect_vintage": false
  }
}
```

## Resources

See `EFFECTS_GUIDE.md` in the root folder for:
- Where to download LUTs
- Effect usage tips
- Recommended settings
- Troubleshooting

## Current Features

✅ Built-in effects (Resilience, Vibrance, HDR, Brightness, Vintage)
🔄 LUT support (coming soon)
🔄 Preset loading (coming soon)
🔄 Video overlays (coming soon)
