"""
AegisAI / RescueNet AI — Expanded 2,500+ Disaster NLP Training Corpus.

Generates realistic, varied, diverse disaster text reports across 9 emergency classes:
- FLOOD
- FIRE
- EARTHQUAKE
- LANDSLIDE
- CYCLONE
- BUILDING_COLLAPSE
- ROAD_ACCIDENT
- INDUSTRIAL_ACCIDENT
- OTHER
"""

import itertools
import random

LOCATIONS = [
    "Sector 17 downtown", "North Industrial Zone", "Riverside Parkway", "Main Highway 44",
    "Hillside Pass", "Coastal Harbor Bay", "Central Commercial Square", "East Suburb District",
    "Metro Rail Station", "Highway Expressway Mile 22", "Old City Market", "Residential Sector 9",
    "Valley Ridge Road", "Port Terminal 4", "University Campus Perimeter", "Southern Boulevard",
]

SEVERITY_MODIFIERS = [
    "critical", "severe", "massive", "catastrophic", "heavy", "intense",
    "rapidly spreading", "major", "life-threatening", "emergency level 3",
]

TEMPLATES = {
    "FLOOD": [
        "Heavy rainfall causing {sev} waterlogging and submerged roadways near {loc}.",
        "River broke its embankments flooding houses and submerging cars in {loc}.",
        "Flash flood warning issued as flash waters rise 4 feet along {loc}.",
        "Water levels rising rapidly in residential neighborhood at {loc}, boats deployed.",
        "Storm drain overflow causing inundated streets and stranded motorists at {loc}.",
        "Torrential downpour inundated basements and ground floors in {loc}.",
        "Dam spillway overflow inundating agricultural fields and suburban roads near {loc}.",
        "Severe water accumulation blocking main transit lines and underpasses at {loc}.",
        "Rapid surge of muddy flood water trapping residents on rooftops in {loc}.",
        "Creek overflow caused widespread flooding across lower {loc}, evacuation in progress.",
        "Monsoon surge creating lake on arterial road with submerged vehicles at {loc}.",
        "Drainage failure leading to thigh-high water in commercial alleys at {loc}.",
    ],
    "FIRE": [
        "Massive structural blaze engulfing 3-story commercial complex near {loc}.",
        "Wildfire ignited by lightning spreading fast through timber trees toward {loc}.",
        "Thick black smoke and intense flames erupting from warehouse roof at {loc}.",
        "Residential apartment building on fire, multiple fire trucks dispatched to {loc}.",
        "Scrap yard fire producing toxic fumes and expanding rapidly near {loc}.",
        "Brush fire threatening residential subdivisions along {loc}.",
        "Commercial kitchen fire spreading through ventilation ducts in {loc}.",
        "Electrical fire inside server substation creating heavy sparks and blaze in {loc}.",
        "Inferno reported in multi-unit storage facility with chemical drums near {loc}.",
        "Forest fire crown burning moving rapidly with 40kmh wind gusts approaching {loc}.",
        "Lumber mill engulfed in 4-alarm structural fire at {loc}.",
        "Flaming debris blowing onto nearby properties triggering secondary fires at {loc}.",
    ],
    "EARTHQUAKE": [
        "Magnitude 6.2 seismic tremor felt violently across city, centered near {loc}.",
        "Violent ground shaking cracked concrete pavements and shattered storefronts at {loc}.",
        "Earthquake aftershock caused structural tremors and falling masonry in {loc}.",
        "Seismic event knocked out electrical substations and fractured road bridges near {loc}.",
        "Strong earthquake tremor triggered widespread panic and building fissures in {loc}.",
        "Surface faulting and cracked building foundations reported across {loc}.",
        "Severe tremor recorded at 10km depth, swaying high-rise towers in {loc}.",
        "Subterranean shock caused broken gas mains and structural cracking in {loc}.",
        "Moderate foreshock followed by 5.8 magnitude tremor felt across {loc}.",
        "Seismological bureau alerts public to ongoing aftershocks rattling {loc}.",
        "Deep rumbling and powerful horizontal shaking caused ceiling tiles to drop in {loc}.",
        "Tremor caused partial façade collapse and brick debris falling on sidewalks in {loc}.",
    ],
    "LANDSLIDE": [
        "Massive mudslide and boulder fall completely blocked highway passage at {loc}.",
        "Heavy rains triggered hillside slope failure burying two vehicles in {loc}.",
        "Unstable cliff collapse washed earth and rocks across mountain switchback near {loc}.",
        "Debris flow containing boulders and mud surging into valley road at {loc}.",
        "Erosion slope collapse severed retaining wall and blocked traffic near {loc}.",
        "Steep embankment gave way after 48 hours of rain, threatening homes at {loc}.",
        "Rock avalanche crashing down gorge, cutting off vehicle transit to {loc}.",
        "Saturated mountain slope collapsed, engulfing road shoulder near {loc}.",
        "Earth slip and fractured soil shifting downward onto residential road in {loc}.",
        "Mudflow swept away telephone poles and obstructed primary route to {loc}.",
        "Geological survey warns of active slope movement and rockfall danger along {loc}.",
        "Gravel slide and dislodged boulders impeding emergency responder access at {loc}.",
    ],
    "CYCLONE": [
        "Category 3 cyclone making landfall with 140 km/h wind gusts approaching {loc}.",
        "Violent hurricane winds tearing off metal roofs and uprooting trees in {loc}.",
        "Severe gale storm surge flooding coastal seawalls and pier front at {loc}.",
        "Tropical cyclone warning issued, extreme barometric drop recorded near {loc}.",
        "Typhoon eyewall passing over coastline, bringing destructive wind shear to {loc}.",
        "Blinding squall line and hurricane-force gusts knocking down billboards in {loc}.",
        "Severe coastal tempest causing high waves and destructive winds across {loc}.",
        "Cyclone eyewall debris blowing dangerously down empty streets of {loc}.",
        "High-velocity ocean windstorm tearing down electrical towers near {loc}.",
        "Deep depression intensified into severe cyclonic storm approaching {loc}.",
        "Coastal surge warning as 130kmh cyclone winds batter seaside properties at {loc}.",
        "Destructive gale force wind gusts leveling light structures throughout {loc}.",
    ],
    "BUILDING_COLLAPSE": [
        "Four-story residential building suffered sudden structural collapse in {loc}.",
        "Commercial roof caved in under heavy load, trapping workers inside {loc}.",
        "Old brick masonry structure suffered sudden facade failure and debris crush at {loc}.",
        "Demolition failure caused unintended pancake collapse of warehouse in {loc}.",
        "Excavation failure caused adjacent residential foundation to collapse in {loc}.",
        "Balcony and stairwell detachment in multi-family dwelling at {loc}.",
        "Ceiling support beam fractured causing floor slab collapse in {loc}.",
        "Search and rescue teams deploying acoustic sensors to collapsed structure in {loc}.",
        "Industrial silo structure failed and collapsed onto adjacent office in {loc}.",
        "Structural columns buckled causing progressive failure of floor plates in {loc}.",
        "Historic facade collapsed outward crushing parked vehicles on street at {loc}.",
        "Pancake collapse of parking garage deck trapped vehicles and occupants in {loc}.",
    ],
    "ROAD_ACCIDENT": [
        "Multi-car pileup involving 8 passenger vehicles and freight truck on {loc}.",
        "Overturned tanker truck blocking both lanes of expressway near {loc}.",
        "Head-on collision between commuter bus and utility van along {loc}.",
        "High-speed rollover crash resulting in vehicle ejection on {loc}.",
        "Delivery van collided with highway guardrail, blocking traffic at {loc}.",
        "Chain reaction vehicle collision during foggy morning commute on {loc}.",
        "Motorcycle collision with box truck requiring immediate medevac at {loc}.",
        "T-bone crash at major traffic intersection causing severe vehicle damage at {loc}.",
        "Cargo trailer jackknifed across 3 highway lanes causing gridlock near {loc}.",
        "Sedan struck concrete divider at high speed causing vehicle intrusion on {loc}.",
        "Rear-end collision involving public transit bus and taxi at {loc}.",
        "Disabled vehicle struck from behind on shoulder of expressway at {loc}.",
    ],
    "INDUSTRIAL_ACCIDENT": [
        "High-pressure ammonia pipeline rupture at refrigeration warehouse in {loc}.",
        "Chemical vat explosion releasing dense acidic gas vapor cloud over {loc}.",
        "Toxic solvent spill from freight tanker threatening municipal drains at {loc}.",
        "Boiler explosion inside textile manufacturing facility in {loc}.",
        "Hazardous chlorine gas leak detected at water treatment facility near {loc}.",
        "Petrochemical storage tank fire with risk of BLEVE explosion at {loc}.",
        "Pressurized steam valve blowout causing flash burns to operators at {loc}.",
        "Combustible dust explosion inside grain processing elevator near {loc}.",
        "Acid drum breach during forklift transit spilling corrosive liquid at {loc}.",
        "Smelting furnace failure causing molten metal spill inside foundry in {loc}.",
        "Flammable gas leak alarm triggered inside chemical synthesizer hall at {loc}.",
        "Hazardous materials hazmat team dispatched to volatile polymer spill in {loc}.",
    ],
    "OTHER": [
        "Routine city maintenance and scheduled streetlight repair in {loc}.",
        "Lost golden retriever dog spotted wandering near playground in {loc}.",
        "Citizen inquiry regarding weekly municipal trash collection schedule in {loc}.",
        "Minor civic noise complaint about loud music from park event in {loc}.",
        "Scheduled power outage for transformer upgrades in {loc}.",
        "Pothole patching crew working on secondary road near {loc}.",
        "Water main scheduled inspection with low pressure alert in {loc}.",
        "Permit request for neighborhood block party festival in {loc}.",
        "Information request on property tax assessment office hours in {loc}.",
        "Traffic signal timing adjustment being conducted at junction in {loc}.",
        "Fallen tree branch on sidewalk cleared by municipal forestry crew at {loc}.",
        "General inquiry regarding public library weekend hours near {loc}.",
    ],
}


def get_expanded_corpus(samples_per_class: int = 300, seed: int = 42):
    """
    Generate 2,700+ diverse, realistic emergency text samples (>= 300 per class).
    """
    rng = random.Random(seed)
    corpus = []

    for cls_name, tlist in TEMPLATES.items():
        class_samples = set()
        while len(class_samples) < samples_per_class:
            tpl = rng.choice(tlist)
            loc = rng.choice(LOCATIONS)
            sev = rng.choice(SEVERITY_MODIFIERS)
            sentence = tpl.format(loc=loc, sev=sev)
            # Add minor phrase perturbations
            prefix = rng.choice(["URGENT: ", "DISPATCH REPORT: ", "INCIDENT LOG: ", "CITIZEN ALERT: ", "OPERATIONS UPDATE: ", ""])
            sample_text = f"{prefix}{sentence}"
            class_samples.add(sample_text)

        for s in class_samples:
            corpus.append((s, cls_name))

    rng.shuffle(corpus)
    return corpus
