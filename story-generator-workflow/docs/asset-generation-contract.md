# Asset Generation Contract

에셋은 Editor 승인 후에만 생성한다.

## 1. Asset Types

### Backgrounds
- opening scene background
- interrogation room / central scene background
- key location backgrounds, only if UI needs them

### Suspect Portraits
각 용의자별 최소 4개:
- low: controlled / neutral mask
- medium: defensive / guarded
- high: rattled / angry / pressured
- critical: broken / exposed / collapsing

### Evidence Photos
각 증거별 하나의 thumbnail/photo style image:
- physical evidence: close-up noir photograph
- digital/record evidence: document/screen/card/log visual
- autopsy/medical: clinical but non-graphic prop image

## 2. Manifest Shape

```json
{
  "caseId": "case_...",
  "styleBible": {
    "genre": "Korean noir detective visual novel",
    "palette": ["deep navy", "warm amber", "desaturated burgundy"],
    "lighting": "cinematic noir rim light, rainy mansion atmosphere",
    "negativePrompt": "text, watermark, extra fingers, distorted face, childish cartoon, low quality"
  },
  "assets": [
    {
      "assetId": "vis_char_hanseoyeon_high",
      "type": "suspect_portrait",
      "characterId": "char_hanseoyeon",
      "pressure": "high",
      "prompt": "...",
      "outputPath": "assets/characters/char_hanseoyeon/high.png"
    }
  ]
}
```

## 3. Prompt Requirements

공통 포함:
- Detective Agent FE 목표: dark noir single-screen dashboard에 어울리는 고품질 PNG/WebP
- readable expression
- consistent identity across pressure variants
- no text / no watermark
- bust portrait for characters, object close-up for evidence

금지:
- placeholder SVG 수준 묘사
- ugly/low quality/generated artifact 허용
- pressure variant마다 인물이 달라 보이는 프롬프트
- hidden truth를 이미지 설명에 직접 노출하는 파일명/alt text/public metadata

## 4. Generation Timing

```text
Editor approved
  -> freeze suspect/evidence/background list
  -> create asset_manifest.json
  -> lint prompts and output paths
  -> generate images
  -> verify files exist and dimensions/format acceptable
  -> link asset IDs into case visualProfiles
```

## 5. Visual Profile Link

```json
{
  "characterId": "char_...",
  "states": {
    "low": { "assetId": "vis_..._low", "expression": "controlled" },
    "medium": { "assetId": "vis_..._medium", "expression": "defensive" },
    "high": { "assetId": "vis_..._high", "expression": "rattled" },
    "critical": { "assetId": "vis_..._critical", "expression": "broken" }
  }
}
```
