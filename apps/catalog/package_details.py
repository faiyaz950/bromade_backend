from .models import PackageInclusion, ServiceInclusion, ServicePackage

# Starter copy per package. Only fills packages that have no rows yet, so edits made in admin stay.
PACKAGE_DETAILS = {
    'Classic Bathroom Clean': {
        'description': 'Regular clean that keeps one bathroom fresh and hygienic.',
        'included': [
            'Toilet bowl, seat and rim cleaning',
            'Washbasin, taps and mirror wipe-down',
            'Wall tiles wiped up to reachable height',
            'Floor scrubbing and mopping',
            'Deodorising at the end',
        ],
        'excluded': [
            'Hard water and heavy stain removal',
            'Grout scrubbing and acid wash',
            'Exhaust fan and ceiling cleaning',
        ],
    },
    'Premium Bathroom Spa': {
        'description': 'Intensive deep clean with machine scrubbing and stain removal.',
        'included': [
            'Everything in Classic Bathroom Clean',
            'Hard water and limescale stain removal',
            'Machine scrubbing of floor and wall tiles',
            'Tile grout cleaning',
            'Exhaust fan, window and door cleaning',
            'Shower area, glass partition and fittings polish',
        ],
        'excluded': [
            'Plumbing or fitting repairs',
            'Removal of permanent stains or tile damage',
        ],
    },
    'Kitchen Revival': {
        'description': 'Degreasing of the main kitchen surfaces you use every day.',
        'included': [
            'Countertop and backsplash degreasing',
            'Sink and tap scrubbing',
            'Gas stove top cleaning',
            'Outside of cabinets wiped',
            'Floor mopping',
        ],
        'excluded': [
            'Inside of cabinets and drawers',
            'Chimney and exhaust deep cleaning',
            'Appliance interiors (fridge, oven, microwave)',
        ],
    },
    'Kitchen Deep Clean Plus': {
        'description': 'Full kitchen deep clean including cabinets and chimney exterior.',
        'included': [
            'Everything in Kitchen Revival',
            'Inside and outside of all cabinets and drawers',
            'Chimney exterior and filter degreasing',
            'Fridge and microwave exterior',
            'Tile and wall degreasing up to ceiling height',
            'Window and grill cleaning',
        ],
        'excluded': [
            'Chimney motor or internal servicing',
            'Removal of pest infestations',
        ],
    },
    '1 BHK Full Clean': {
        'description': 'Top-to-bottom clean of a 1 BHK: 1 bedroom, hall, kitchen and 1 bathroom.',
        'included': [
            '1 bedroom and living room dusting and mopping',
            'Kitchen surface degreasing',
            '1 bathroom deep clean',
            'Fans, switchboards and windows wiped',
            'Balcony sweeping and mopping',
        ],
        'excluded': [
            'Sofa, carpet and mattress shampooing',
            'Wall washing and painting touch-ups',
            'Inside of wardrobes',
        ],
    },
    '2 BHK Full Clean': {
        'description': 'Top-to-bottom clean of a 2 BHK: 2 bedrooms, hall, kitchen and 2 bathrooms.',
        'included': [
            '2 bedrooms and living room dusting and mopping',
            'Kitchen surface degreasing',
            '2 bathrooms deep clean',
            'Fans, switchboards and windows wiped',
            'Balcony sweeping and mopping',
        ],
        'excluded': [
            'Sofa, carpet and mattress shampooing',
            'Wall washing and painting touch-ups',
            'Inside of wardrobes',
        ],
    },
    '3 BHK Full Clean': {
        'description': 'Top-to-bottom clean of a 3 BHK: 3 bedrooms, hall, kitchen and 3 bathrooms.',
        'included': [
            '3 bedrooms and living room dusting and mopping',
            'Kitchen surface degreasing',
            '3 bathrooms deep clean',
            'Fans, switchboards and windows wiped',
            'All balconies swept and mopped',
        ],
        'excluded': [
            'Sofa, carpet and mattress shampooing',
            'Wall washing and painting touch-ups',
            'Inside of wardrobes',
        ],
    },
    '3 Seater Sofa Clean': {
        'description': 'Shampoo and vacuum clean for one 3 seater fabric sofa.',
        'included': [
            'Dry vacuuming to remove dust',
            'Foam shampoo on seats, back and arms',
            'Spot treatment of common stains',
            'Wet extraction for faster drying',
        ],
        'excluded': [
            'Leather polish and conditioning',
            'Removal of permanent or old stains',
            'Cushion cover stitching or repair',
        ],
    },
    'Carpet Clean (upto 50 sq ft)': {
        'description': 'Deep shampoo for one carpet or rug up to 50 sq ft.',
        'included': [
            'Dry vacuuming on both sides',
            'Shampoo and brush scrub',
            'Spot stain treatment',
            'Wet extraction and quick dry',
        ],
        'excluded': [
            'Carpets larger than 50 sq ft',
            'Silk or delicate handmade rugs',
        ],
    },
    'Overhead Tank Clean': {
        'description': 'Mechanised cleaning of one overhead tank up to 1000 litres.',
        'included': [
            'Draining of remaining water',
            'Sludge and dirt removal',
            'High-pressure wall scrubbing',
            'Anti-bacterial disinfection',
            'Final rinse',
        ],
        'excluded': [
            'Underground sumps',
            'Tank or pipe leak repair',
            'Tanks larger than 1000 litres',
        ],
    },
    'Split AC Service': {
        'description': 'Jet-pump service for one split AC (indoor and outdoor unit).',
        'included': [
            'Indoor coil and filter jet cleaning',
            'Outdoor unit cleaning',
            'Drain pipe flushing',
            'Cooling and gas pressure check',
        ],
        'excluded': [
            'Gas refill (charged separately)',
            'Spare parts and PCB repair',
            'Installation or uninstallation',
        ],
    },
    'Window AC Service': {
        'description': 'Complete service for one window AC.',
        'included': [
            'Front panel and filter cleaning',
            'Coil cleaning with jet pump',
            'Drain tray cleaning',
            'Cooling performance check',
        ],
        'excluded': [
            'Gas refill (charged separately)',
            'Spare parts and compressor repair',
            'Installation or uninstallation',
        ],
    },
    'Plumbing Visit': {
        'description': 'Inspection visit by a plumber with minor fixes on the spot.',
        'included': [
            'Inspection of the reported issue',
            'Minor fixes up to 30 minutes',
            'Clear quote before any extra work',
        ],
        'excluded': [
            'Spare parts and fittings',
            'Wall breaking or concealed pipe work',
        ],
    },
    'Leak Fix Package': {
        'description': 'Fix for leaking taps, pipes or flush tanks.',
        'included': [
            'Leak detection',
            'Washer, seal or connector replacement',
            'Tap, mixer or flush tank leak repair',
            'Water flow check after repair',
        ],
        'excluded': [
            'Cost of new taps or fittings',
            'Concealed pipeline leak repair',
        ],
    },
    'Electrician Visit': {
        'description': 'Inspection visit by an electrician with minor fixes on the spot.',
        'included': [
            'Inspection of the reported issue',
            'Minor fixes up to 30 minutes',
            'Safety check of the connected points',
            'Clear quote before any extra work',
        ],
        'excluded': [
            'Spare parts and wires',
            'New wiring or concealed work',
        ],
    },
    'Switchboard Repair': {
        'description': 'Repair or replacement work on one switchboard.',
        'included': [
            'Faulty switch or socket replacement (labour)',
            'Loose connection tightening',
            'Board fixing and alignment',
            'Load and safety check',
        ],
        'excluded': [
            'Cost of switches, sockets or board',
            'MCB or main panel work',
        ],
    },
    'RO Basic Service': {
        'description': 'Routine service for one domestic RO water purifier.',
        'included': [
            'Pre-filter and sediment filter cleaning',
            'Storage tank cleaning',
            'TDS and water flow check',
            'Leak check of pipes and fittings',
        ],
        'excluded': [
            'Filter, membrane or spare part replacement',
            'Installation or uninstallation',
        ],
    },
    'Washer Inspection Visit': {
        'description': 'Diagnosis visit for a washing machine that is not working right.',
        'included': [
            'Full diagnosis of the problem',
            'Minor fixes up to 30 minutes',
            'Clear quote before any repair',
        ],
        'excluded': [
            'Spare parts (motor, PCB, belt, etc.)',
            'Drum cleaning or descaling',
        ],
    },
    '1 BHK Pest Control': {
        'description': 'Cockroach and ant treatment for a 1 BHK home.',
        'included': [
            'Gel treatment in kitchen and bathroom',
            'Spray in corners, drains and cracks',
            'Odourless, family-safe chemicals',
            '30 day service warranty',
        ],
        'excluded': [
            'Termite and bed bug treatment',
            'Rodent control',
        ],
    },
    '2 BHK Pest Control': {
        'description': 'Cockroach and ant treatment for a 2 BHK home.',
        'included': [
            'Gel treatment in kitchen and all bathrooms',
            'Spray in corners, drains and cracks in every room',
            'Odourless, family-safe chemicals',
            '30 day service warranty',
        ],
        'excluded': [
            'Termite and bed bug treatment',
            'Rodent control',
        ],
    },
    'Painting Consultation Visit': {
        'description': 'An expert visits to measure your walls and give a painting quote.',
        'included': [
            'Wall measurement and condition check',
            'Colour and finish suggestions',
            'Written quote with timeline',
            'Visit fee adjusted if you book the job',
        ],
        'excluded': [
            'Actual painting work',
            'Paint and material cost',
        ],
    },
    'Small Office Clean': {
        'description': 'Deep clean for offices up to 1000 sq ft.',
        'included': [
            'Desks, chairs and glass surfaces wiped',
            'Floor vacuuming and mopping',
            'Pantry and washroom cleaning',
            'Dustbins emptied and cleaned',
            'Doors, windows and switchboards wiped',
        ],
        'excluded': [
            'Offices larger than 1000 sq ft',
            'Carpet shampoo and upholstery cleaning',
            'Electronics and server room cleaning',
        ],
    },
}


def seed_package_details():
    filled = 0
    for package in ServicePackage.objects.filter(name__in=PACKAGE_DETAILS):
        details = PACKAGE_DETAILS[package.name]
        generic = f'{package.name}: professional'
        if not package.description.strip() or package.description.startswith(generic):
            package.description = details['description']
            package.save(update_fields=['description', 'updated_at'])
        if package.inclusions.exists():
            continue
        rows = [
            PackageInclusion(package=package, kind=kind, text=text, sort_order=index)
            for kind, key in ((ServiceInclusion.Kind.INCLUDED, 'included'), (ServiceInclusion.Kind.EXCLUDED, 'excluded'))
            for index, text in enumerate(details[key])
        ]
        PackageInclusion.objects.bulk_create(rows)
        filled += 1
    return filled
