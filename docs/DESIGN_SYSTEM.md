# ClipForge Design System

## Colors

### Backgrounds
| Token | Dark | Light |
|-------|------|-------|
| `--bg-primary` | `#0B0B12` | `#FFFFFF` |
| `--bg-surface` | `#14141F` | `#F5F5F7` |
| `--bg-elevated` | `#1E1E2E` | `#FFFFFF` |
| `--bg-input` | `#1A1A28` | `#EAEAEA` |

### Text
| Token | Dark | Light |
|-------|------|-------|
| `--text-primary` | `#F0F0F5` | `#1A1A2E` |
| `--text-secondary` | `#9090A8` | `#6B6B80` |
| `--text-tertiary` | `#606078` | `#9090A0` |
| `--text-inverse` | `#0B0B12` | `#FFFFFF` |

### Accent
| Token | Value |
|-------|-------|
| `--accent-start` | `#FF3D81` (hot pink) |
| `--accent-end` | `#FF9F43` (orange) |
| `--accent-gradient` | `linear-gradient(135deg, #FF3D81, #FF9F43)` |
| `--accent-ring` | `rgba(255, 61, 129, 0.4)` |

### Functional
| Token | Dark | Light |
|-------|------|-------|
| `--success` | `#34D399` | `#10B981` |
| `--warning` | `#FBBF24` | `#F59E0B` |
| `--error` | `#F87171` | `#EF4444` |
| `--info` | `#60A5FA` | `#3B82F6` |

### Borders & Dividers
| Token | Dark | Light |
|-------|------|-------|
| `--border` | `#2A2A3E` | `#E0E0E8` |
| `--border-strong` | `#3A3A52` | `#D0D0DA` |
| `--border-focus` | `#FF3D81` | `#FF3D81` |

## Type Scale (Inter for UI, Archivo Black for display)

| Token | Font | Size | Weight | Line Height |
|-------|------|------|--------|-------------|
| `display-xl` | Archivo Black | 40px / 2.5rem | 400 | 1.1 |
| `display-md` | Archivo Black | 28px / 1.75rem | 400 | 1.2 |
| `heading-lg` | Inter | 24px / 1.5rem | 700 | 1.3 |
| `heading-md` | Inter | 20px / 1.25rem | 600 | 1.35 |
| `heading-sm` | Inter | 16px / 1rem | 600 | 1.4 |
| `body-lg` | Inter | 16px / 1rem | 400 | 1.5 |
| `body-md` | Inter | 14px / 0.875rem | 400 | 1.5 |
| `body-sm` | Inter | 13px / 0.8125rem | 400 | 1.45 |
| `body-xs` | Inter | 12px / 0.75rem | 400 | 1.4 |
| `caption` | Inter | 11px / 0.6875rem | 500 | 1.3 |
| `label` | Inter | 12px / 0.75rem | 600 | 1.3 |

## Spacing (8px base)

| Token | Value |
|-------|-------|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-10` | 40px |
| `--space-12` | 48px |
| `--space-16` | 64px |

## Border Radius

| Token | Value |
|-------|-------|
| `--radius-sm` | 6px |
| `--radius-md` | 10px |
| `--radius-lg` | 16px |
| `--radius-xl` | 24px |
| `--radius-full` | 999px |

## Shadows

| Token | Value |
|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.4)` |
| `--shadow-lg` | `0 8px 32px rgba(0,0,0,0.5)` |
| `--shadow-glow` | `0 0 24px rgba(255,61,129,0.15)` |

## Motion

| Token | Value |
|-------|-------|
| `--transition-fast` | `150ms ease` |
| `--transition-md` | `250ms ease` |
| `--transition-slow` | `400ms ease` |
| `--transition-spring` | `300ms cubic-bezier(0.34, 1.56, 0.64, 1)` |

Reduced motion: `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0ms !important; animation: none !important; } }`

## Typography (Caption Fonts - all open license)

| Font | Google Fonts | Use |
|------|-------------|-----|
| Archivo Black | Archivo Black:900 | Display headlines, caption style |
| Inter | Inter:400;500;600;700 | UI, body text |
| Anton | Anton:400 | Caption style "Heavy Impact" |
| Bebas Neue | Bebas Neue:400 | Caption style "Pop Bold" |
| Bangers | Bangers:400 | Caption style "Comic Burst" |
| Poppins | Poppins:800 | Caption style "Slim Tall" |

## Layout

- Max content width: 760px (centered)
- App bar height: 56px (sticky top)
- Card padding: 24px (desktop), 16px (mobile)
- Grid gap: 16px
- 44px minimum touch targets
- Fully responsive down to 360px

## Accessibility

- WCAG AA contrast minimum (4.5:1 for body text)
- Visible focus rings: 2px solid `--accent-start` with 2px offset
- Full keyboard navigation (Tab, Enter, Escape)
- ARIA labels on all interactive elements
- `prefers-reduced-motion` respected
