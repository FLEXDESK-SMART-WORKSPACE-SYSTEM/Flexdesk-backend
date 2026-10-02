from datetime import date, time, timedelta

from sqlalchemy import select

from app.db import Base, SessionLocal, ensure_schema, engine
from app.models import Bay, Booking, Floor, Location, Preference, User, Workspace

Base.metadata.create_all(bind=engine)
ensure_schema()

OFFICES = [
    ("Pune - Bhageerath", "Pune", "402, Senapati Bapat Road, Shivaji Co-operative Housing Society, Gokhalenagar, Pune, Maharashtra - 411016", "Registered Office & HQ"),
    ("Pune - Aryabhata-Pingala", "Pune", "9A, 12, Kashibai Khilare Path, Erandwane, Pune, Maharashtra - 411004", "Aryabhata-Pingala"),
    ("Pune - Hinjawadi Veda Complex", "Pune", "Plot No. 39, Hinjawadi Phase 1 Road, MIDC, Rajiv Gandhi Information Technology Park, Pune, Maharashtra - 411057", "Veda Complex"),
    ("Pune - Blue Ridge Township", "Pune", "B9 The Loft Commercial Building, Sector R-1, Hinjawadi, Pune, Maharashtra - 411057", "Blue Ridge"),
    ("Pune - Qubix Business Park", "Pune", "4th & 5th Floor, Building IT 3, Zone C-1, SEZ, Hinjawadi, Pune, Maharashtra - 411057", "Qubix Business Park"),
    ("Bengaluru - Pritech Park SEZ", "Bengaluru", "5th Floor, Block 9, Pritech Park SEZ, Belandur Village, Varthur Hobli, Bengaluru, Karnataka - 560103", "5th Floor - Block 9"),
    ("Bengaluru - Prestige Shantiniketan", "Bengaluru", "12th Floor, Crescent 1, Prestige Shantiniketan Business Precinct, Whitefield, Bengaluru, Karnataka - 560048", "12th Floor - Crescent 1"),
    ("Bengaluru - Karle Town Centre", "Bengaluru", "6th Floor, The Cube at Karle Town Center, Manyata Tech Park, Nagavara, Bengaluru, Karnataka - 560024", "6th Floor - The Cube"),
    ("Hyderabad - WaveRock", "Hyderabad", "11th & 12th Floor, WaveRock Building, Survey No. 115, TSIIC IT/ITES SEZ, Nanakramguda, Gachibowli, Hyderabad, Telangana - 500032", "11th Floor - WaveRock"),
    ("Hyderabad - Argus Block", "Hyderabad", "6th Floor, T-Hub, Gate 11, Argus Building, Silpa Gram Craft Village, Madhapur, Hyderabad, Telangana - 500081", "6th Floor - A Wing"),
    ("Mumbai - Andheri East", "Mumbai", "12th Floor, Tower C, Times Square Building, Andheri-Kurla Road, Marol, Mumbai, Maharashtra - 400059", "12th Floor - Tower C"),
    ("Navi Mumbai - Regional Facility", "Navi Mumbai", "Regional corporate support facility, Navi Mumbai, Maharashtra", "Regional Office"),
    ("Nagpur - IT Park MIDC", "Nagpur", "Plot No. 8 and 9, IT Park Road, Parsodi, MIDC, Trimurti Nagar, Nagpur, Maharashtra - 440022", "IT Park - Gargi-Maitreyi"),
    ("Gurugram - DLF Cyber City", "Gurugram", "18th Floor, DLF Building No. 5, Tower C, DLF Cyber City, Sector 24, Gurugram, Haryana - 122002", "18th Floor - Tower C"),
    ("Noida - Logix Cyber Park", "Noida", "4th Floor, Tower B, Logix Cyber Park, C-28 & 29, Sector 62, Noida, Uttar Pradesh - 201301", "4th Floor - Tower B"),
    ("Kolkata - Salt Lake Center", "Kolkata", "7th Floor, Godrej Genesis Building, EP Block, Sector V, Bidhannagar, Kolkata, West Bengal - 700091", "7th Floor - Godrej Genesis"),
    ("Indore - Race Course Road", "Indore", "4th & 5th Floor, Brilliant Centre, 17 Race Course Road, Indore, Madhya Pradesh - 452003", "4th Floor - Brilliant Centre"),
    ("Ahmedabad - Navratna Corporate Park", "Ahmedabad", "11th Floor, Block A, Navratna Corporate Park, Bodakdev, Ahmedabad, Gujarat - 380058", "11th Floor - Block A"),
    ("Vadodara - OHM Business Park", "Vadodara", "5th Floor, OHM Business Park, Ellora Park Road, Subhanpura, Vadodara, Gujarat - 390023", "5th Floor - OHM"),
    ("Chennai - Olympia Pinnacle", "Chennai", "Olympia Pinnacle, Seevaram, Thoraipakkam, Chennai, Tamil Nadu - 600097", "Olympia Pinnacle"),
    ("Goa - Verna Industrial Estate", "Goa", "Unit 1, Software Technology Park, L-44, Verna Industrial Estate, Verna, Goa - 403722", "Verna - Bhaskar Charak"),
]


