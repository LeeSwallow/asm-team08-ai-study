# Character ImageGen Prompts

Use these prompts to replace the current placeholder/ugly character assets with coherent noir comic detective-game portraits. Target style: polished 2D comic/anime visual novel, Ace Attorney-inspired but original, Korean mansion murder mystery, readable expressions, clean line art, painterly cel shading, dramatic noir rim light, no text, no watermark.

## Shared negative prompt

ugly, deformed, low quality, blurry, extra fingers, bad anatomy, uncanny, photorealistic, generic corporate avatar, flat icon, placeholder SVG, watermark, text, logo, broken face, mismatched eyes, distorted mouth

## Han Seo-yeon / 한서연

High-quality character portrait asset for a noir detective visual novel game, Korean mansion murder mystery, coherent stylish 2D comic/anime illustration, Ace Attorney inspired but original. Character: Han Seo-yeon, late 20s Korean heiress niece, elegant but tense, sharp intelligent eyes, black wavy shoulder-length hair, pearl earrings, dark burgundy blouse under tailored cream jacket, subtle anxiety and hidden confidence, dramatic rim light, rain-soaked mansion study atmosphere, expressive readable face, clean line art, painterly cel shading, polished game asset, upper body portrait, neutral/wary expression, dark transparent-feeling background, no text, no watermark, beautiful professional character design.

Expression variants to generate: neutral, wary, defensive, angry, anxious, shocked, breakdown, confident_lying, sad, focused.

## Yoon Jae-ho / 윤재호

High-quality character portrait asset for a noir detective visual novel game, Korean mansion murder mystery, coherent stylish 2D comic/anime illustration, Ace Attorney inspired but original. Character: Yoon Jae-ho, Korean male butler in his late 50s, dignified and weary, silver-streaked neatly combed hair, narrow glasses, black butler suit with white gloves, composed posture but worried eyes, loyal yet suspicious, dramatic mansion study rim lighting, expressive readable face, clean line art, painterly cel shading, polished game asset, upper body portrait, wary/focused expression, dark transparent-feeling background, no text, no watermark, handsome mature design.

Expression variants to generate: neutral, wary, defensive, angry, anxious, shocked, breakdown, confident_lying, sad, focused.

## Park Min-gyu / 박민규

High-quality character portrait asset for a noir detective visual novel game, Korean mansion murder mystery, coherent stylish 2D comic/anime illustration, Ace Attorney inspired but original. Character: Park Min-gyu, Korean male physician in his early 40s, calm clinical demeanor, tidy dark hair, white doctor coat over charcoal vest and tie, holding a small medical notebook, intelligent eyes with concealed pressure, polished and slightly unsettling, dramatic cool rim light, rain-soaked mansion study atmosphere, expressive readable face, clean line art, painterly cel shading, polished game asset, upper body portrait, neutral/defensive expression, dark transparent-feeling background, no text, no watermark, attractive professional design.

Expression variants to generate: neutral, wary, defensive, angry, anxious, shocked, breakdown, confident_lying, sad, focused.

## Choi Yoon-a / 최윤아

High-quality character portrait asset for a noir detective visual novel game, Korean mansion murder mystery, coherent stylish 2D comic/anime illustration, Ace Attorney inspired but original. Character: Choi Yoon-a, Korean female executive secretary in early 30s, sleek short bob haircut, navy tailored suit, thin gold-rim glasses, holding a tablet and fountain pen, controlled professional smile with nervous tension underneath, observant and calculating, dramatic mansion study rim lighting, expressive readable face, clean line art, painterly cel shading, polished game asset, upper body portrait, focused/anxious expression, dark transparent-feeling background, no text, no watermark, elegant professional game character design.

Expression variants to generate: neutral, wary, defensive, angry, anxious, shocked, breakdown, confident_lying, sad, focused.

## Integration requirements

- Save generated images under `FE/public/assets/` with existing canonical names:
  - `char_hanseoyeon_{expression}.png`
  - `char_yoonjaeho_{expression}.png`
  - `char_parkmingyu_{expression}.png`
  - `char_choiyuna_{expression}.png`
- Keep `.svg` placeholders only as fallback if needed; runtime should prefer generated PNG/WebP imagegen assets.
- Preserve canonical expression enum: `neutral,wary,defensive,angry,anxious,shocked,breakdown,confident_lying,sad,focused`.
- Browser validation must show no broken image/404 and must clearly improve character attractiveness/readability/mood.
