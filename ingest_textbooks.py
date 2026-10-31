"""
VidyaFlow - PDF Textbook Ingestion & Metadata Tagging Pipeline
Processes official PDF textbooks into smart semantic chunks and stores them
into local ChromaDB with strict curriculum metadata:
{"board": "TS" | "ICSE", "class": int (6-10), "subject": "string", "chapter": "string"}
"""

import argparse
import glob
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# Support running directly or as module
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from app.services.vector_store import ChromaVectorStore, normalize_board

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


# Canonical syllabus seed data covering all subjects across Classes 6 to 10 for TS and ICSE boards:
# - Mathematics
# - Physical Science (Physics / Chemistry)
# - Biological Science (Biology)
# - Social Studies
CANONICAL_SEEDS = [
    # =========================================================================
    # TELANGANA STATE BOARD (TS) - CLASSES 6 TO 10
    # =========================================================================

    # --- TS CLASS 6 ---
    {
        "board": "TS",
        "class_num": 6,
        "class": 6,
        "subject": "Mathematics",
        "chapter": "Knowing Our Numbers",
        "text": """Chapter 1: Knowing Our Numbers (Telangana SCERT Class 6 Mathematics).
1.1 Indian and International Systems of Numeration:
In the Indian System:
- Periods: Ones, Thousands, Lakhs, Crores.
- Commas: After first 3 digits from right, then after every 2 digits (e.g., 5,08,21,340).
- 1 Lakh = 100 Thousands; 1 Crore = 100 Lakhs = 10 Millions.
In the International System:
- Periods: Ones, Thousands, Millions, Billions.
- Commas: After every 3 digits from right (e.g., 50,821,340).
- 1 Million = 1,000,000.
1.5 Roman Numerals:
Seven basic symbols: I=1, V=5, X=10, L=50, C=100, D=500, M=1000.
Rules: Symbols I, X, C, M repeat at most 3 times. V, L, D never repeat or subtract.
Example: 99 = (100-10) + (10-1) = XCIX.
Estimation: Rounding off numbers to nearest tens, hundreds, and thousands using midpoint benchmark rule.""",
    },
    {
        "board": "TS",
        "class_num": 6,
        "class": 6,
        "subject": "Physical Science",
        "chapter": "Playing with Magnets",
        "text": """Chapter 2: Playing with Magnets (Telangana SCERT Class 6 Science).
A magnet is a material or object that produces a magnetic field that attracts ferromagnetic substances like iron, nickel, and cobalt.
Poles of a Magnet:
Every magnet has two magnetic poles where magnetic attractive strength is concentrated: North Pole (N) and South Pole (S).
Fundamental Laws of Magnetism:
1. Like magnetic poles repel each other (North repels North, South repels South).
2. Unlike magnetic poles attract each other (North attracts South).
3. A freely suspended bar magnet always aligns itself along the geographic North-South direction.
Applications:
- Magnetic compass: Contains a magnetized needle pivoted to rotate freely, used by navigators.
- Preservation: Bar magnets are stored in pairs with opposite poles alongside and soft iron keepers across their ends.""",
    },
    {
        "board": "TS",
        "class_num": 6,
        "class": 6,
        "subject": "Biological Science",
        "chapter": "Our Food and Its Components",
        "text": """Chapter 1: Our Food and Its Components (Telangana SCERT Class 6 Science).
Nutrients are chemical components of food essential for growth, metabolism, and health:
1. Carbohydrates: Major energy source (starch, sugars). Tested using diluted iodine solution (turns blue-black).
2. Proteins: Body-building and tissue repair nutrients (pulses, milk, eggs). Tested using copper sulphate and caustic soda solution (turns violet).
3. Fats: High-density energy reserves (groundnut, butter). Tested by translucent patch on paper.
4. Vitamins & Minerals: Protective nutrients preventing deficiency diseases:
   - Vitamin A: Night blindness.
   - Vitamin C: Scurvy (bleeding gums).
   - Vitamin D: Rickets (soft bones).
   - Iron: Anaemia (haemoglobin deficiency).
   - Iodine: Goitre (swollen neck gland).
Dietary fibres (roughage) assist digestive peristalsis, and water maintains cellular homeostasis.""",
    },
    {
        "board": "TS",
        "class_num": 6,
        "class": 6,
        "subject": "Social Studies",
        "chapter": "Globe - Model of the Earth",
        "text": """Chapter 1: Reading and Making Maps & Globe - Model of the Earth (TS SCERT Class 6 Social Studies).
A globe is a three-dimensional spherical scale model of Earth.
Key Coordinate Features:
- Axis: Imaginary line connecting North Pole and South Pole, tilted at 23.5 degrees to the perpendicular plane.
- Equator: 0-degree latitude dividing Earth into Northern and Southern Hemispheres.
- Latitudes (Parallels): Circles parallel to the Equator from 0° to 90°N/S (Tropic of Cancer 23.5°N, Tropic of Capricorn 23.5°S).
- Longitudes (Meridians): Semicircles passing from pole to pole. Prime Meridian is 0° at Greenwich, London.
- International Date Line: Approximately 180° longitude.
Earth Movements:
- Rotation: Earth spins on its axis from West to East once every 24 hours, causing day and night.
- Revolution: Earth orbits the Sun once in 365.25 days, causing seasons due to axial tilt.""",
    },

    # --- TS CLASS 7 ---
    {
        "board": "TS",
        "class_num": 7,
        "class": 7,
        "subject": "Mathematics",
        "chapter": "Fractions, Decimals and Rational Numbers",
        "text": """Chapter 2: Fractions, Decimals and Rational Numbers (Telangana SCERT Class 7 Mathematics).
Rational Numbers:
A rational number is any number that can be expressed in the form p/q, where p and q are integers and q != 0.
Operations on Rational Numbers:
- Addition: p/q + r/s = (ps + qr) / (qs).
- Multiplication: (p/q) * (r/s) = (p * r) / (q * s).
- Division: (p/q) / (r/s) = (p/q) * (s/r) (multiplication by reciprocal).
Terminating vs Non-Terminating Decimals:
A rational number p/q in simplest form has a terminating decimal expansion if and only if prime factors of denominator q are of form 2^m * 5^n.
If other prime factors exist (e.g., 3, 7), the decimal expansion is non-terminating repeating/recurring.
Worked Example:
Convert 0.375 to p/q form: 375/1000 = 3/8 (where 8 = 2^3, terminating).""",
    },
    {
        "board": "TS",
        "class_num": 7,
        "class": 7,
        "subject": "Physical Science",
        "chapter": "Heat and Measurement",
        "text": """Chapter 5: Heat and Temperature (Telangana SCERT Class 7 Science).
Heat is a form of thermal energy that flows spontaneously from an object at higher temperature to an object at lower temperature.
Temperature: The degree of hotness or coldness of a body, measured using a thermometer in Celsius (°C), Fahrenheit (°F), or Kelvin (K).
Conversion formula: (C / 5) = (F - 32) / 9.
Modes of Heat Transfer:
1. Conduction: Transfer of thermal kinetic energy between adjacent molecules without bulk movement of matter (dominant in solids).
2. Convection: Heat transfer through fluid medium accompanied by actual movement of particles due to density gradients (liquids, gases; land and sea breezes).
3. Radiation: Transfer of heat via electromagnetic waves without requiring a material medium (Sun's heat reaching Earth).""",
    },
    {
        "board": "TS",
        "class_num": 7,
        "class": 7,
        "subject": "Biological Science",
        "chapter": "Nutrition in Plants and Animals",
        "text": """Chapter 2: Nutrition in Plants (Telangana SCERT Class 7 Science).
Autotrophic Nutrition:
Green plants synthesize organic nutrients through photosynthesis:
Equation: 6CO2 + 6H2O --(Sunlight / Chlorophyll)--> C6H12O6 + 6O2.
Key Components:
- Chlorophyll: Green pigment inside chloroplasts that traps radiant solar energy.
- Stomata: Microscopic stomatal apertures guarded by crescent guard cells regulating transpiration and CO2 intake.
Heterotrophic Nutrition in Plants:
- Parasitic: Cuscuta (Dodder) produces haustoria that tap host vascular xylem/phloem.
- Saprophytic: Fungi (mushrooms) secrete enzymes onto decaying matter and absorb nutrients.
- Insectivorous: Pitcher plant and Drosera supplement nitrogen deficiency in marshy soils by digesting insects.""",
    },
    {
        "board": "TS",
        "class_num": 7,
        "class": 7,
        "subject": "Social Studies",
        "chapter": "Maps: Reading and Making",
        "text": """Chapter 1: Reading and Making Maps & The Kakatiyas (TS SCERT Class 7 Social Studies).
Map Fundamentals:
Components of a Map:
1. Distance / Scale: Ratio between distance on map and actual distance on ground (e.g., 1 cm = 10 km).
2. Direction: Cardinal points (North, South, East, West) indicated by arrow labeled 'N'.
3. Conventional Symbols: Standard cartographic signs representing railways, bridges, forests, water bodies.
Contour Lines: Imaginary lines joining places having equal elevation above mean sea level. Steep slopes have close contours; gentle slopes have widely spaced contours.
Historical Context - Kakatiya Dynasty:
Ruled Orugallu (Warangal) during 12th-14th centuries CE (King Ganapati Deva, Rani Rudrama Devi, Prataparudra). Pioneer irrigation tanks (Ramappa, Pakhal) built to sustain Deccan agricultural communities.""",
    },

    # --- TS CLASS 8 ---
    {
        "board": "TS",
        "class_num": 8,
        "class": 8,
        "subject": "Mathematics",
        "chapter": "Algebraic Expressions and Identities",
        "text": """Chapter 9: Algebraic Expressions and Identities (Telangana SCERT Class 8 Mathematics).
An algebraic expression is formed by combining variables and constants using the operations of addition, subtraction, multiplication, and division.
Terms, Factors, and Coefficients:
- A term is a product of factors. In 4x²y, 4, x, x, and y are factors.
- Numerical factor is the numerical coefficient. In -7xy, the coefficient is -7.
Monomial (1 term), Binomial (2 terms), Trinomial (3 terms), Polynomial (finite non-negative integer exponents).
Standard Algebraic Identities:
1. (a + b)² = a² + 2ab + b²
2. (a - b)² = a² - 2ab + b²
3. (a + b)(a - b) = a² - b²
4. (x + a)(x + b) = x² + (a + b)x + ab
Worked Examples:
Evaluate (103)² = (100 + 3)² = 10000 + 600 + 9 = 10609.
Factorize 49a² - 36b² = (7a)² - (6b)² = (7a + 6b)(7a - 6b).""",
    },
    {
        "board": "TS",
        "class_num": 8,
        "class": 8,
        "subject": "Physical Science",
        "chapter": "Force and Pressure",
        "text": """Chapter 1: Force and Chapter 3: Pressure (Telangana SCERT Class 8 Physical Science).
Force: A push or pull upon an object resulting from its interaction with another object.
SI Unit: Newton (N).
Types of Forces:
1. Contact Forces: Muscular force, Frictional force, Normal force, Tension.
2. Non-Contact (Action-at-a-Distance) Forces: Gravitational force, Electrostatic force, Magnetic force.
Pressure:
Pressure is force acting perpendicularly per unit surface area:
Formula: P = Force / Area (N/m² or Pascal, Pa).
Pressure in Fluids:
- Liquid pressure increases with depth: P = h * rho * g.
- Liquids exert equal pressure at the same depth in all directions.
Atmospheric Pressure: Pressure exerted by the Earth's atmospheric envelope (~101.3 kPa at sea level), measured using a mercury barometer invented by Torricelli.""",
    },
    {
        "board": "TS",
        "class_num": 8,
        "class": 8,
        "subject": "Biological Science",
        "chapter": "Cell - The Basic Unit of Life",
        "text": """Chapter 1: Cell - The Basic Unit of Life (Telangana SCERT Class 8 Biological Science).
Discovery: Robert Hooke (1665) observed dead cork cells under microscope. Antonie van Leeuwenhoek (1674) observed living cells.
Cell Theory: Schleiden and Schwann (1839) & Virchow (1855) - all living organisms are composed of cells, and all cells arise from pre-existing cells (Omnis cellula-e-cellula).
Cell Organelles and Functions:
- Plasma Membrane: Selectively permeable lipid-protein bilayer regulating cellular transport.
- Nucleus: Control center of cell containing chromosomes and DNA (genetic blueprint).
- Mitochondria: 'Powerhouse of the cell' generating ATP via aerobic cellular respiration.
- Chloroplasts: Plastids containing chlorophyll for photosynthesis (exclusive to plant cells).
- Cell Wall: Rigid outer cellulose protective layer (present in plant, fungal, and bacterial cells; absent in animals).""",
    },
    {
        "board": "TS",
        "class_num": 8,
        "class": 8,
        "subject": "Social Studies",
        "chapter": "Earth Movements and Seasons",
        "text": """Chapter 2: Energy from the Sun & Earth Movements (TS SCERT Class 8 Social Studies).
Earth Movements and Orbital Geometry:
- Perihelion: Earth closest to Sun (~January 3, 147 million km).
- Aphelion: Earth farthest from Sun (~July 4, 152 million km).
- Solstices:
  * Summer Solstice (June 21): Sun overhead at Tropic of Cancer (23.5°N); longest day in Northern Hemisphere.
  * Winter Solstice (December 22): Sun overhead at Tropic of Capricorn (23.5°S); longest day in Southern Hemisphere.
- Equinoxes (March 21 and September 23): Sun vertically overhead at the Equator; equal day and night worldwide.
Insolation: Incoming solar radiation intercepted by Earth's atmosphere and surface, influenced by angle of sun rays and duration of daylight.""",
    },

    # --- TS CLASS 9 ---
    {
        "board": "TS",
        "class_num": 9,
        "class": 9,
        "subject": "Mathematics",
        "chapter": "Polynomials and Real Numbers",
        "text": """Chapter 2: Polynomials (Telangana SCERT Class 9 Mathematics).
A polynomial p(x) in one variable x is an algebraic expression of form a_n*x^n + ... + a_1*x + a_0, where exponents are non-negative integers.
Degree: Highest power of variable x in the polynomial.
- Linear (deg 1), Quadratic (deg 2), Cubic (deg 3).
Remainder Theorem: If polynomial p(x) of degree >= 1 is divided by (x - a), the remainder is p(a).
Factor Theorem: (x - a) is a factor of p(x) if and only if p(a) = 0.
Worked Example:
Factorize 6x² + 17x + 5 by splitting the middle term:
Product ac = 6 * 5 = 30; Sum b = 17.
Factors of 30 that add to 17 are 15 and 2:
6x² + 15x + 2x + 5 = 3x(2x + 5) + 1(2x + 5) = (2x + 5)(3x + 1).""",
    },
    {
        "board": "TS",
        "class_num": 9,
        "class": 9,
        "subject": "Physical Science",
        "chapter": "Laws of Motion",
        "text": """Chapter 2: Laws of Motion (Telangana SCERT Class 9 Physical Science).
Newton's Laws of Motion:
1. First Law of Motion (Law of Inertia): Every body continues in its state of rest or uniform motion in a straight line unless acted upon by an external unbalanced force.
   Inertia depends on mass (mass is quantitative measure of inertia).
2. Second Law of Motion: The rate of change of momentum of a body is directly proportional to applied force and takes place in the direction of force:
   Momentum p = m * v.
   F = dp/dt = m * a (Force = mass * acceleration).
3. Third Law of Motion: For every action, there is an equal and opposite reaction (F_AB = -F_BA).
Law of Conservation of Linear Momentum:
In an isolated system without external forces, total initial momentum equals total final momentum:
m1*u1 + m2*u2 = m1*v1 + m2*v2.""",
    },
    {
        "board": "TS",
        "class_num": 9,
        "class": 9,
        "subject": "Biological Science",
        "chapter": "Plant and Animal Tissues",
        "text": """Chapter 2: Plant Tissues & Chapter 3: Animal Tissues (Telangana SCERT Class 9 Biological Science).
Plant Tissues:
1. Meristematic Tissue: Rapidly dividing cells driving growth (Apical meristem - root/shoot tip length; Lateral meristem/cambium - girth; Intercalary meristem - internodes).
2. Permanent Tissues:
   - Simple: Parenchyma (storage/photosynthesis), Collenchyma (flexibility), Sclerenchyma (lignified rigidity, e.g., coconut husk).
   - Complex Vascular:
     * Xylem: Transports water/minerals unidirectionally (tracheids, vessels, xylem parenchyma, xylem fibres).
     * Phloem: Transports synthesized organic solutes bidirectionally (sieve tubes, companion cells, phloem parenchyma, phloem fibres).
Animal Tissues:
- Epithelial: Protective barrier covers body and organs (squamous, cuboidal, columnar, ciliated).
- Connective: Areolar, adipose (fat insulation), tendon (muscle to bone), ligament (bone to bone), cartilage, bone, and blood.""",
    },
    {
        "board": "TS",
        "class_num": 9,
        "class": 9,
        "subject": "Social Studies",
        "chapter": "Democratic Government and Constitution",
        "text": """Chapter 13: Democratic and Nationalist Revolutions & Indian Constitution (TS SCERT Class 9 Social Studies).
Constituent Assembly of India:
Elected indirectly by provincial assemblies; Dr. Rajendra Prasad served as President and Dr. B.R. Ambedkar was Chairman of Drafting Committee.
Adopted November 26, 1949; came into full force on January 26, 1950 (Republic Day).
The Preamble Declares India to be a:
- Sovereign: Free from external control.
- Socialist: Social and economic equality through democratic welfare.
- Secular: No state religion; all religions treated impartially.
- Democratic: Government derived from free universal adult franchise.
- Republic: Head of state is elected, not hereditary.
Fundamental Rights (Articles 12-35): Equality, Freedom, Against Exploitation, Freedom of Religion, Cultural & Educational, and Constitutional Remedies (Article 32 - Heart and Soul of Constitution).""",
    },

    # --- TS CLASS 10 ---
    {
        "board": "TS",
        "class_num": 10,
        "class": 10,
        "subject": "Mathematics",
        "chapter": "Real Numbers and Trigonometry",
        "text": """Chapter 1: Real Numbers & Chapter 11: Trigonometry (Telangana SCERT Class 10 Mathematics).
Real Numbers:
Euclid's Division Lemma: Given positive integers a and b, there exist unique integers q and r satisfying a = bq + r, where 0 <= r < b.
Fundamental Theorem of Arithmetic: Every composite number can be uniquely factorized into a product of prime numbers, up to the order of factors.
Trigonometry:
For a right-angled triangle with acute angle theta:
sin(theta) = Opposite / Hypotenuse, cos(theta) = Adjacent / Hypotenuse, tan(theta) = Opposite / Adjacent.
Standard Identities:
1. sin²(theta) + cos²(theta) = 1
2. sec²(theta) - tan²(theta) = 1 (where theta != 90°)
3. cosec²(theta) - cot²(theta) = 1 (where theta != 0°)
Specific Values:
sin(30°) = 1/2, sin(45°) = 1/sqrt(2), sin(60°) = sqrt(3)/2, sin(90°) = 1.
cos(30°) = sqrt(3)/2, cos(45°) = 1/sqrt(2), cos(60°) = 1/2, cos(90°) = 0.""",
    },
    {
        "board": "TS",
        "class_num": 10,
        "class": 10,
        "subject": "Physical Science",
        "chapter": "Refraction of Light at Curved Surfaces",
        "text": """Chapter 4: Refraction of Light at Curved Surfaces & Chemical Reactions (TS SCERT Class 10 Physical Science).
Refraction at Curved Surfaces:
Lens Formula: 1/f = 1/v - 1/u (where f = focal length, v = image distance, u = object distance).
Lens Maker's Formula: 1/f = (n - 1) * (1/R1 - 1/R2) (where n is refractive index and R1, R2 are radii of curvature).
Magnification m = v / u = Height of image (h') / Height of object (h).
Convex Lens: Converging lens, forms real inverted images for u > f, and virtual erect magnified image when object is placed between optical center and focus.
Concave Lens: Diverging lens, always forms virtual, erect, and diminished images.
Chemical Reactions:
Law of Conservation of Mass: Total mass of reactants equals total mass of products in a balanced chemical equation.
Example: 2Mg + O2 -> 2MgO (Combination reaction and exothermic oxidation).""",
    },
    {
        "board": "TS",
        "class_num": 10,
        "class": 10,
        "subject": "Biological Science",
        "chapter": "Life Processes: Nutrition and Respiration",
        "text": """Chapter 1: Nutrition & Chapter 2: Respiration (Telangana SCERT Class 10 Biological Science).
Human Alimentary Canal and Digestion:
- Mouth: Salivary amylase breaks starch into maltose.
- Stomach: Gastric juice contains HCl (creates acidic pH ~1.5-2.0, kills pathogens) and pepsin (digests proteins).
- Small Intestine (Duodenum/Ileum): Emulsification of fats by bile salts; pancreatic juice (trypsin, lipase); intestinal villi absorb nutrients into bloodstream.
Respiration:
Aerobic Respiration: In presence of oxygen; Glycolysis in cytoplasm yields pyruvate, which enters mitochondria for Krebs cycle producing 38 ATP + 6CO2 + 6H2O.
Anaerobic Respiration / Fermentation: In absence of oxygen; yeast converts pyruvate into ethanol + CO2 + 2 ATP; human muscle cells form lactic acid causing muscle fatigue.""",
    },
    {
        "board": "TS",
        "class_num": 10,
        "class": 10,
        "subject": "Social Studies",
        "chapter": "India: Relief Features and Water Resources",
        "text": """Chapter 1: India: Relief Features & Chapter 3: Production and Employment (TS SCERT Class 10 Social Studies).
Physiographic Divisions of India:
1. The Himalayas: Three parallel ranges - Himadri (Greater Himalayas, avg 6100 m), Himachal (Lesser Himalayas), Shivaliks (outer foothills). Guard northern frontier, source of perennial rivers.
2. Indo-Gangetic Plains: Formed by alluvial deposition of Indus, Ganga, and Brahmaputra river systems (Bhabar, Terai, Bhangar, Khadar).
3. The Peninsular Plateau: Ancient Gondwana landmass divided by Narmada river into Central Highlands (Malwa) and Deccan Plateau, bounded by Western Ghats (continuous, higher) and Eastern Ghats (discontinuous).
4. Coastal Plains (Western & Eastern) and Island groups (Andaman & Nicobar, Lakshadweep coral atolls).
Economic Sectors: Primary (Agriculture), Secondary (Manufacturing), Tertiary (Services - dominant driver of Indian GDP).""",
    },

    # =========================================================================
    # ICSE (CISCE) BOARD - CLASSES 6 TO 10
    # =========================================================================

    # --- ICSE CLASS 6 ---
    {
        "board": "ICSE",
        "class_num": 6,
        "class": 6,
        "subject": "Mathematics",
        "chapter": "Number Systems and Basic Algebra",
        "text": """Chapter 1: Number Systems & Chapter 8: Introduction to Algebra (ICSE Class 6 Mathematics).
Number Concepts:
Natural Numbers N = {1, 2, 3, ...}, Whole Numbers W = {0, 1, 2, ...}, Integers Z = {..., -2, -1, 0, 1, 2, ...}.
Highest Common Factor (HCF) and Lowest Common Multiple (LCM):
Relationship: HCF(a, b) * LCM(a, b) = a * b.
Prime and Composite Numbers: Sieve of Eratosthenes identifies primes (having only two factors: 1 and itself).
Introductory Algebra:
Variables: Symbols representing unknown changing numerical quantities (x, y, z).
Constants: Quantities with fixed numerical value.
Algebraic Operations: Addition and subtraction applied only between like terms (terms with identical variable components).
Example: 3x + 5y - 2x + y = (3x - 2x) + (5y + y) = x + 6y.""",
    },
    {
        "board": "ICSE",
        "class_num": 6,
        "class": 6,
        "subject": "Physical Science",
        "chapter": "Matter and Physical Quantities",
        "text": """Chapter 1: Matter & Chapter 2: Physical Quantities and Measurement (ICSE Class 6 Physics/Chemistry).
Matter is anything that has mass and occupies space.
States of Matter according to Kinetic Molecular Theory:
1. Solid: Definite shape and definite volume; particles closely packed in fixed lattice with strong intermolecular forces and low kinetic energy.
2. Liquid: Definite volume but no fixed shape; particles loosely held with moderate intermolecular space, can flow.
3. Gas: Neither definite shape nor definite volume; maximum intermolecular spaces and negligible attractive forces, particles exhibit rapid random Brownian motion.
Physical Quantities and SI Units:
- Length: Metre (m). Mass: Kilogram (kg). Time: Second (s).
- Density = Mass / Volume (kg/m³). Relative density = Density of substance / Density of water at 4°C.""",
    },
    {
        "board": "ICSE",
        "class_num": 6,
        "class": 6,
        "subject": "Biological Science",
        "chapter": "Plant Life: Leaf and Flower",
        "text": """Chapter 1: Plant Life - The Leaf & Flower (ICSE Class 6 Biology).
Structure of a Typical Leaf:
- Petiole: Leaf stalk attaching lamina to the stem node.
- Lamina (Leaf Blade): Broad green photosynthetic surface.
- Midrib and Veins: Vascular bundle channels providing mechanical support and conduction.
- Venation: Arrangement of veins on lamina (Reticulate venation in dicots like mango; Parallel venation in monocots like maize).
Parts of a Flower:
1. Calyx (Sepals): Protect flower in bud stage.
2. Corolla (Petals): Brightly colored, scented to attract pollinating insects.
3. Androecium (Male reproductive organ): Stamens comprising anther (pollen production) and filament.
4. Gynoecium / Pistil (Female reproductive organ): Comprising stigma, style, and ovary containing ovules.
Pollination: Transfer of pollen from anther to stigma (Self-pollination vs Cross-pollination).""",
    },
    {
        "board": "ICSE",
        "class_num": 6,
        "class": 6,
        "subject": "Social Studies",
        "chapter": "Indus Valley Civilization and Vedic Age",
        "text": """Chapter 2: The River Valley Civilizations - Indus Valley (ICSE Class 6 History & Civics).
The Indus Valley (Harappan) Civilization (c. 2500 BCE - 1750 BCE):
Major Sites: Harappa (on river Ravi) discovered by Daya Ram Sahni (1921); Mohenjo-daro (on river Indus) discovered by R.D. Banerjee (1922).
Key Urban Planning Features:
- Citadel: Raised western mound housing public buildings (The Great Bath, Granary, Assembly Hall).
- Lower Town: Residential sector organized along strict rectangular grid pattern with streets cutting at right angles.
- Advanced Drainage: Underground baked brick drains running beneath streets with inspection manholes and soak pits.
Trade and Economy:
Bronze tools, terracotta figurines (Dancing Girl), steatite seals (Pashupati seal), maritime trade with Mesopotamia (Meluhha) via dockyard at Lothal.""",
    },

    # --- ICSE CLASS 7 ---
    {
        "board": "ICSE",
        "class_num": 7,
        "class": 7,
        "subject": "Mathematics",
        "chapter": "Rational Numbers and Commercial Mathematics",
        "text": """Chapter 2: Rational Numbers & Chapter 7: Commercial Arithmetic (ICSE Class 7 Mathematics).
Commercial Arithmetic:
- Percentage: Per hundred (x% = x/100).
- Profit and Loss:
  * Profit = Selling Price (SP) - Cost Price (CP) when SP > CP.
  * Loss = CP - SP when CP > SP.
  * Profit % = (Profit / CP) * 100; Loss % = (Loss / CP) * 100.
- Simple Interest (SI):
  Formula: SI = (P * R * T) / 100
  Where P = Principal sum, R = Rate percent per annum, T = Time period in years.
  Total Amount A = P + SI = P * (1 + (R * T)/100).
Worked Example:
Calculate SI on Rs 8,000 for 3 years at 5% per annum:
SI = (8000 * 5 * 3) / 100 = Rs 1,200. Total Amount = Rs 9,200.""",
    },
    {
        "board": "ICSE",
        "class_num": 7,
        "class": 7,
        "subject": "Physical Science",
        "chapter": "Energy: Kinetic and Potential Energy",
        "text": """Chapter 3: Energy (ICSE Class 7 Physics).
Energy is the capacity or ability of a body to do work.
SI Unit: Joule (J). 1 Kilojoule (kJ) = 1000 J.
Mechanical Energy:
1. Kinetic Energy (KE): Energy possessed by a body by virtue of its state of motion.
   Formula: KE = (1/2) * m * v² (where m = mass in kg, v = velocity in m/s).
2. Potential Energy (PE): Energy possessed by a body by virtue of its position, configuration, or state of strain.
   Gravitational Potential Energy: PE = m * g * h (where g = 9.8 m/s²).
Law of Conservation of Energy:
Energy can neither be created nor destroyed; it can only be transformed from one form into another. The total mechanical energy of an isolated system remains constant.""",
    },
    {
        "board": "ICSE",
        "class_num": 7,
        "class": 7,
        "subject": "Biological Science",
        "chapter": "Photosynthesis and Respiration",
        "text": """Chapter 3: Photosynthesis & Respiration in Plants (ICSE Class 7 Biology).
Photosynthesis is the fundamental physiological process by which green plants manufacture glucose from carbon dioxide and water in the presence of sunlight and chlorophyll.
Balanced Equation:
6CO2 + 12H2O --(Sunlight / Chlorophyll)--> C6H12O6 + 6O2 + 6H2O.
Phases:
1. Light-Dependent Reaction (Grana/Thylakoids): Photolysis of water releases oxygen: 2H2O -> 4H+ + 4e- + O2. ATP and NADPH are formed.
2. Light-Independent Reaction / Calvin Cycle (Stroma): Carbon dioxide reduced to glucose using ATP and NADPH.
Storage: Excess glucose is polymerized into insoluble starch.
Respiration in Plants: Continual biochemical oxidation of glucose inside mitochondria yielding ATP:
C6H12O6 + 6O2 -> 6CO2 + 6H2O + 38 ATP.""",
    },
    {
        "board": "ICSE",
        "class_num": 7,
        "class": 7,
        "subject": "Social Studies",
        "chapter": "The Delhi Sultanate and Medieval India",
        "text": """Chapter 4: The Delhi Sultanate (1206 - 1526 CE) (ICSE Class 7 History & Civics).
Dynasties of the Delhi Sultanate:
1. Mamluk / Slave Dynasty (1206-1290): Founded by Qutb-ud-din Aibak; strengthened by Iltutmish; Razia Sultan (first female Muslim monarch); Balban's policy of Blood and Iron.
2. Khalji Dynasty (1290-1320): Alauddin Khalji introduced market price regulations, branding of horses (Dagh), descriptive rolls (Chehra), and extensive military campaigns into the Deccan led by Malik Kafur.
3. Tughlaq Dynasty (1320-1414): Muhammad bin Tughlaq's visionary but failed experiments (capital transfer from Delhi to Daulatabad, token copper/brass currency).
4. Sayyid Dynasty (1414-1451) and Lodi Dynasty (1451-1526).
Defeat of Ibrahim Lodi by Babur at the First Battle of Panipat (1526) established the Mughal Empire.""",
    },

    # --- ICSE CLASS 8 ---
    {
        "board": "ICSE",
        "class_num": 8,
        "class": 8,
        "subject": "Mathematics",
        "chapter": "Exponents, Factorisation and Linear Equations",
        "text": """Chapter 2: Exponents & Chapter 12: Linear Equations (ICSE Class 8 Mathematics).
Laws of Indices / Exponents:
For real base a != 0 and integers m, n:
1. a^m * a^n = a^(m+n)
2. a^m / a^n = a^(m-n)
3. (a^m)^n = a^(m*n)
4. a^(-n) = 1 / a^n
5. a^0 = 1
Solving Simultaneous Linear Equations:
Standard system: a1*x + b1*y = c1 and a2*x + b2*y = c2.
Methods of Solution:
- Method of Elimination: Multiply equations by suitable coefficients so coefficients of one variable become equal, then add or subtract.
- Method of Substitution: Express one variable in terms of the other and substitute into the remaining equation.
Worked Example:
Solve: 2x + 3y = 11 and x - y = 3 => x = y + 3.
2(y + 3) + 3y = 11 => 5y + 6 = 11 => 5y = 5 => y = 1.
x = 1 + 3 = 4. Solution: x=4, y=1.""",
    },
    {
        "board": "ICSE",
        "class_num": 8,
        "class": 8,
        "subject": "Physical Science",
        "chapter": "Force, Pressure and Buoyancy",
        "text": """Chapter 1: Force and Pressure & Chapter 2: Buoyancy (ICSE Class 8 Physics).
Turning Effect of Force (Moment of Force / Torque):
Moment of Force = Force * Perpendicular distance of line of action from axis of rotation (tau = F * d). SI Unit: Newton-metre (N m).
Principle of Moments: For a body in rotational equilibrium, sum of clockwise moments = sum of anticlockwise moments.
Liquid Pressure and Archimedes' Principle:
- Liquid Pressure: P = h * rho * g (independent of container shape).
- Archimedes' Principle: When a body is completely or partially immersed in a fluid, it experiences an upward buoyant force (upthrust) equal to the weight of fluid displaced by it:
  F_buoyant = V_submerged * rho_fluid * g.
- Law of Floatation: A floating body displaces fluid whose weight equals the total weight of the floating body.""",
    },
    {
        "board": "ICSE",
        "class_num": 8,
        "class": 8,
        "subject": "Biological Science",
        "chapter": "Circulatory System and Nervous System",
        "text": """Chapter 3: Circulatory System & Chapter 5: Nervous System (ICSE Class 8 Biology).
The Human Heart and Double Circulation:
- Structure: Four chambers - two thin-walled atria (auricles) and two muscular ventricles.
- Valves: Tricuspid valve (right auricle-ventricle), Bicuspid/Mitral valve (left auricle-ventricle), Semilunar valves at base of pulmonary artery and aorta.
- Double Circulation:
  1. Pulmonary Circulation: Deoxygenated blood from right ventricle -> Pulmonary artery -> Lungs -> Oxygenated blood -> Pulmonary veins -> Left auricle.
  2. Systemic Circulation: Oxygenated blood from left ventricle -> Aorta -> Body organs -> Deoxygenated blood -> Vena cava -> Right auricle.
Nervous System:
- Neuron: Structural and functional unit comprising cyton (cell body), dendrites (receive impulses), and axon (myelin sheath, transmits impulse to synapse).
- Central Nervous System (CNS): Brain (Cerebrum - intellect/memory, Cerebellum - motor balance, Medulla oblongata - autonomic reflexes) and Spinal Cord.""",
    },
    {
        "board": "ICSE",
        "class_num": 8,
        "class": 8,
        "subject": "Social Studies",
        "chapter": "The Indian National Movement and 1857 Revolt",
        "text": """Chapter 1: The First War of Independence (1857) & The National Movement (ICSE Class 8 History & Civics).
The Revolt of 1857 (First War of Independence):
Causes:
- Political: Lord Dalhousie's Doctrine of Lapse (annexation of Satara, Jhansi, Nagpur); annexation of Awadh on grounds of misgovernance.
- Economic: Heavy land revenue settlements (Ryotwari, Permanent Settlement); destruction of Indian handicrafts.
- Military: Discrimination against Indian sepoys; General Service Enlistment Act of 1856.
- Immediate Cause: Introduction of Enfield rifle cartridges greased with animal fat (cow and pig), offending Hindu and Muslim religious sentiments.
Mangal Pandey revolted at Barrackpore on March 29, 1857.
Consequence: Government of India Act 1858 transferred power from East India Company to the British Crown under Queen Victoria's Proclamation; Governor-General became Viceroy.""",
    },

    # --- ICSE CLASS 9 ---
    {
        "board": "ICSE",
        "class_num": 9,
        "class": 9,
        "subject": "Mathematics",
        "chapter": "Compound Interest and Coordinate Geometry",
        "text": """Chapter 2: Compound Interest & Chapter 19: Coordinate Geometry (ICSE Class 9 Mathematics).
Compound Interest Formula:
When interest is compounded annually:
Amount A = P * (1 + r/100)^n
Compound Interest CI = A - P = P * [(1 + r/100)^n - 1]
When compounded semi-annually (half-yearly):
A = P * (1 + r/200)^(2n).
Coordinate Geometry:
Cartesian coordinate plane with horizontal x-axis (abscissa) and vertical y-axis (ordinate) intersecting at origin (0, 0).
Distance Formula:
Distance between points P(x1, y1) and Q(x2, y2):
d = sqrt[(x2 - x1)² + (y2 - y1)²].
Section Formula (internal division in ratio m1:m2):
x = (m1*x2 + m2*x1) / (m1 + m2); y = (m1*y2 + m2*y1) / (m1 + m2).""",
    },
    {
        "board": "ICSE",
        "class_num": 9,
        "class": 9,
        "subject": "Physical Science",
        "chapter": "Light: Refraction and Total Internal Reflection",
        "text": """Chapter 4: Refraction of Light at Plane Surfaces (ICSE Class 9 Physics).
Refraction is the change in the direction of path of light when it passes obliquely from one transparent medium into another due to change in speed.
Rules:
- Rarer to denser medium: Bends towards the normal (i > r).
- Denser to rarer medium: Bends away from normal (i < r).
Snell's Law:
sin(i) / sin(r) = constant = 1n2 (Refractive index of medium 2 with respect to medium 1).
Refractive Index n = Speed of light in vacuum (c) / Speed of light in medium (v).
Critical Angle (C) & Total Internal Reflection (TIR):
Critical angle is the angle of incidence in denser medium for which angle of refraction in rarer medium is 90°.
Relationship: n = 1 / sin(C). For glass-air, C ~ 42°; for water-air, C ~ 49°.
TIR occurs when:
1. Light travels from denser to rarer medium.
2. Angle of incidence > Critical angle.""",
    },
    {
        "board": "ICSE",
        "class_num": 9,
        "class": 9,
        "subject": "Biological Science",
        "chapter": "Cell and Tissues: The Unit of Life",
        "text": """Chapter 2: Cell - The Unit of Life & Chapter 3: Tissues (ICSE Class 9 Biology).
Cell Ultrastructure:
- Protoplasm = Cytoplasm + Nucleus (Purkinje, 1839).
- Endoplasmic Reticulum (Rough ER with ribosomes for protein synthesis; Smooth ER for lipid synthesis).
- Golgi Apparatus: Packaging and secretion of glycoproteins.
- Lysosomes: 'Suicide bags' containing hydrolytic digestive enzymes.
- Ribosomes: Site of protein synthesis (70S in prokaryotes, 80S in eukaryotes).
Cell Division:
1. Mitosis: Equational division occurring in somatic cells producing 2 identical diploid (2n) daughter cells. Stages: Prophase, Metaphase, Anaphase, Telophase.
2. Meiosis: Reduction division in germ cells producing 4 haploid (n) gametes with genetic variation via crossing over during pachytene.""",
    },
    {
        "board": "ICSE",
        "class_num": 9,
        "class": 9,
        "subject": "Social Studies",
        "chapter": "The Harappan Civilization and Fundamental Rights",
        "text": """Chapter 1: The Harappan Civilization & Civics: Fundamental Rights (ICSE Class 9 History & Civics).
Harappan Civilization Heritage:
Sources: Great Bath at Mohenjo-daro, Granaries at Harappa, Bronze Dancing Girl, Bearded Priest, Seals.
Decline Hypotheses: Floods, tectonic shifts diverting river courses, Aryan migration, deforestation, or desiccating climate.
Fundamental Rights (Constitution of India, Part III):
1. Right to Equality (Articles 14-18): Equality before law, abolition of untouchability (Art 17), abolition of titles (Art 18).
2. Right to Freedom (Articles 19-22): Freedom of speech, assembly, movement, trade.
3. Right against Exploitation (Articles 23-24): Prohibition of trafficking, forced labor, and child labor in hazardous factories.
4. Right to Constitutional Remedies (Article 32): Writs of Habeas Corpus, Mandamus, Prohibition, Quo Warranto, Certiorari.""",
    },

    # --- ICSE CLASS 10 ---
    {
        "board": "ICSE",
        "class_num": 10,
        "class": 10,
        "subject": "Mathematics",
        "chapter": "Quadratic Equations and Matrices",
        "text": """Chapter 5: Quadratic Equations & Chapter 8: Matrices (ICSE Class 10 Mathematics).
Quadratic Equations:
Standard form: ax² + bx + c = 0 (a != 0).
Quadratic Formula: x = [-b +- sqrt(b² - 4ac)] / (2a).
Discriminant D = b² - 4ac:
1. D > 0: Roots are real and unequal.
2. D = 0: Roots are real and equal (x = -b / (2a)).
3. D < 0: Roots are complex / not real.
Matrices:
A rectangular array of numbers arranged in rows and columns.
Order of Matrix: m x n (m rows, n columns).
Matrix Addition and Subtraction: Applicable only when matrices have identical order.
Matrix Multiplication: Product AB is defined if and only if number of columns in A equals number of rows in B.
If A is of order m x k and B is of order k x n, product AB has order m x n.""",
    },
    {
        "board": "ICSE",
        "class_num": 10,
        "class": 10,
        "subject": "Physical Science",
        "chapter": "Current Electricity and Electromagnetism",
        "text": """Chapter 8: Current Electricity & Chapter 9: Household Circuits (ICSE Class 10 Physics).
Ohm's Law: Electric current flowing through a conductor is directly proportional to potential difference across its ends, provided temperature remains constant:
V = I * R (where R is electrical resistance in Ohms, Omega).
Factors affecting Resistance: R = rho * (L / A) (where rho is resistivity, L is length, A is cross-sectional area).
Resistors in Combinations:
- Series: R_eq = R1 + R2 + R3. Current remains uniform across all components.
- Parallel: 1/R_eq = 1/R1 + 1/R2 + 1/R3. Potential difference remains uniform.
Electrical Power and Energy:
P = V * I = I² * R = V² / R (Watts).
Electrical Energy E = P * t (Joules). Commercial unit: 1 Kilowatt-hour (kWh) = 3.6 * 10^6 J.
Safety: Earthing wire (green/yellow), live wire (brown), neutral wire (light blue), and cartridge fuse rated in amperes.""",
    },
    {
        "board": "ICSE",
        "class_num": 10,
        "class": 10,
        "subject": "Biological Science",
        "chapter": "Genetics: Mendel's Laws and DNA",
        "text": """Chapter 3: Genetics - Some Basic Fundamentals (ICSE Class 10 Biology).
Gregor Johann Mendel is the Father of Genetics. Conducted hybridization experiments on garden pea (Pisum sativum).
Mendel's Laws of Inheritance:
1. Law of Dominance: In a monohybrid cross between two homozygous individuals with contrasting traits, only the dominant allele is expressed in F1 generation.
2. Law of Segregation (Purity of Gametes): Allele pairs separate during gamete formation, so each gamete carries only one allele for each gene.
   Monohybrid cross phenotypic ratio in F2 = 3:1 (Genotypic ratio = 1:2:1).
3. Law of Independent Assortment: When two pairs of traits are combined in a dihybrid cross, segregation of one pair of characters is independent of the other pair.
   Dihybrid cross phenotypic ratio in F2 = 9:3:3:1.
DNA Molecule: Double helical structure discovered by Watson and Crick (1953) consisting of deoxyribose sugar, phosphate, and nitrogenous bases (Adenine pairs with Thymine, Guanine pairs with Cytosine).""",
    },
    {
        "board": "ICSE",
        "class_num": 10,
        "class": 10,
        "subject": "Social Studies",
        "chapter": "First War of Independence and UN Organization",
        "text": """Chapter 1: The First War of Independence & Civics: The United Nations (ICSE Class 10 History & Civics).
The United Nations Organization (UNO):
Charter signed on June 26, 1945 at San Francisco; officially established October 24, 1945. Headquarters in New York City.
Principal Organs:
1. General Assembly: Main deliberative body representing all 193 member states.
2. Security Council: Responsible for international peace and security; 15 members (5 permanent: USA, UK, France, Russia, China with veto power; 10 non-permanent elected for 2-year terms).
3. International Court of Justice (ICJ): Principal judicial organ situated at The Hague, Netherlands (15 judges elected for 9-year terms).
Major Specialized Agencies:
- UNESCO: Education, science, culture, preservation of World Heritage sites.
- WHO: Global public health guidelines and disease eradication.
- UNICEF: Children's humanitarian welfare, health, nutrition, and emergency relief.""",
    },
]


