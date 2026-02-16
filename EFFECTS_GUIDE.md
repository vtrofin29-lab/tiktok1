# Video Effects Guide - CapCut Style Effects

## Overview
This TikTok video editor now includes CapCut-style video effects that can enhance your videos professionally. This guide explains what effects are available, how they work, and where to get additional effect resources.

## Built-in Effects

The application includes 5 CapCut-style effects that can be applied to your videos:

### 1. 💎 Resilience (Sharpness)
- **Description**: Enhances video sharpness and clarity, making details pop
- **Use Case**: Great for product videos, text-heavy content, or when you want crisp details
- **Intensity Range**: 0.5x to 3.0x (default: 1.5x)
- **Effect**: Makes edges sharper and details more defined

### 2. 🌈 Vibrance (Saturation)
- **Description**: Boosts color saturation for more vibrant, eye-catching videos
- **Use Case**: Food videos, nature content, fashion, or any colorful subject
- **Intensity Range**: 0.5x to 2.0x (default: 1.3x)
- **Effect**: Makes colors more vivid and saturated

### 3. ⚡ HDR (Contrast)
- **Description**: Enhances contrast for a more dramatic, HDR-like look
- **Use Case**: Landscapes, dramatic content, or to add depth
- **Intensity Range**: 0.5x to 2.0x (default: 1.2x)
- **Effect**: Deepens blacks and brightens highlights

### 4. ☀️ Brightness Boost
- **Description**: Increases overall brightness without washing out the image
- **Use Case**: Dark videos, indoor content, or moody lighting
- **Intensity Range**: 0.5x to 2.0x (default: 1.15x)
- **Effect**: Lightens the entire image uniformly

### 5. 📽️ Vintage (Film Grain)
- **Description**: Adds film grain and subtle sepia tone for a retro look
- **Use Case**: Nostalgic content, music videos, artistic projects
- **Grain Range**: 0.1 to 1.0 (default: 0.3)
- **Effect**: Adds texture and warm tones

## How to Use Effects

### In the Application:
1. Open the video editor
2. Scroll down to the "Video Effects" section
3. Check the effects you want to apply
4. Adjust intensity sliders for each effect
5. Add to job queue or run directly
6. Effects will be applied during video processing

### Combining Effects:
You can combine multiple effects for unique looks:
- **Social Media Look**: Vibrance + HDR + slight Brightness
- **Professional Clean**: Resilience only at moderate intensity
- **Nostalgic**: Vintage + reduced Saturation
- **Dramatic**: HDR + Brightness + Resilience

## Advanced Effects Resources

### Where to Get Additional Effects

While the built-in effects cover most needs, you can enhance your videos with external resources:

#### 1. LUTs (Lookup Tables)
LUTs are color grading presets used by professional video editors.

**Recommended Sources:**
- **Free LUTs**:
  - RocketStock Free LUTs: https://www.rocketstock.com/free-after-effects-templates/35-free-luts-for-color-grading-videos/
  - CreativeMarket Free Goods: https://creativemarket.com/free-goods (weekly freebies)
  - IWLTBAP Free LUTs: https://iwltbap.com/
  
- **Premium LUTs**:
  - PremiumBeat: https://www.premiumbeat.com/blog/free-luts-color-grading/
  - SmallHD: https://www.smallhd.com/pages/lut-library
  - FilmConvert: https://www.filmconvert.com/

**How to Install LUTs** (for future integration):
1. Create folder: `/effects/luts/`
2. Download .cube or .3dl format LUTs
3. Place LUT files in the luts folder
4. Restart the application
(Note: LUT support will be added in a future update)

#### 2. Video Filters and Presets

**Free Resources:**
- **Filmora Effects**: https://filmora.wondershare.com/effects.html
- **DaVinci Resolve Free Effects**: Available within DaVinci Resolve
- **OBS Studio Filters**: Can export filter configurations

**Installation Instructions**:
Currently, the application uses PIL-based effects. Advanced filters can be applied:
1. Create `/effects/presets/` folder
2. Save preset files (JSON format with effect parameters)
3. Future versions will support preset loading

#### 3. Transitions and Overlays

**Where to Get**:
- **Pixabay**: https://pixabay.com/videos/ (free overlays)
- **Pexels**: https://www.pexels.com/search/videos/overlay/
- **Videezy**: https://www.videezy.com/free-video/overlay

