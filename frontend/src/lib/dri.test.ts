import { describe, expect, test } from 'vitest';
import { DRI_EAR, DRI_TARGETS, DRI_UL, MICRO_KEYS } from './dri';

describe('MICRO_KEYS', () => {
    test('has exactly 20 entries', () => {
        expect(MICRO_KEYS).toHaveLength(20);
    });
});

describe('DRI_TARGETS', () => {
    test('male 19-30 spot checks', () => {
        const t = DRI_TARGETS.male['19-30'];
        expect(t.calcium_mg).toBe(1000);
        expect(t.iron_mg).toBe(8);
        expect(t.vitamin_k_mcg).toBe(120);
    });

    test('female 19-30 spot checks', () => {
        const t = DRI_TARGETS.female['19-30'];
        expect(t.iron_mg).toBe(18);
        expect(t.potassium_mg).toBe(2600);
    });

    test('male 31-50 has magnesium override (420, not 400)', () => {
        expect(DRI_TARGETS.male['31-50'].magnesium_mg).toBe(420);
    });

    test('female 51-70 has iron override (8, not 18)', () => {
        expect(DRI_TARGETS.female['51-70'].iron_mg).toBe(8);
    });
});

describe('DRI_UL', () => {
    test('male 19-30 spot checks', () => {
        const ul = DRI_UL.male['19-30'];
        expect(ul.calcium_mg).toBe(2500);
        expect(ul.iron_mg).toBe(45);
    });
});

describe('DRI_EAR', () => {
    test('male 19-30 calcium', () => {
        expect(DRI_EAR.male['19-30'].calcium_mg).toBe(800);
    });

    test('female 19-30 has different values from male', () => {
        const f = DRI_EAR.female['19-30'];
        expect(f.iron_mg).toBe(8.1);
        expect(f.zinc_mg).toBe(6.8);
    });
});