def parse_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """
    Infers board, class, subject, and chapter from file names like:
    - TS_Class8_Mathematics_Algebra.pdf
    - ICSE_Class9_Physics_Light.pdf
    - ts_scert_class6_math_ch1.pdf
    """
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)

    meta = {
        "board": "TS",
        "class": 8,
        "subject": "Mathematics",
        "chapter": "General",
    }

    # Detect Board
    if "icse" in name.lower():
        meta["board"] = "ICSE"
    elif "ts" in name.lower() or "scert" in name.lower() or "telangana" in name.lower():
        meta["board"] = "TS"

    # Detect Class (6-10)
    class_match = re.search(r"class[-_\s]?(\d{1,2})", name, re.IGNORECASE)
    if class_match:
        c_num = int(class_match.group(1))
        if 6 <= c_num <= 10:
            meta["class"] = c_num

    # Detect Subject
    lower = name.lower()
    if "phys" in lower:
        meta["subject"] = "Physics"
    elif "chem" in lower:
        meta["subject"] = "Chemistry"
    elif "bio" in lower:
        meta["subject"] = "Biology"
    elif "sci" in lower:
        meta["subject"] = "Science"
    elif "math" in lower:
        meta["subject"] = "Mathematics"
    elif "social" in lower or "hist" in lower or "geog" in lower:
        meta["subject"] = "Social Studies"

    # Detect Chapter
    parts = re.split(r"[-_]", name)
    if len(parts) >= 4:
        meta["chapter"] = parts[-1].replace(".pdf", "").title()
    elif "ch1" in lower or "chapter1" in lower:
        meta["chapter"] = "Knowing Our Numbers" if meta["subject"] == "Mathematics" and meta["class"] == 6 else "Chapter 1"

    return meta


