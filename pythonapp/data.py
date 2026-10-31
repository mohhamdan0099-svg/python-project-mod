# data.py - the lists the whole site uses (cities and categories).
# To add a city, add it to CITIES. To add a category group, add it to CATEGORY_GROUPS.

CITIES = [
    'Abu Dis', 'Al-Bireh', 'Al-Eizariya', 'Anabta', 'Azzun', 'Bani Naim',
    'Beit Jala', 'Beit Sahour', 'Beit Ummar', 'Beitunia', 'Bethlehem',
    'Birzeit', 'Deir Dibwan', 'Dura', 'Halhul', 'Hebron', 'Idhna',
    'Jenin', 'Jericho', 'Jerusalem', 'Nablus', 'Qabatiya', 'Qalqilya',
    'Ramallah', 'Salfit', 'Sa\'ir', 'Tarqumiya', 'Tubas', 'Tulkarm', 'Yatta',
]

CATEGORY_GROUPS = {
    'Health & Medical': [
        'General Practitioner', 'Dentist', 'Pediatrician', 'Gynecologist',
        'Dermatologist', 'Eye Doctor', 'ENT Doctor', 'Cardiologist',
        'Orthopedic Doctor', 'Physiotherapist', 'Psychologist', 'Counselor',
        'Nutritionist', 'Speech Therapist', 'Home Nursing', 'Home Blood Sampling',
    ],
    'Beauty & Wellness': [
        'Ladies Hair Salon', 'Barber', 'Makeup Artist', 'Bridal Services',
        'Nails and Manicure', 'Skin Care', 'Massage and Spa', 'Henna Artist',
    ],
    'Fitness & Sports': [
        'Personal Trainer', 'Yoga Instructor', 'Pilates Instructor',
        'Swimming Coach', 'Football Coach', 'Martial Arts Coach', 'Dance Instructor',
    ],
    'Education & Training': [
        'School Tutor', 'Math Tutor', 'English Teacher', 'Hebrew Teacher',
        'Arabic Teacher', 'Quran Teacher', 'Music Teacher', 'Art Teacher',
        'Driving Instructor', 'IT and Programming Trainer', 'Tawjihi Preparation',
        'Kindergarten Educator',
    ],
    'Legal & Business': [
        'Lawyer', 'Notary', 'Accountant', 'Tax Consultant', 'Business Consultant',
        'Marketing Consultant', 'HR Consultant', 'Insurance Agent',
        'Real Estate Agent', 'Translator', 'Customs Clearance Agent',
    ],
    'Engineering & Construction': [
        'Civil Engineer', 'Architect', 'Interior Designer', 'Land Surveyor',
        'Electrical Engineer', 'Building Contractor', 'Gypsum and Decoration',
    ],
    'Home Services': [
        'Plumber', 'Electrician', 'Carpenter', 'Painter', 'Tiler',
        'Aluminum and Glass Work', 'Welding and Blacksmith', 'Home Cleaning',
        'AC Technician', 'Appliance Repair', 'Solar Panel Technician',
        'Water Tank Cleaning', 'Satellite and Internet Installation',
        'Gardener', 'Pest Control', 'Furniture Moving', 'Locksmith',
    ],
    'Automotive': [
        'Car Mechanic', 'Car Electrician', 'Car Wash', 'Tire Service',
        'Car Body and Paint', 'Car Air Conditioning', 'Vehicle Inspection',
    ],
    'Events & Media': [
        'Photographer', 'Videographer', 'Wedding Planner', 'Event Decoration',
        'Catering', 'DJ and Live Music', 'Wedding Hall Tour',
    ],
    'Technology & Design': [
        'Web Developer', 'Mobile App Developer', 'Graphic Designer',
        'Social Media Manager', 'Phone Repair', 'Computer Repair',
        'Network Technician', 'CCTV Installation',
    ],
    'Pets & Animals': [
        'Veterinarian', 'Pet Grooming', 'Pet Training', 'Farm Animal Vet',
    ],
    'Crafts & Tailoring': [
        'Tailor', 'Embroidery (Tatreez)', 'Shoemaker', 'Upholstery',
        'Jewelry Repair', 'Watch Repair',
    ],
    'Other': ['Other'],
}

# icons (Bootstrap Icons) for the landing page
GROUP_ICONS = {
    'Health & Medical': 'bi-heart-pulse', 'Beauty & Wellness': 'bi-stars',
    'Fitness & Sports': 'bi-activity', 'Education & Training': 'bi-mortarboard',
    'Legal & Business': 'bi-briefcase', 'Engineering & Construction': 'bi-rulers',
    'Home Services': 'bi-tools', 'Automotive': 'bi-car-front',
    'Events & Media': 'bi-camera', 'Technology & Design': 'bi-laptop',
    'Pets & Animals': 'bi-balloon-heart', 'Crafts & Tailoring': 'bi-scissors',
    'Other': 'bi-grid',
}


# ---- helper functions you run ONCE from the Django shell ----

def seed():
    """Put all the categories above into the database."""
    from .models import Category
    for group, names in CATEGORY_GROUPS.items():
        for name in names:
            Category.objects.get_or_create(name=name, defaults={'group': group})


def create_admin(email, password, first_name='Admin', last_name='User'):
    """Create an admin account (the register forms can never create one)."""
    import bcrypt
    from .models import User
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    User.objects.create(first_name=first_name, last_name=last_name,
                        email=email, password=hashed, role='admin')
