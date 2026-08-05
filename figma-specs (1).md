# DEX Dashboard Design Specification

**Figma File:** gm4vgVSMsPPbFZEjRGEluX  
**Master Library Node:** 1-19 (Library page)  
**Dashboard Layout Node:** 50-214974 (Layouts section, Basic DEX page)  
**Document Generated:** 2026-08-03

---

## 1. Design Tokens & Master Library

### 1.1 Color Palette

The design system uses CSS custom properties (CSS variables) for all color tokens. Light and dark theme variants are supported.

| Token | Light Mode | Dark Mode | Usage |
|-------|-----------|-----------|-------|
| `--colours/primary-btn-bg` | #222 | TBD | Primary button background |
| `--colours/primary-btn-text` | #eceae3 | TBD | Primary button text color |
| `--colours/surface-bg` | #eceae3 | TBD | Main surface/panel background |
| `--colours/border-stroke` | #b3b2ad | TBD | Border and stroke color |
| `--colours/primary-text` | #171716 | TBD | Primary text (headings, body) |
| `--colours/labels` | #767676 | TBD | Label text (captions, metadata) |

**Color System Notes:**
- All colors reference CSS variables with fallback values
- Light palette uses warm grays and high contrast
- Supporting up to light and dark theme variants
- Border stroke applied consistently across panels and dividers

---

### 1.2 Typography System

The design exclusively uses **JetBrains Mono** font family across all text layers.

| Text Role | Font Family | Size | Weight | Weight Numeric | Line Height | Letter Spacing | Usage |
|-----------|-----------|------|---------|----------------|-------------|-----------------|-------|
| **Display Large** | JetBrains Mono | 48px | - | 700 | 1.2 | 0 | Not actively used in current layouts |
| **Display** | JetBrains Mono | 40px | - | 700 | 1.2 | 0 | Not actively used in current layouts |
| **H2** | JetBrains Mono | 31px | - | 700 | 1.2 | 0 | Not actively used in current layouts |
| **Body / P** | JetBrains Mono | 16px | Medium | 500 | 1.2 | 0 | Primary body text, asset labels (Market Stats) |
| **Caption** | JetBrains Mono | 14px | SemiBold | 600 | 1.2 | 0 | Data values, table cells, secondary content |
| **Overline / Label** | JetBrains Mono | 12px | ExtraBold | 800 | 1.2 | 0.12px (1px/8.33) | Column headers, metadata labels, uppercase badges |

**Typography Application:**
- All body text rendered via `font-['JetBrains_Mono:Medium']`
- Numeric data (price, change values) use Caption weight (14px SemiBold)
- Labels and section headers use Overline weight (12px ExtraBold) with 0.12px letter-spacing
- Consistent 1.2 line-height ratio across all scales
- Monospace rendering ensures alignment for financial data

---

### 1.3 Measurement & Spacing System

| Token | Value | Usage |
|-------|-------|-------|
| `--measurements/0` | 0px | Padding/margin resets |
| `--measurements/1` | 4px | Minimal gaps, icon-to-text spacing |
| `--measurements/2` | 8px | Standard padding (interior panels) |
| `--measurements/4` | 16px | Button padding (horizontal) |
| `--measurements/5` | 20px | Medium gaps (between columns) |
| `--measurements/6` | 24px | Large gaps (between major sections) |
| `--measurements/11` | 44px | Button height standard |

**Container Sizing:**
- Market Stats bar: 44px height
- Chart section: 500px height (candle charts)
- Orderbook panel: 546px height
- Order Form panel: 978px height (full height variant)
- Tables/Spot-Perps: 430px height

---

### 1.4 Component Library Inventory

#### 1.4.1 **Icon Component**
- **Location:** Section "Icons by Phosophor Icons" (Figma node 19:102181)
- **Source:** Phosphor Icons (MIT Licensed)
- **Sizes Available:** xs (10px), sm (16px), md (24px), lg (32px), xl (40px)
- **Icon Set Used:** Topic-based naming (CaretDown, CaretUp, ArrowDown, ArrowUp, X, MagnifyingGlass, FunnelSimple, ArrowsDownUp, ChartLine, Calendar, ShareNetwork, NotePencil, ArrowRight, ArrowLeft, Trash, DotsThreeVertical)
- **Implementation:** SVG vectors, rendered as `<img>` with absolute positioning
- **Color:** Inherits from `--colours/labels` for standard icons
- **States:** Default (always present), no interactive states on icons themselves