**Installation**:
1. Create `/effects/overlays/` folder
2. Place video overlay files (.mp4, .mov with alpha channel)
3. Future: Use in composition layer

## Creating Custom Effects Folder Structure

For organizing custom effects (future expansion):

```
tiktok1/
├── effects/
│   ├── luts/
│   │   ├── cinematic/
│   │   ├── vintage/
│   │   └── modern/
│   ├── presets/
│   │   ├── my_preset1.json
│   │   └── my_preset2.json
│   └── overlays/
│       ├── light_leaks/
│       ├── film_burns/
│       └── particles/
└── tiktok_full_gui.py
```

To create this structure:
```bash
mkdir -p effects/luts/cinematic effects/luts/vintage effects/luts/modern
mkdir -p effects/presets
mkdir -p effects/overlays/light_leaks effects/overlays/film_burns effects/overlays/particles
```

## Effect Preset Format (JSON)

For saving custom effect combinations:

```json
{
  "name": "My Preset",
  "description": "Custom effect combination",
  "effects": {
    "effect_sharpness": true,
    "effect_sharpness_intensity": 1.8,
    "effect_saturation": true,
    "effect_saturation_intensity": 1.4,
    "effect_contrast": false,
    "effect_brightness": false,
    "effect_vintage": false
  }
}
```

Save this in `effects/presets/my_preset.json`

## Technical Details

### How Effects Are Applied

Effects are applied using PIL (Python Imaging Library) ImageEnhance module:
- **Sharpness**: PIL ImageEnhance.Sharpness
- **Saturation**: PIL ImageEnhance.Color
- **Contrast**: PIL ImageEnhance.Contrast
- **Brightness**: PIL ImageEnhance.Brightness
- **Vintage**: Custom implementation with noise and sepia tone

### Performance Considerations

- Effects are applied frame-by-frame during video processing
- More effects = longer processing time
- Recommended: Use 1-3 effects per video for balance
- Higher intensity values increase processing time slightly
- 4K videos will take longer to process with effects

### Effect Processing Order

Effects are applied in this order:
1. Sharpness (Resilience)
2. Saturation (Vibrance)
3. Contrast (HDR)
4. Brightness
5. Vintage (Film Grain)

This order ensures optimal visual results.

## Tips and Best Practices

### For TikTok/Social Media:
- Use Vibrance + slight HDR for eye-catching content
- Keep Resilience moderate (1.3-1.7x) to avoid over-sharpening
- Brightness boost helpful for indoor content

### For Professional Content:
- Subtle effects work best (intensity 1.1-1.3x)
- Combine Resilience + Contrast for crisp, professional look
- Avoid heavy Vintage unless artistic intent

### For Artistic Projects:
- Experiment with high Vintage grain (0.5-0.8)
- Combine multiple effects for unique signatures
- Try extreme values for creative looks

### Performance Tips:
- Process shorter clips first to test effect combinations
- Use lower intensity for faster processing
- Disable unused effects (unchecked = not processed)

## Troubleshooting

**Effects Not Visible?**
- Ensure effect checkbox is enabled
- Increase intensity slider
- Check that video actually processed (look at logs)

**Processing Too Slow?**
- Disable some effects
- Reduce effect intensity
- Process at 1080p instead of 4K

**Video Looks Over-Processed?**
- Reduce intensity values
- Use fewer combined effects
- Reset to defaults and start subtle

## Future Enhancements

Planned features for effect system:
- [ ] LUT support (color grading files)
- [ ] Effect preset saving/loading
- [ ] Real-time effect preview
- [ ] Custom effect plugins
- [ ] Video overlay support
- [ ] Transition effects
- [ ] AI-powered auto-enhancement

## Additional Resources

### Learning Color Grading:
- YouTube: Search "Color Grading Tutorial"
- Skillshare: Video editing courses
- Udemy: Color grading courses

### CapCut Tutorials:
Study how CapCut applies effects and recreate similar looks with our effects.

### Community Resources:
- Reddit: r/VideoEditing
- Reddit: r/colorgrading
- Discord: Join video editing communities

## Credits

Effects implementation uses:
- PIL (Python Imaging Library)
- MoviePy for video processing
- NumPy for numerical operations

## License

Effects code is part of the tiktok1 project.
LUTs and presets from external sources follow their respective licenses.

---

**Need Help?** Check the application logs for effect processing status or create an issue on GitHub.
