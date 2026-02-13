from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Sex(Enum):
    MALE = "male"
    FEMALE = "female"


class AgeGroup(Enum):
    AGE_19_30 = "19-30"
    AGE_31_50 = "31-50"
    AGE_51_70 = "51-70"
    AGE_71_PLUS = "71+"


@dataclass(frozen=True, slots=True)
class MicroInfo:
    name: str
    unit: str
    usda_id: int
    tier: int


# ---------------------------------------------------------------------------
# Canonical nutrient keys -> display / lookup info
# ---------------------------------------------------------------------------

MICRO_INFO: dict[str, MicroInfo] = {
    "calcium_mg": MicroInfo(name="Calcium", unit="mg", usda_id=1087, tier=1),
    "iron_mg": MicroInfo(name="Iron", unit="mg", usda_id=1089, tier=1),
    "magnesium_mg": MicroInfo(name="Magnesium", unit="mg", usda_id=1090, tier=1),
    "phosphorus_mg": MicroInfo(name="Phosphorus", unit="mg", usda_id=1091, tier=1),
    "potassium_mg": MicroInfo(name="Potassium", unit="mg", usda_id=1092, tier=1),
    "zinc_mg": MicroInfo(name="Zinc", unit="mg", usda_id=1095, tier=1),
    "copper_mg": MicroInfo(name="Copper", unit="mg", usda_id=1098, tier=1),
    "manganese_mg": MicroInfo(name="Manganese", unit="mg", usda_id=1101, tier=1),
    "selenium_mcg": MicroInfo(name="Selenium", unit="mcg", usda_id=1103, tier=1),
    "vitamin_c_mg": MicroInfo(name="Vitamin C", unit="mg", usda_id=1162, tier=2),
    "thiamin_mg": MicroInfo(name="Thiamin", unit="mg", usda_id=1165, tier=2),
    "riboflavin_mg": MicroInfo(name="Riboflavin", unit="mg", usda_id=1166, tier=2),
    "niacin_mg": MicroInfo(name="Niacin", unit="mg", usda_id=1167, tier=2),
    "vitamin_b6_mg": MicroInfo(name="Vitamin B6", unit="mg", usda_id=1175, tier=2),
    "folate_mcg": MicroInfo(name="Folate", unit="mcg", usda_id=1177, tier=2),
    "vitamin_b12_mcg": MicroInfo(name="Vitamin B12", unit="mcg", usda_id=1178, tier=2),
    "vitamin_a_mcg": MicroInfo(name="Vitamin A", unit="mcg", usda_id=1106, tier=3),
    "vitamin_d_mcg": MicroInfo(name="Vitamin D", unit="mcg", usda_id=1114, tier=3),
    "vitamin_e_mg": MicroInfo(name="Vitamin E", unit="mg", usda_id=1109, tier=3),
    "vitamin_k_mcg": MicroInfo(name="Vitamin K", unit="mcg", usda_id=1185, tier=3),
}

# ---------------------------------------------------------------------------
# DRI targets (RDA / AI) from NIH/USDA  –  keyed by (Sex, AgeGroup)
# ---------------------------------------------------------------------------

_MALE_19_30: dict[str, float] = {
    "calcium_mg": 1000,
    "iron_mg": 8,
    "magnesium_mg": 400,
    "phosphorus_mg": 700,
    "potassium_mg": 3400,
    "zinc_mg": 11,
    "copper_mg": 0.9,
    "manganese_mg": 2.3,
    "selenium_mcg": 55,
    "vitamin_c_mg": 90,
    "thiamin_mg": 1.2,
    "riboflavin_mg": 1.3,
    "niacin_mg": 16,
    "vitamin_b6_mg": 1.3,
    "folate_mcg": 400,
    "vitamin_b12_mcg": 2.4,
    "vitamin_a_mcg": 900,
    "vitamin_d_mcg": 15,
    "vitamin_e_mg": 15,
    "vitamin_k_mcg": 120,
}

_MALE_31_50: dict[str, float] = {
    **_MALE_19_30,
    "magnesium_mg": 420,
}

_MALE_51_70: dict[str, float] = {
    **_MALE_31_50,
    "vitamin_b6_mg": 1.7,
    "vitamin_d_mcg": 15,
}

_MALE_71_PLUS: dict[str, float] = {
    **_MALE_51_70,
    "calcium_mg": 1200,
    "vitamin_d_mcg": 20,
}

_FEMALE_19_30: dict[str, float] = {
    "calcium_mg": 1000,
    "iron_mg": 18,
    "magnesium_mg": 310,
    "phosphorus_mg": 700,
    "potassium_mg": 2600,
    "zinc_mg": 8,
    "copper_mg": 0.9,
    "manganese_mg": 1.8,
    "selenium_mcg": 55,
    "vitamin_c_mg": 75,
    "thiamin_mg": 1.1,
    "riboflavin_mg": 1.1,
    "niacin_mg": 14,
    "vitamin_b6_mg": 1.3,
    "folate_mcg": 400,
    "vitamin_b12_mcg": 2.4,
    "vitamin_a_mcg": 700,
    "vitamin_d_mcg": 15,
    "vitamin_e_mg": 15,
    "vitamin_k_mcg": 90,
}

_FEMALE_31_50: dict[str, float] = {
    **_FEMALE_19_30,
    "magnesium_mg": 320,
}

_FEMALE_51_70: dict[str, float] = {
    **_FEMALE_31_50,
    "iron_mg": 8,
    "vitamin_b6_mg": 1.5,
}

_FEMALE_71_PLUS: dict[str, float] = {
    **_FEMALE_51_70,
    "calcium_mg": 1200,
    "vitamin_d_mcg": 20,
}

DRI_TARGETS: dict[tuple[Sex, AgeGroup], dict[str, float]] = {
    (Sex.MALE, AgeGroup.AGE_19_30): _MALE_19_30,
    (Sex.MALE, AgeGroup.AGE_31_50): _MALE_31_50,
    (Sex.MALE, AgeGroup.AGE_51_70): _MALE_51_70,
    (Sex.MALE, AgeGroup.AGE_71_PLUS): _MALE_71_PLUS,
    (Sex.FEMALE, AgeGroup.AGE_19_30): _FEMALE_19_30,
    (Sex.FEMALE, AgeGroup.AGE_31_50): _FEMALE_31_50,
    (Sex.FEMALE, AgeGroup.AGE_51_70): _FEMALE_51_70,
    (Sex.FEMALE, AgeGroup.AGE_71_PLUS): _FEMALE_71_PLUS,
}