#### 1.4.2 **Button Component**
- **Figma Node:** 9:7163 (Buttons frame)
- **Variants:**
  - **Type:** Primary, Secondary, Tertiary
  - **States:** Default, Hover, Focus, Disabled
- **Primary Button (Default State):**
  - Background: `--colours/primary-btn-bg` (#222)
  - Text: `--colours/primary-btn-text` (#eceae3)
  - Height: 44px (`--measurements/11`)
  - Padding: 20px horizontal, 0px vertical
  - Border-radius: 4px
  - Font: JetBrains Mono, Medium, 16px
  - Gap: 4px (between icon and label)
- **Secondary Button (Default State):**
  - Background: Lighter/outlined variant
  - Text: Dark text
  - Same height and padding structure
- **Tertiary Button:**
  - Ghost/text-only variant
  - No background fill
- **All Buttons:**
  - Support optional `lead` icon (left)
  - Support optional `trail` icon (right)
  - Support optional label text
  - Border-radius: 4px
  - Overflow: hidden

#### 1.4.3 **Label / Badge Component**
- **Figma Node:** 1:405 (Label)
- **Sizing:** 16px high (variable width)
- **Text:** JetBrains Mono ExtraBold, 12px, letter-spacing 0.12px, uppercase
- **Color:** `--colours/labels` (#767676)
- **Options:**
  - `lead`: Boolean to show optional leading icon
  - `trail`: Boolean to show optional trailing icon (default: true)
  - `underline`: Boolean to show bottom border indicator (default: true)
- **Gap between elements:** 4px
- **Use:** Column headers, data labels, metadata tags

#### 1.4.4 **Token / Asset Icon**
- **Figma Node:** 1:451 (Colour frame in Tokens section)
- **Supported Coins:** BTC, ETH, SOL, USDC, USDT, BONK, SRM, stSOL, scnSOL, mSOL, jup.ag, PSY
- **Size Variants:** 10px, 16px, 24px, 64px
- **Implementation:** Circular/branded coin badges with logo overlay
- **Usage:** Market pair indicators, asset selection

#### 1.4.5 **Tab Components**
- **Underline Tab (Figma Node:** 3:7245)
  - Frame: 210px × 80px
  - States: Active=Yes, Active=No
  - Height: 48px per tab
  - Bottom border indicates active state
  - Spacing: Fitted to content
- **Segment Tab (Figma Node:** 5:18461)
  - Frame: 210px × 80px
  - States: Active=Yes, Active=No
  - Height: 44px per tab
  - Background pill-style indicator
  - Spacing: Fitted to content
- **Multi-tab layouts:** 2-6 tabs supported (Figma nodes 3:7333 through 3:7329)

#### 1.4.6 **Chart Components**
- **Candle Chart (Figma Node:** 1:3959)
  - Frame: 684px × 500px
  - Styles: Monochrome or Color variants
  - Body: Fill or outline style
  - Tail: 2px line connector
- **Chart containers:** Used in Market Stats and main trading area

#### 1.4.7 **Table Components**
- **Cell Types:**
  - **Header:** Line=single, Type=header | 80px × 32px
  - **Standard:** Line=single, Type=standard | 58px × 56px
  - **Icon Cell:** Line=single, Type=icon | 40px × 56px
  - **Tag Cell:** Line=single, Type=tag | 54px × 56px
  - **Action Cell:** Line=single, Type=action | 60px × 56px
  - **Asset Cell:** Line=single, Type=asset | 86px × 56px
  - **Double-line cells:** Variant for denser content
- **Column Layouts:** Std, Tag, Icon, Action, Asset types (Figma node 2:6468)
- **Tables / Spot-Perps (Figma Node:** 3:9265)
  - Supported views: Positions, Orders, Trade History, Account Status
  - Height: 430px (standard), 1920px (full view frame)
  - Width: 1061-1093px (responsive)

#### 1.4.8 **Orderbook Component**
- **Standard Orderbook (Figma Node:** 5:16839)
  - Frame: 838px × 578px
  - Views: Orderbook, Recent Trades
  - Panel width: 375px per view
  - Height: 546px
- **Orderbook XL (Figma Node:** 24:113926)
  - Frame: 838px × 1103px
  - Views: Orderbook-Recent_xl, Recent Trades
  - Panel width: 375px
  - Height: 1071px (full-height variant)

#### 1.4.9 **Order Form / Spot-Perps**
- **Figma Node:** 9:9045
- **Variants:**
  - Order Type=Market (Market order form)
  - Order Type=Limit (Limit order form)
- **Dimensions:** 750px frame, 331px panel width (deployed), 978px or 932px height
- **Controls included:**
  - Order Type Dropdown (Figma node 25:121068): 197px × 88px
  - Advanced Accordion (Figma node 9:6346): 750px × 228px
  - Time-in-Force selector (Figma node 9:6240): 273px × 256px
  - Checkbox controls (Figma node 9:6390): 92px × 56px
  - Slider components (Figma node 13:10564): 228px × 4px
  - Slider knob (Figma node 13:10561): 46px × 22px

#### 1.4.10 **Market Stats Bar**
- **Figma Node:** 1:629 (Master symbol), 1:657 (instance)
- **Dimensions:** 760px × 44px (standard), 1093px (responsive)
- **Layout:** Flex row with gap 24px
- **Sections:**
  1. **Market Dropdown:** 283-323px min-width, max-width 323px
     - Coin pair icons (overlapped 8px)
     - Asset label (e.g., "SOL-USDC")
     - "Change Market" label with trailing icon
     - Border right separator
  2. **Market Data Columns:** 3 columns × 64px width each
     - Column 1: 24H Change
     - Column 2: 24H High
     - Column 3: 24H Low
     - Each with Overline label + Caption value
- **Background:** `--colours/surface-bg`
- **Border:** `--colours/border-stroke`
- **Padding:** 8px horizontal, 0px vertical
- **Height:** 44px (fixed)

---

### 1.5 Component State Specifications

#### Button States
1. **Default:** Filled background, text visible, no decoration
2. **Hover:** Darker background, slight elevation or opacity change
3. **Focus:** Border glow or outline (keyboard navigation)
4. **Disabled:** Opacity reduction, grayed text, no click interaction

#### Tab States
1. **Active:** Bottom border or background pill highlighted
2. **Inactive:** Subtle text color, no indicator
3. **Hover (inactive):** Slightly darker background or border

#### Table Cell States
1. **Header:** Bold text, background fill, border bottom
2. **Standard:** Regular weight, white/light background, subtle border
3. **Icon:** Center-aligned icon, border
4. **Action:** Hover state shows interactive controls

---

## 2. Main Dashboard Specs & Layout

### 2.1 Dashboard Breakpoints & Variants

The dashboard system supports multiple viewport widths with responsive layouts:

| Breakpoint | Width | Variants | Pages | Notes |
|------------|-------|----------|-------|-------|
| Mobile | 1280px | Light, Dark | LIGHT, DARK | 5:15178, 9:9174, 50:194695, 50:209390 |
| Desktop | 1440px | Light, Dark | LIGHT, DARK | 1:640, 2:6503, 50:194679, 50:209382 |
| UltraWide | 1728px | Light, Dark | LIGHT, DARK | 18:14419, 18:14420, 50:194712, 50:209399 |

All variants follow the same component hierarchy and styling tokens.

---

### 2.2 Dashboard Structural Layout

The DEX Dashboard uses a **multi-column trading grid** layout:

```
┌─────────────────────────────────────────────────────┐
│ NAVIGATION BAR (44px height)                         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────────┬──────────┐                │
│  │  Market Stats        │ Orderbook│                │
│  │  (760×44)            │(345×546) │    ┌─────────┐│
│  ├──────────────────────┤          │    │ Order   ││
│  │  Chart               │          │    │ Form    ││
│  │  (Candle)            │          │    │(331×978)││
│  │  (760×500)           │          │    │         ││
│  ├──────────────────────┴──────────┘    └─────────┘│
│  │  Tables / Spot-Perps (1107×430)                 │
│  │  - Positions                                     │
│  │  - Orders                                        │
│  │  - Trade History                                 │
│  │  - Account Status                                │
│  └──────────────────────────────────────────────────┘
│
│ TOTAL: 1440px wide × 1024px tall (1440px variant)
```

**Layout Type:** CSS Flexbox with multiple nesting levels  
**Main Container:** Full viewport fill  
**Direction:** Row-based for sidebar arrangement, column-based for stacked sections

---

### 2.3 Spacing & Alignment Specifications

#### Navigation Bar
- **Height:** 44px (fixed)
- **Content:** Centered "NAVIGATION" label
- **Width:** Full viewport width
- **Background:** White/light surface (inherited from parent)
- **Border:** None

#### Market Stats Section
- **Position:** Top-left after navigation
- **Dimensions:** 760px × 44px (responsive to 1093px width)
- **Margin from top:** 46px (gap from nav)
- **Flex properties:** flex: 1 0 0 (flex grow enabled)
- **Gap between children:** 24px (`--measurements/6`)
- **Padding:** 8px horizontal (left/right)
- **Border:** Right border separator to Orderbook

#### Chart Section (Candle)
- **Position:** Below Market Stats
- **Dimensions:** 760px × 500px
- **Margin from Market Stats:** 46px (gap from nav)
- **Container:** Flex column
- **Content alignment:** Stretch to fill available width

#### Orderbook Section
- **Position:** Right of Chart (same row start as Market Stats)
- **Dimensions:** 345px × 546px
- **Margin from top:** 46px
- **Layout:** Flex column with tab switching
- **Scroll:** Internal scrollable area for orderbook rows

#### Order Form Section
- **Position:** Far right, full height
- **Dimensions:** 331px × 978px (responsive 932px or 740px)
- **Margin from top:** 46px
- **Layout:** Flex column
- **Scroll:** Internal scrollable form controls
- **Sticky behavior:** Form remains visible while user scrolls through sections

#### Tables Section (Spot-Perps)
- **Position:** Below Chart and Orderbook (full width)
- **Dimensions:** 1107px × 430px (responsive 1061-1093px)
- **Margin from Chart:** 52px (gap)
- **Layout:** Flex column with tab switching (Positions/Orders/History/Status)
- **Scroll:** Horizontal table scroll for data rows

---

### 2.4 Component Mapping & Instantiation

#### Dashboard Instance Tree (1440px Light Variant - Node 1:640)

```
Frame: SPOT / PERPS [LIGHT] - 1440 (1440×1024)
├── Frame: NAVIGATION (1440×44)
│   └── Text: "NAVIGATION" (centered)
├── Instance: Market Stats (760×44)
│   ├── Market Dropdown (283-323px)
│   │   ├── Asset Icons (coin overlays)
│   │   ├── Asset Label ("SOL-USDC")
│   │   └── Label: "CHANGE MARKET" with trailing icon
│   └── Market Data Columns (3× data columns)
│       ├── Column 1: "24H CHANGE" + "Value 1"
│       ├── Column 2: "24H HIGH" + "Value 2"
│       └── Column 3: "24H LOW" + "Value 3"
├── Instance: Chart Styles/Candle (760×500)
│   └── Candlestick chart rendering
├── Instance: Orderbook (345×546)
│   ├── Tab: "ORDERBOOK"
│   ├── Tab: "RECENT TRADES"
│   └── [Scrollable content area]
├── Instance: Order Form / Spot-Perps (331×978)
│   ├── Radio: Order Type (Market/Limit)
│   ├── Input fields
│   ├── Advanced Accordion
│   ├── Slider controls
│   ├── Checkbox controls
│   └── Submit Button (Primary)
└── Instance: Tables / Spot-Perps (1107×430)
    ├── Tab: "POSITIONS"
    ├── Tab: "ORDERS"
    ├── Tab: "TRADE HISTORY"
    ├── Tab: "ACCOUNT STATUS"
    └── [Scrollable table rows]
```

**Key CSS Properties Applied:**
- Order Form: `position: absolute` or `flex` with `flex-shrink: 0`
- Market Stats: `flex: 1 0 0` (grows to fill available width after fixed-width siblings)
- Chart & Table: Full responsive width, constrained by parent container
- All instances: `data-node-id` attribute for Figma traceability

---

### 2.5 Layout Variants & Responsive Behavior

#### 1280px Variant (Mobile/Tablet)
- Chart width reduced to 699px
- Orderbook width reduced to 286px
- Order Form repositioned: 989px × 46px (left side below nav, overlapping chart area)
- Tables width reduced to 987px
- Table height: 360px

**Layout shift:** Order Form moves left, other sections reflow

#### 1440px Variant (Standard Desktop)
- Chart: 760px
- Orderbook: 345px
- Order Form: 1109px × 46px (right side, full height)
- Tables: 1107px

**Layout:** All sections visible simultaneously, right-aligned order form

#### 1728px Variant (UltraWide)
- Chart: 1018px (expanded)
- Orderbook XL: 375px (larger orderbook variant)
- Order Form: 1397px × 46px (far right, full height)
- Tables: 1018px

**Layout:** Expanded orderbook, larger chart, all sections visible

---

### 2.6 Theme Support

The design supports **Light** and **Dark** themes with CSS variable overrides:

#### Light Theme (Active in Figma library)
- Surface background: #eceae3 (warm beige)
- Primary text: #171716 (near-black)
- Labels: #767676 (mid-gray)
- Border: #b3b2ad (light gray)
- Button background: #222 (dark gray)
- Button text: #eceae3 (light beige)

#### Dark Theme (Exported but values not fully specified)
- Surface background: [Dark variant TBD]
- Primary text: [Light variant TBD]
- Labels: [Light variant TBD]
- Border: [Dark variant TBD]
- Button background: [Light variant TBD]
- Button text: [Dark variant TBD]

**Implementation:** CSS variables with dark mode media query or class-based switching

```css
:root {
  --colours/surface-bg: #eceae3;
  --colours/primary-text: #171716;
  --colours/labels: #767676;
  --colours/border-stroke: #b3b2ad;
  --colours/primary-btn-bg: #222;
  --colours/primary-btn-text: #eceae3;
}

/* Dark mode variant */
@media (prefers-color-scheme: dark) {
  :root {
    /* Dark theme variable overrides */
  }
}
```

---

## 3. Implementation Notes

### 3.1 Assets & External Resources
- Icon assets: Phosphor Icons (MIT Licensed), MIT License included in source (Figma node 34:189838)
- Coin badges: Custom branded assets (12 coin types supported)
- Chart rendering: Candle chart SVG or canvas-based implementation required

### 3.2 Responsive Breakpoint Implementation
Use CSS media queries or JavaScript viewport detection to swap between layouts:

```css
/* 1280px (Mobile/Tablet) */
@media (max-width: 1440px) {
  /* 1280px layout adjustments */
}

/* 1440px (Desktop) */
@media (min-width: 1441px) and (max-width: 1728px) {
  /* 1440px layout adjustments */
}

/* 1728px (UltraWide) */
@media (min-width: 1729px) {
  /* 1728px layout adjustments */
}
```

### 3.3 CSS Variable Structure
All colors, measurements, and typography use CSS custom properties for maintainability:

```css
/* Color tokens */
--colours/[token]: [hex value];

/* Measurement tokens */
--measurements/[0-11]: [px value];

/* Typography tokens */
--font-family/mono: 'JetBrains Mono';
--font-size/[label]: [px];
--font-weight/[label]: [numeric];
--line-height/mono: 1.2;
```

### 3.4 Component Hierarchy
```
Dashboard Container
├── Navigation Bar (static)
├── Trading Grid (responsive flex layout)
│   ├── Left Column
│   │   ├── Market Stats
│   │   ├── Chart
│   │   └── Tables
│   ├── Center Column (Orderbook)
│   └── Right Column (Order Form)
```

### 3.5 Figma Symbol References
All Figma instances reference master symbols from the Library page (1-19). Symbol updates propagate automatically:

- `Market Stats` → Figma symbol 1:629
- `Chart Styles/Candle` → Figma symbol 1:3959
- `Orderbook` → Figma symbol 5:16838 / 5:16837
- `Order Form / Spot-Perps` → Figma symbol 9:7171 / 9:8973
- `Tables / Spot-Perps` → Figma symbol 3:9264 / 3:9263 / 3:9261 / 3:9262

---

## 4. Design System Summary Table

| Category | Key Details |
|----------|------------|
| **Font Family** | JetBrains Mono (all text) |
| **Typography Scales** | 12px, 14px, 16px (primary); 18px, 31px, 40px, 48px (unused display) |
| **Color Tokens** | 6 primary CSS variables (background, surface, border, text, labels, button states) |
| **Measurement System** | 12 spacing tokens (0px, 4px, 8px, 16px, 20px, 24px, etc.) |
| **Button Heights** | 44px standard (--measurements/11) |
| **Table Cell Height** | 56px standard (varies by type) |
| **Border Radius** | 4px (components), 32px (circular badges) |
| **Icon Library** | Phosphor Icons, 20+ icon types, 5 size variants |
| **Chart Types** | Candlestick (monochrome/color, fill/outline) |
| **Layout Type** | Flex-based responsive grid |
| **Breakpoints** | 1280px, 1440px, 1728px |
| **Theme Support** | Light (defined), Dark (structure ready) |

---

## 5. Exported Figma Screenshots

### Library Node (1-19) Overview
![Library screenshot showing typography scale, icons, components, tabs, charts, and DEX panels]

### Dashboard Node (50-214974) Layouts
![Dashboard showing multiple responsive variants: 1280px, 1440px, 1728px in both light and dark themes]

---

**End of Design Specification**

*This document serves as the authoritative ground truth for implementing the DEX Dashboard UI system. All spacing, typography, color, and component specifications derive directly from the Figma master library and dashboard layouts.*
