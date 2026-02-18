# Draggable Priority Cards (Mobile)

## Summary

Replace the small up/down arrow buttons for solve priorities with touch drag-and-drop cards on mobile (≤640px), using SortableJS. Desktop keeps the existing UI.

## Decisions

- **Library**: SortableJS (~12KB gzipped), mature touch support
- **Scope**: Mobile only (≤640px); desktop unchanged
- **Re-solve**: Immediate on drop (matches current behavior)

## Visual Design

Each priority renders as a card on mobile:
- Drag handle (grip icon) on the left
- Rank number (1-4) + descriptive label
- ~48px height for comfortable touch targets
- Rounded corners, subtle border, slight background elevation

## Interaction

- Drag handle initiates drag (prevents conflicts with page scrolling)
- During drag: card lifts with shadow, other cards animate to show drop position
- On drop: `priorities` array reorders, `triggerSolve()` fires immediately
- SortableJS `animation: 150` for smooth transitions

## Integration

- Install `sortablejs` + `@types/sortablejs` via bun
- Create `PriorityCards.svelte` component
- Use `onMount` to initialize `Sortable.create()` on the container
- `onEnd` callback reads new order, updates `priorities` state, calls `triggerSolve()`
- Clean up with `sortable.destroy()` on unmount
- In `+page.svelte`, conditionally render `PriorityCards` on mobile vs existing rows on desktop
