import re

BASE_BAYS = ("Open Area", "Meeting Room", "Focus Room")


def office(
    location: str,
    city: str,
    floor_names: tuple[str, ...],
    bay_names: tuple[str, ...] = ("Open Area",),
    floor_bays: dict[str, tuple[str, ...]] | None = None,
) -> dict:
    floors = []
    for name in floor_names:
        match = re.search(r"\d+", name)
        if match:
            number = int(match.group())
        elif name == "Ground Floor":
            number = 0
        else:
            raise ValueError(f"Floor name must include a floor number: {name}")
        selected_bays = (floor_bays or {}).get(name, bay_names)
        combined_bays = tuple(dict.fromkeys((*selected_bays, *BASE_BAYS)))
        floors.append({"name": name, "number": number, "bays": list(combined_bays)})
    return {"location": location, "city": city, "address": None, "floors": floors}


OFFICES = [
    office("Bengaluru", "Bengaluru", (
        "Hebbal - 6th floor",
        "Prestige Shantiniketan-12th floor",
        "Pritech Park-5th floor",
    )),
    office("Chennai - Olympia Pinnacle", "Chennai", ("5th floor",)),
    office("Goa - Bhaskar", "Goa", (
        "B2 FE (First East)", "B2 FN (First North)", "B2 FW (First West)",
        "B2 SE (Second East)", "B2 SN (Second North)", "B2 SS (Second South)",
        "B2 SW (Second West)",
    )),
    office("Goa - Charak", "Goa", (
        "B1FE (First East)", "B1FN (First North)", "B1FS (First South)",
        "B1FW (First West)", "B1GE (Ground East)", "B1GW (Ground West)",
        "B1SE (Second East)", "B1SN (Second North)", "B1SS (Second South)",
        "B1SW (Second West)",
    )),
    office("Gurugram - DLF Cybercity", "Gurugram", ("18th Floor",)),
    office("Hyderabad - Equinox", "Hyderabad", ("3rd Floor",),
           ("Meeting Area", "ODC 1", "ODC 2", "ODC 3", "Open Area")),
    office("Hyderabad - Waverock", "Hyderabad", ("Floor 11", "Floor 12"),
           floor_bays={
               "Floor 11": ("Blue Wing", "Magenta Wing", "Orange Wing", "Reception"),
               "Floor 12": ("ODC IBM", "ODC VOVO", "ODC MS", "Open Area", "Meeting Area"),
           }),
    office("Hyderabad- Argus Block", "Hyderabad", (
        "6th Floor- A Wing", "6th Floor- B Wing", "6th Floor- C Wing",
    )),
    office("Indore - Brilliant Centre", "Indore", ("4th Floor",),
           ("Open Area", "4th Floor Meeting Area", "Meeting Area")),
    office("Jaipur - Fort Anandam", "Jaipur", ("5th Floor",)),
    office("Kochi- Nippon Q1", "Kochi", ("10th Floor",),
           ("Open Area", "Meetin Room")),
    office("Kolkata - Godrej Genesis", "Kolkata", ("7th Floor",),
           ("Open Area", "Meeting Area")),
    office("Mumbai - Time Square", "Mumbai", ("12th Floor",),
           ("Open Area", "Meeting Room", "Board Room")),
    office("Nagpur - Gargi", "Nagpur", ("G0", "G1", "G2", "G3", "G4"),
           ("Meeting Area",)),
    office("Nagpur - Maitreyi", "Nagpur", ("M 0", "M 2", "M 3", "M 4", "M 5", "M 6")),
    office("Noida- Logix Cyber Park", "Noida", ("4th floor",)),
    office("Pune - Aryabhata", "Pune", tuple(f"Floor {number}" for number in range(1, 7)),
           ("Open Area", "Meeting Area", "Focus Room")),
    office("Pune - Bhageerath", "Pune", tuple(f"Floor {number}" for number in range(1, 6)),
           ("Block A",)),
    office("Pune - HJ-Atharvaveda", "Pune", tuple(f"Floor A{number}" for number in range(1, 7))),
    office("Pune - HJ-Rgveda", "Pune", tuple(f"Rgveda E{number}" for number in range(1, 7))),
    office("Pune - HJ-Samaveda", "Pune", tuple(f"Floor B{number}" for number in (0, 2, 3, 4, 5, 6))),
    office("Pune - HJ-Yajurveda", "Pune", ("Floor D1",)),
    office("Pune - Pingala", "Pune", tuple(f"Floor {number}" for number in range(1, 7))),
    office("Pune - Ramanujan", "Pune", ("1st Floor", "2nd Floor", "3rd Floor", "Ground Floor")),
]

LOCATION_NAMES = tuple(item["location"] for item in OFFICES)
