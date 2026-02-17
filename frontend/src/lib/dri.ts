// DRI reference data ported from src/daily_chow/dri.py
// Source: NIH/USDA Dietary Reference Intakes

export type NutrientTable = Record<string, number>;

export const MICRO_KEYS: string[] = [
    'calcium_mg',
    'iron_mg',
    'magnesium_mg',
    'phosphorus_mg',
    'potassium_mg',
    'zinc_mg',
    'copper_mg',
    'manganese_mg',
    'selenium_mcg',
    'vitamin_c_mg',
    'thiamin_mg',
    'riboflavin_mg',
    'niacin_mg',
    'vitamin_b6_mg',
    'folate_mcg',
    'vitamin_b12_mcg',
    'vitamin_a_mcg',
    'vitamin_d_mcg',
    'vitamin_e_mg',
    'vitamin_k_mcg',
];

// ---------------------------------------------------------------------------
// DRI targets (RDA / AI)
// ---------------------------------------------------------------------------

const MALE_19_30: NutrientTable = {
    calcium_mg: 1000,
    iron_mg: 8,
    magnesium_mg: 400,
    phosphorus_mg: 700,
    potassium_mg: 3400,
    zinc_mg: 11,
    copper_mg: 0.9,
    manganese_mg: 2.3,
    selenium_mcg: 55,
    vitamin_c_mg: 90,
    thiamin_mg: 1.2,
    riboflavin_mg: 1.3,
    niacin_mg: 16,
    vitamin_b6_mg: 1.3,
    folate_mcg: 400,
    vitamin_b12_mcg: 2.4,
    vitamin_a_mcg: 900,
    vitamin_d_mcg: 15,
    vitamin_e_mg: 15,
    vitamin_k_mcg: 120,
};

const MALE_31_50: NutrientTable = {
    ...MALE_19_30,
    magnesium_mg: 420,
};

const MALE_51_70: NutrientTable = {
    ...MALE_31_50,
    vitamin_b6_mg: 1.7,
    vitamin_d_mcg: 15,
};

const MALE_71_PLUS: NutrientTable = {
    ...MALE_51_70,
    calcium_mg: 1200,
    vitamin_d_mcg: 20,
};

const FEMALE_19_30: NutrientTable = {
    calcium_mg: 1000,
    iron_mg: 18,
    magnesium_mg: 310,
    phosphorus_mg: 700,
    potassium_mg: 2600,
    zinc_mg: 8,
    copper_mg: 0.9,
    manganese_mg: 1.8,
    selenium_mcg: 55,
    vitamin_c_mg: 75,
    thiamin_mg: 1.1,
    riboflavin_mg: 1.1,
    niacin_mg: 14,
    vitamin_b6_mg: 1.3,
    folate_mcg: 400,
    vitamin_b12_mcg: 2.4,
    vitamin_a_mcg: 700,
    vitamin_d_mcg: 15,
    vitamin_e_mg: 15,
    vitamin_k_mcg: 90,
};

const FEMALE_31_50: NutrientTable = {
    ...FEMALE_19_30,
    magnesium_mg: 320,
};

const FEMALE_51_70: NutrientTable = {
    ...FEMALE_31_50,
    iron_mg: 8,
    vitamin_b6_mg: 1.5,
};

const FEMALE_71_PLUS: NutrientTable = {
    ...FEMALE_51_70,
    calcium_mg: 1200,
    vitamin_d_mcg: 20,
};

export const DRI_TARGETS: Record<string, Record<string, NutrientTable>> = {
    male: {
        '19-30': MALE_19_30,
        '31-50': MALE_31_50,
        '51-70': MALE_51_70,
        '71+': MALE_71_PLUS,
    },
    female: {
        '19-30': FEMALE_19_30,
        '31-50': FEMALE_31_50,
        '51-70': FEMALE_51_70,
        '71+': FEMALE_71_PLUS,
    },
};

// ---------------------------------------------------------------------------
// EAR (Estimated Average Requirement)
// Nutrients without an EAR (AI-only: potassium, manganese, vitamin K) omitted.
// ---------------------------------------------------------------------------

const EAR_MALE_19_30: NutrientTable = {
    calcium_mg: 800,
    iron_mg: 6,
    magnesium_mg: 350,
    phosphorus_mg: 580,
    zinc_mg: 9.4,
    copper_mg: 0.7,
    selenium_mcg: 45,
    vitamin_c_mg: 75,
    thiamin_mg: 1.0,
    riboflavin_mg: 1.1,
    niacin_mg: 12,
    vitamin_b6_mg: 1.1,
    folate_mcg: 320,
    vitamin_b12_mcg: 2.0,
    vitamin_a_mcg: 625,
    vitamin_d_mcg: 10,
    vitamin_e_mg: 12,
};

const EAR_FEMALE_19_30: NutrientTable = {
    ...EAR_MALE_19_30,
    iron_mg: 8.1,
    magnesium_mg: 265,
    zinc_mg: 6.8,
    vitamin_c_mg: 60,
    thiamin_mg: 0.9,
    riboflavin_mg: 0.9,
    niacin_mg: 11,
    vitamin_a_mcg: 500,
};

export const DRI_EAR: Record<string, Record<string, NutrientTable>> = {
    male: {
        '19-30': EAR_MALE_19_30,
    },
    female: {
        '19-30': EAR_FEMALE_19_30,
    },
};

// ---------------------------------------------------------------------------
// UL (Tolerable Upper Intake Level)
// Nutrients without a UL (potassium, thiamin, riboflavin, B12, vitamin K) omitted.
// Same values for M/F 19-30, 31-50, 51-70.
// ---------------------------------------------------------------------------

const UL_19_70: NutrientTable = {
    calcium_mg: 2500,
    iron_mg: 45,
    // Note: magnesium UL (350mg) applies only to supplemental/pharmacological
    // sources, not dietary intake from food. Omitted here.
    phosphorus_mg: 4000,
    zinc_mg: 40,
    copper_mg: 10,
    manganese_mg: 11,
    selenium_mcg: 400,
    vitamin_c_mg: 2000,
    niacin_mg: 35,
    vitamin_b6_mg: 100,
    folate_mcg: 1000,
    vitamin_a_mcg: 3000,
    vitamin_d_mcg: 100,
    vitamin_e_mg: 1000,
};

export const DRI_UL: Record<string, Record<string, NutrientTable>> = {
    male: {
        '19-30': UL_19_70,
        '31-50': UL_19_70,
        '51-70': UL_19_70,
    },
    female: {
        '19-30': UL_19_70,
        '31-50': UL_19_70,
        '51-70': UL_19_70,
    },
};
