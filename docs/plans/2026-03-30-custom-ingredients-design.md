# Custom Ingredients Design

## Goal

Allow users to add custom ingredients (foods not in the USDA database) with manually entered nutritional data. Stored in localStorage with import/export for portability.

## Data Model

Custom ingredients reuse the existing `Food` interface with these conventions:

- **`fdc_id`**: Negative integers (-1, -2, ...), auto-assigned on creation. Avoids collision with real USDA IDs.
- **`category`**: `"Custom"` for identification and UI badging.
- **`commonness`**: `5` so custom foods sort to the top in search results.
- **`group`**: Set to the ingredient name (no variant grouping).
- **`micros`**: Only keys the user provides. Missing micros treated as 0, so custom foods won't contribute to gap-fill scores for unlisted nutrients.
- **`portion`**: Optional, same structure as USDA foods (`{ unit: string, g: number }`).

## Storage

- **localStorage** key: `"custom-foods"`, stored as a JSON array of `Food` objects.
- Loaded at app startup and merged into the main `foods` record alongside USDA data.

## Import/Export

- **Export**: Downloads `custom-ingredients.json` containing the raw array.
- **Import**: File picker for `.json`. Validates shape. Name collisions prompt overwrite-or-skip. Imported ingredients get fresh negative `fdc_id` values to avoid collisions.

## UI: Creating a Custom Ingredient

A **"Create Custom Ingredient"** button at the top of the Add Ingredient modal (visible in both browse and search states).

Clicking it replaces the modal content with a form.

### Required fields

- Name (text)
- Calories (kcal per 100g)
- Protein (g per 100g)
- Fat (g per 100g)
- Carbs (g per 100g)
- Fiber (g per 100g)

### Optional fields

- Subtitle (text, e.g., "chocolate flavor")
- Portion size (unit name + grams, e.g., "scoop" = 35g)
- Micronutrients: collapsed section, shows all 20 micros as labeled inputs, all blank by default. Only non-empty values are saved.

All nutrition values are entered per 100g, matching the internal data model.

### Actions

- **Save**: Validates required fields (filled + numeric), assigns negative `fdc_id`, saves to localStorage, adds to in-memory foods record, returns to search view.
- **Cancel**: Returns to search view, discards input.

## UI: Management View

Inside the Add Ingredient modal, a **"My Ingredients"** link near the search bar switches the modal to a list of all custom ingredients.

### List view

- Name + subtitle
- Macros summary (kcal / protein / fat / carbs per 100g)
- Edit and Delete buttons per row

### Edit

Opens the same form as creation, pre-filled. Save overwrites in localStorage and updates the in-memory record. If the ingredient is in the current meal, solver inputs update on next solve.

### Delete

Prompts confirmation, then removes from localStorage and memory. If the ingredient is in the current meal, removes it from the ingredient list.

### Import/Export

Buttons at the bottom of the management view:
- **Export**: Downloads `custom-ingredients.json`
- **Import**: File picker, validates shape, prompts on name collisions, assigns fresh negative IDs

## Integration with Existing Systems

- **Search**: Custom ingredients appear in normal search results alongside USDA foods, with a "Custom" badge.
- **Solver**: No changes needed. Custom foods use the same `Food` interface, so the solver treats them identically.
- **Gap-fill scoring**: Works for any micros the user entered. Unlisted micros contribute 0.
- **IngredientRow**: No changes needed. Displays custom foods identically to USDA foods.
- **Pinned meals**: Compatible, since pinned meals store solved nutrient totals, not food references.
