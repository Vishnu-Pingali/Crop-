# Design System Strategy: CropSense AI

## 1. Overview & Creative North Star
**The Creative North Star: "The Digital Greenhouse"**

This design system rejects the clinical, sterile aesthetic of traditional SaaS in favor of a "Digital Greenhouse" philosophy. It is a high-tech ecosystem that feels alive, breathing, and rooted in the earth. We move beyond the "template" look by blending the precision of AI with the organic fluidity of nature. 

To achieve this, the system utilizes **Intentional Asymmetry**. Instead of a rigid, centered grid, we use "weighted" layouts where heavy data visualizations are balanced by expansive white space or overlapping organic patterns. This is not just a dashboard; it is an editorial experience that guides the eye through a narrative of growth and data-driven insight.

---

## 2. Colors & Surface Philosophy
The palette is a dialogue between the subterranean (`primary`: #00342e) and the sky (`surface`: #f8faf8), punctuated by the warmth of the soil (`tertiary`: #521c00).

*   **The "No-Line" Rule:** We do not use 1px solid borders to define sections. Boundaries are created through "Tonal Shifts." A dashboard sidebar should be `surface-container-low`, resting against a `surface` main content area. Contrast is our divider, not ink.
*   **Surface Hierarchy & Nesting:** Treat the interface as a series of stacked, semi-transparent sheets.
    *   **Level 0 (Base):** `surface` (#f8faf8)
    *   **Level 1 (Sectioning):** `surface-container-low` (#f2f4f2)
    *   **Level 2 (Cards/Focus):** `surface-container-lowest` (#ffffff)
*   **The "Glass & Gradient" Rule:** For AI-driven insights or "Floating Labs," use Glassmorphism. Apply `surface_variant` at 40% opacity with a `24px` backdrop blur. 
*   **Signature Textures:** Main Action Buttons (CTAs) should never be flat. Use a subtle linear gradient transitioning from `primary` (#00342e) to `primary_container` (#004d44) at a 135-degree angle to provide a "living" depth.

---

## 3. Typography
We utilize a dual-typeface system to balance authority with utility.

*   **Display & Headlines (Manrope):** Chosen for its geometric purity and modern "tech" feel. Use `display-lg` for hero data points (e.g., Yield Forecasts) to create an editorial, high-impact hierarchy.
*   **Body & Labels (Inter):** A workhorse for legibility. Inter is used for all functional data, ensuring that complex agricultural metrics remain readable at `body-sm` scales.
*   **Hierarchy Note:** Always pair a `headline-md` (Manrope) with a `label-md` (Inter, uppercase, tracking +5%) to create a sophisticated, "Pro-Tools" aesthetic.

---

## 4. Elevation & Depth
In this system, "Up" is defined by light and clarity, not by shadows.

*   **The Layering Principle:** Use the `surface-container` tiers to create a nested "Russian Doll" effect. A data chart (`surface-container-highest`) sits inside a module (`surface-container-low`), which sits on the page base (`surface`).
*   **Ambient Shadows:** Use only when an element is "detached" from the surface (e.g., a hovering AI recommendation). Shadows must be `on-surface` color at 6% opacity, with a blur radius of `40px` and a `Y` offset of `12px`. It should feel like a soft glow of light, not a dark smudge.
*   **The "Ghost Border" Fallback:** If a border is required for accessibility, use the `outline_variant` (#bfc9c4) at **15% opacity**. It should be felt, not seen.
*   **Neural Overlays:** Apply a subtle SVG pattern of neural nodes in `outline_variant` at 5% opacity in the background of `primary_container` sections to signify the AI "soul" of the platform.

---

## 5. Components

### Buttons & Interaction
*   **Primary Action:** Gradient-fill (`primary` to `primary_container`), `rounded-md` (1.5rem). On hover, increase the `surface_tint` glow.
*   **Secondary/Glass:** `surface_variant` at 20% opacity with backdrop blur. No border.
*   **Micro-animations:** Buttons should subtly scale (0.98) on click and shift gradient position on hover to mimic "organic" feedback.

### Intelligent Cards
*   **The Rule:** Forbid divider lines.
*   **Structure:** Use `spacing-6` (2rem) as the standard internal padding. Separate the header from the content using a `surface-container-high` background shift for the header area only.
*   **Corner Radius:** All cards must use `rounded-lg` (2rem) to maintain the "2xl" futuristic feel.

### Agricultural Input Fields
*   **States:** Default state uses `surface-container-highest`. On focus, the field transitions to `surface-container-lowest` with a `primary_fixed` (2px) "Ghost Border."
*   **Feedback:** Error states use `error` (#ba1a1a) but replace the background with a 5% tint of `error_container` to maintain the soft aesthetic.

### Data Visualization (The "Pulse")
*   **Glow Accents:** Use `primary_fixed` (#8df5e4) for active data lines. Apply a `drop-shadow` with the same color at 30% opacity to create a "glowing wire" effect against deep green backgrounds.

---

## 6. Do’s and Don’ts

### Do
*   **Do** use expansive white space (`spacing-16` or `20`) to separate major modules.
*   **Do** overlap elements (e.g., a glass card overlapping a photo of a crop field) to create depth.
*   **Do** use `tertiary` (Sienna/Clay) sparingly for "Warning" or "Soil Health" metrics to provide an earthy anchor to the greens.

### Don’t
*   **Don’t** use black (#000000) for text. Always use `on_surface` (#191c1b) for a softer, premium feel.
*   **Don’t** use sharp corners. The minimum radius for any functional element is `rounded-sm` (0.5rem); most should be `rounded-md` (1.5rem) or higher.
*   **Don’t** use standard "Select" dropdowns. Design custom, full-screen or "Glass" overlays that feel integrated into the environment.