def split_text_into_smart_chunks(
    text: str,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> List[str]:
    """
    Splits text into coherent chunks respecting paragraph and heading boundaries.
    """
    if not text or not text.strip():
        return []

    # Clean redundant whitespace
    text = re.sub(r"\r\n|\r", "\n", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        # If a single paragraph is too large, split by sentences
        if para_len > chunk_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for s in sentences:
                s_len = len(s)
                if current_len + s_len > chunk_size and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    # Retain last piece for overlap
                    overlap_item = current_chunk[-1] if len(current_chunk[-1]) <= chunk_overlap else ""
                    current_chunk = [overlap_item, s] if overlap_item else [s]
                    current_len = sum(len(x) for x in current_chunk) + len(current_chunk)
                else:
                    current_chunk.append(s)
                    current_len += s_len + 1
        else:
            if current_len + para_len > chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return [c.strip() for c in chunks if len(c.strip()) > 30]


def extract_text_from_pdf(pdf_path: str) -> List[Tuple[int, str]]:
    """
    Extracts text page-by-page from a PDF file using pypdf.
    Returns [(page_number, text), ...]
    """
    if not PdfReader:
        raise ImportError("pypdf is required for PDF ingestion. Please install via: pip install pypdf")

    pages_data = []
    reader = PdfReader(pdf_path)
    for idx, page in enumerate(reader.pages, 1):
        try:
            txt = page.extract_text() or ""
            txt = txt.strip()
            if txt:
                pages_data.append((idx, txt))
        except Exception as e:
            print(f"  Warning: failed to extract page {idx} from {pdf_path}: {e}")

    return pages_data


def ingest_single_pdf(
    pdf_path: str,
    vector_store: ChromaVectorStore,
    board_override: Optional[str] = None,
    class_override: Optional[int] = None,
    subject_override: Optional[str] = None,
    chapter_override: Optional[str] = None,
) -> int:
    """
    Ingests a single PDF into ChromaDB with strict metadata tagging.
    """
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return 0

    inferred_meta = parse_metadata_from_filename(pdf_path)
    final_meta = {
        "board": normalize_board(board_override or inferred_meta["board"]),
        "class": int(class_override if class_override is not None else inferred_meta["class"]),
        "subject": (subject_override or inferred_meta["subject"]).strip(),
        "chapter": (chapter_override or inferred_meta["chapter"]).strip(),
        "source": os.path.basename(pdf_path),
    }

    print(f"-> Ingesting PDF: {pdf_path}")
    print(f"   Metadata: Board={final_meta['board']}, Class={final_meta['class']}, Subject={final_meta['subject']}, Chapter={final_meta['chapter']}")

    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        print(f"   No text could be extracted from {pdf_path}.")
        return 0

    all_chunks = []
    all_metas = []
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

    for page_num, page_text in pages:
        page_chunks = split_text_into_smart_chunks(page_text)
        for c_idx, chunk in enumerate(page_chunks):
            meta = dict(final_meta)
            meta["page"] = page_num
            all_chunks.append(chunk)
            all_metas.append(meta)

    chunk_ids = [f"{base_name}_p{m['page']}_c{i}" for i, m in enumerate(all_metas)]
    added_count = vector_store.add_chunks(all_chunks, all_metas, ids=chunk_ids)
    print(f"   [OK] Extracted {len(pages)} pages into {added_count} semantic chunks in ChromaDB.\n")
    return added_count


def seed_canonical_curriculum(vector_store: ChromaVectorStore) -> int:
    """
    Seeds verified canonical syllabus chunks for TS and ICSE (Physics Light, Math Algebra, Bio Photosynthesis, etc.)
    Ensures zero-cost local RAG is instantly operational on cold start.
    """
    print("-> Seeding canonical curriculum chunks for TS and ICSE...")
    chunks = []
    metas = []
    ids = []

    for idx, item in enumerate(CANONICAL_SEEDS, 1):
        item_chunks = split_text_into_smart_chunks(item["text"], chunk_size=600)
        class_val = int(item.get("class_num", item.get("class", 8)))
        for sub_idx, c in enumerate(item_chunks):
            chunks.append(c)
            metas.append({
                "board": normalize_board(item["board"]),
                "class_num": class_val,
                "class": class_val,
                "subject": item["subject"],
                "chapter": item["chapter"],
                "source": f"Official {item['board']} Class {class_val} Textbook",
            })
            ids.append(f"canonical_{item['board']}_c{class_val}_{item['subject']}_{item['chapter']}_{idx}_{sub_idx}")

    count = vector_store.add_chunks(chunks, metas, ids=ids)
    print(f"   [OK] Seeded {count} verified curriculum chunks into ChromaDB.\n")
    return count


def ingest_directory(dir_path: str, vector_store: ChromaVectorStore) -> int:
    """
    Scans a directory for all .pdf files and ingests them into ChromaDB.
    """
    if not os.path.exists(dir_path):
        print(f"Directory not found: {dir_path}")
        return 0

    pdf_files = glob.glob(os.path.join(dir_path, "**", "*.pdf"), recursive=True)
    if not pdf_files:
        print(f"No .pdf files found in {dir_path}")
        return 0

    print(f"Found {len(pdf_files)} PDF textbook(s) in {dir_path}...")
    total_chunks = 0
    for pdf in pdf_files:
        total_chunks += ingest_single_pdf(pdf, vector_store)
    return total_chunks


def main():
    parser = argparse.ArgumentParser(description="VidyaFlow PDF Textbook Ingestion Tool")
    parser.add_argument("--dir", type=str, default=None, help="Directory containing PDF textbooks to ingest")
    parser.add_argument("--file", type=str, default=None, help="Single PDF textbook to ingest")
    parser.add_argument("--board", type=str, choices=["TS", "ICSE", "Telangana"], default=None, help="Board override")
    parser.add_argument("--class", dest="class_num", type=int, choices=[6, 7, 8, 9, 10], default=None, help="Class grade override (6-10)")
    parser.add_argument("--subject", type=str, default=None, help="Subject override (e.g. Physics, Mathematics)")
    parser.add_argument("--chapter", type=str, default=None, help="Chapter override (e.g. Light, Algebra)")
    parser.add_argument("--seed-canonical", action="store_true", help="Pre-seed canonical syllabus chunks (TS & ICSE)")

    args = parser.parse_args()

    print("==================================================")
    print("      VidyaFlow Textbook Ingestion Pipeline       ")
    print("==================================================")

    store = ChromaVectorStore.get_instance()
    initial_count = store.get_count()
    print(f"Current ChromaDB collection size: {initial_count} chunks\n")

    # If canonical seed requested or collection is empty, seed verified curriculum
    if args.seed_canonical or initial_count == 0:
        seed_canonical_curriculum(store)

    # Ingest single file if specified
    if args.file:
        ingest_single_pdf(
            args.file,
            store,
            board_override=args.board,
            class_override=args.class_num,
            subject_override=args.subject,
            chapter_override=args.chapter,
        )

    # Ingest directory if specified
    if args.dir:
        ingest_directory(args.dir, store)

    # If neither file nor dir passed, check default downloads directory
    if not args.file and not args.dir:
        default_dir = os.path.join(CURRENT_DIR, "storage", "downloads")
        if os.path.exists(default_dir):
            ingest_directory(default_dir, store)

    final_count = store.get_count()
    print(f"==================================================")
    print(f"Ingestion complete! Total chunks in ChromaDB: {final_count}")
    print(f"==================================================")


if __name__ == "__main__":
    main()
