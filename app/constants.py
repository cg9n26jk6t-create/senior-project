"""
Shared, Lebanon-specific lookup data used throughout the app: service areas,
issue types with their base pricing (USD), and the request state machine.
Keeping all of it in one place makes it easy to audit for anything
US-specific (there isn't any) and to re-price services later.
"""

# Areas offered as an autocomplete suggestion list on the "request help"
# location field. Customers may still type a free-text address (e.g. a
# street name near one of these areas) -- this list just seeds the
# <datalist> so the field feels familiar rather than forcing a rigid choice.
LEBANESE_AREAS = [
    "Beirut",
    "Hamra",
    "Achrafieh",
    "Verdun",
    "Baabda",
    "Jounieh",
    "Dbayeh",
    "Antelias",
    "Aley",
    "Byblos (Jbeil)",
    "Tripoli",
    "Batroun",
    "Zgharta",
    "Saida (Sidon)",
    "Tyre (Sour)",
    "Nabatieh",
    "Zahle",
    "Baalbek",
    "Chtaura",
    "Broummana",
]

# Approximate town-center coordinates for the areas above, used to seed
# demo requests with a real map pin and as a fallback lookup if a customer
# types one of these names instead of dropping a pin on the map.
LEBANESE_AREA_COORDS = {
    "Beirut": (33.8938, 35.5018),
    "Hamra": (33.8969, 35.4823),
    "Achrafieh": (33.8886, 35.5165),
    "Verdun": (33.8869, 35.4788),
    "Baabda": (33.8333, 35.5433),
    "Jounieh": (33.9808, 35.6178),
    "Dbayeh": (33.9406, 35.5947),
    "Antelias": (33.9167, 35.5833),
    "Aley": (33.8103, 35.6019),
    "Byblos (Jbeil)": (34.1208, 35.6481),
    "Tripoli": (34.4367, 35.8497),
    "Batroun": (34.2554, 35.6581),
    "Zgharta": (34.3986, 35.8964),
    "Saida (Sidon)": (33.5606, 35.3758),
    "Tyre (Sour)": (33.2704, 35.2038),
    "Nabatieh": (33.3789, 35.4839),
    "Zahle": (33.8463, 35.9019),
    "Baalbek": (34.0059, 36.2181),
    "Chtaura": (33.8175, 35.8467),
    "Broummana": (33.8811, 35.6197),
}

# Default map view: centered on Lebanon, zoomed to show the whole country.
LEBANON_MAP_CENTER = (33.8547, 35.8623)
LEBANON_MAP_DEFAULT_ZOOM = 9

# issue_type key -> (display label, base price in USD). "other" always
# requires the customer to describe the problem in their own words (see
# ServiceRequestForm.details); a base price for it is a starting estimate,
# not a final quote, since the mechanic hasn't seen the vehicle yet.
ISSUE_TYPES = {
    "flat_tire": ("Flat tire", 30),
    "dead_battery": ("Dead battery", 25),
    "lockout": ("Lockout", 35),
    "out_of_fuel": ("Out of fuel", 20),
    "engine_trouble": ("Engine trouble", 60),
    "accident_tow": ("Accident / tow", 85),
    "overheating": ("Engine overheating", 45),
    "brake_issue": ("Brake problems", 40),
    "electrical_issue": ("Electrical issue", 35),
    "transmission_issue": ("Transmission trouble", 65),
    "other": ("Other (describe below)", 35),
}

URGENT_SURCHARGE = 10

# The cut RoadRescue keeps from each completed job; the mechanic is paid the
# rest. Applied once, at completion time, and the resulting dollar amount is
# stored on the request itself (ServiceRequest.platform_fee) rather than
# recomputed later, so a future change to this rate never rewrites the
# history of jobs already done.
PLATFORM_COMMISSION_RATE = 0.15

# How a customer wants the job handled: fixed immediately wherever they are,
# or scheduled as a drop-off at the mechanic's own workshop.
SERVICE_MODES = {
    "on_demand": "Fix it now -- a mechanic comes to me",
    "appointment": "Book an appointment -- I'll drop off my car",
}

APPOINTMENT_TIME_SLOTS = [
    ("morning", "Morning (8am - 12pm)"),
    ("afternoon", "Afternoon (12pm - 4pm)"),
    ("evening", "Evening (4pm - 7pm)"),
]

PAYMENT_METHOD_CHOICES = [
    ("app", "Pay in app"),
    ("cash", "Pay with cash"),
]

# Ordered request lifecycle. Each status can only move to the next one
# (see ServiceRequest.advance_to in models.py for the enforcement).
REQUEST_STATUSES = [
    "pending",
    "accepted",
    "enroute",
    "arrived",
    "inprogress",
    "completed",
    "paid",
    "rated",
]

# Statuses a mechanic drives forward manually via the "advance" button.
# ("enroute" -> "arrived" instead happens automatically once the simulated
# distance reaches 0km, see ServiceRequest.refresh_tracking.)
MECHANIC_ADVANCEABLE = {
    "accepted": "enroute",
    "arrived": "inprogress",
    "inprogress": "completed",
}

# An appointment has the customer driving to the mechanic, not the other way
# around, so there's nothing to simulate a live "en route" trip for -- it
# skips straight from accepted to in-progress once the customer drops the
# car off on the scheduled day.
APPOINTMENT_ADVANCEABLE = {
    "accepted": "inprogress",
    "inprogress": "completed",
}

STATUS_LABELS = {
    "pending": "Waiting for a mechanic",
    "accepted": "Mechanic assigned",
    "enroute": "Mechanic en route",
    "arrived": "Mechanic arrived",
    "inprogress": "Job in progress",
    "completed": "Completed - payment due",
    "paid": "Paid",
    "rated": "Paid & rated",
    "cancelled": "Cancelled",
}

# Certification uploads: real-world documents are almost always a PDF or a
# photo/scan, plus plain text so the seed data and quick demo uploads don't
# require a real document on hand.
ALLOWED_CERT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}
MAX_CERT_FILE_SIZE_MB = 5

# +961 7 12 34 567 / +961 71 234 567 style numbers: country code, a one- or
# two-digit network prefix, then the rest of the local number. Spaces are
# optional and allowed between groups.
LEBANON_PHONE_REGEX = r"^\+961\s?\d{1,2}\s?\d{3}\s?\d{3,4}$"

# km/h used to compute the ETA a customer actually sees.
DISPLAY_SPEED_KMH = 30

# The simulated drive is sped up so a demo doesn't require waiting the
# realistic ~10-20 minutes for a mechanic to arrive. At 12x, a 5km trip
# (realistically ~10 minutes) completes in under a minute of wall-clock time.
DEMO_ACCELERATION = 12
