# Grocery List Export Enhancements

## Goal

Improve the grocery list modal with weight equivalents and multiple export formats.

## 1. Weight Equivalents in Modal Display

Extend the parenthetical on each item to show both metric and imperial:

- Portion-based items: `2.5 cups (610g / 1.3 lb)`
- Weight-only items (no portion): `1.3 lb (610g)`

The `formatGrams` helper already handles g-to-lb conversion. Extend it to always show both units.

## 2. Export Dropdown Menu

Replace the single "Copy" button with a dropdown menu offering four options.

### Copy for Reminders

One item per line, flat, no categories. Designed to paste directly into Apple Reminders or any checklist app.

```
Chicken breast - 1.5 lb (680g)
Brown rice - 2 cups (370g / 0.8 lb)
Whole milk - 3.5 cups (854g / 1.9 lb)
```

### Copy Formatted

Current behavior. Category grouping, indentation, header with day count.

```
Grocery List (7 days)

Poultry Products
  Chicken breast - 4 breasts (696g / 1.5 lb)

Dairy and Egg Products
  Whole milk - 3.5 cups (854g / 1.9 lb)
```

### Download Markdown

`.md` file with category headers and checkbox items:

```markdown
# Grocery List (7 days)

## Dairy and Egg Products
- [ ] Whole milk - 3.5 cups (854g / 1.9 lb)
- [ ] Cheddar cheese - 4 oz (113g / 0.2 lb)

## Vegetables
- [ ] Broccoli - 2 cups (182g / 0.4 lb)
```

Triggered as a blob URL download with `.md` extension.

### Download PDF

Grouped by category, simple clean styling matching the modal layout. Title header with day count. Generated client-side using jsPDF.

## 3. Implementation

### Dependencies

- `jspdf` for PDF generation (install via bun)

### Changes

- **GroceryListModal.svelte**: Replace copy button with dropdown menu. Add export functions for each format. Update item display to show both g and lb.
- **Weight formatting**: Update `formatQty` and `formatGrams` to return both metric and imperial strings.
- **Dropdown component**: Simple click-to-toggle menu, dismiss on outside click or Escape. No need for a separate component, just local state in the modal.