def add_workspace_set(bay: Bay, prefix: str) -> None:
    if bay.workspaces:
        return
    bay.workspaces = [
        Workspace(name=f"{prefix}-01", workspace_type="desk", capacity=1, has_monitor=True, has_power=True, is_quiet=True),
        Workspace(name=f"{prefix}-02", workspace_type="desk", capacity=1, has_monitor=True, has_power=True),
        Workspace(name=f"{prefix}-03", workspace_type="desk", capacity=1, has_power=True, has_window=True),
        Workspace(name=f"{prefix}-04", workspace_type="desk", capacity=1, has_power=True),
        Workspace(name=f"{prefix}-Focus", workspace_type="focus room", capacity=2, has_monitor=True, has_power=True, has_window=True, is_quiet=True),
        Workspace(name=f"{prefix}-Meeting", workspace_type="meeting room", capacity=8, has_monitor=True, has_power=True, has_window=True),
    ]


def password_digest(password: str) -> str:
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", password.encode(), b"flexdesk-auth", 120_000).hex()


with SessionLocal() as db:
    demo_user = db.scalar(select(User).where(User.username == "ipshita"))
    if not demo_user:
        db.add(User(username="ipshita", name="Ipshita Das", email="ipshita@persistent.com", department="Engineering", password_hash=password_digest("1234")))
    else:
        demo_user.name = "Ipshita Das"
        demo_user.password_hash = password_digest("1234")

    for name, city, address, floor_name in OFFICES:
        location = db.scalar(select(Location).where(Location.name == name))
        if not location:
            location = Location(name=name, city=city, address=address)
            db.add(location)
            db.flush()
        if not location.floors:
            floor = Floor(name=floor_name, floor_number=1, location=location)
            db.add(floor)
            db.flush()
            for bay_name, bay_type in (("Open Area", "open"), ("Focus Rooms", "quiet"), ("Meeting Rooms", "meeting")):
                bay = Bay(name=bay_name, bay_type=bay_type, floor=floor)
                add_workspace_set(bay, f"{city[:3].upper()}-{floor.id}-{bay_name[:2].upper()}")
                db.add(bay)

    db.flush()
    user = db.scalar(select(User).where(User.username == "ipshita"))
    first_workspace = db.scalar(select(Workspace).order_by(Workspace.id))
    if user and not db.scalar(select(Preference).where(Preference.user_id == user.id)):
        db.add(Preference(user_id=user.id, preferred_type="desk", preferred_location="Pune", preferred_facilities="monitor,power", quiet_preference=True))
    if user and first_workspace and not db.scalar(select(Booking).where(Booking.user_id == user.id)):
        db.add(Booking(user_id=user.id, workspace_id=first_workspace.id, booking_date=date.today() + timedelta(days=1), start_time=time(9, 0), end_time=time(17, 0), status="confirmed"))

    db.commit()

print(f"FLEXDESK seed complete: {len(OFFICES)} Persistent locations available")
