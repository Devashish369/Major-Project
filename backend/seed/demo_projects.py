"""
seed/demo_projects.py – Pure data for the demo: 12 fictional users and the
16 hand-designed projects of PROJECT_SPEC.md section 10.

No dates live here.  seed_demo.py generates every date relative to today and
derives each project's due date from its own Monte Carlo forecast, so a story
such as "delayed" or "healthy" stays true no matter which day you rebuild.

Task line format (one per line):   Module | Title | skill,skill | estimate_hours
Tasks are listed in the order they would be worked on; the seeder marks the
first tasks as done, the next few in progress and the rest todo.

Per-project tuning knobs (params):
  progress   share of estimated hours already done (0..1)
  wip        number of in-progress tasks (default: ~25% of open tasks)
  overdue    number of open tasks whose due date is already past
  slip       expected-progress minus actual-progress (the health "slip" input)
  f          slack = days left until due ÷ forecast P50 days
             (f≈1.5 comfortable · ≈1.0 coin-flip · <0.85 almost surely late)
  dens       probability a task depends on the previous task of its module
  growth     mean log(actual/estimate) of finished tasks (0.05 normal, 0.4 scope creep)
  unassigned leave every open task without an assignee
  skew       (user, share) send that share of open tasks to one person
  idle       user who is a member but gets (almost) no work
  elapsed    force "project started N days ago"
  cross      [(module_a, module_b)] tasks of module_a also depend on module_b tasks
expect = (designed health level, (min, max) delay probability)
"""

import os

# ── 12 fictional users ───────────────────────────────────────────────────────
# key: (full name, skills 1-5, on_time_rate)
USERS = {
    "aarav":  ("Aarav Mehta",      {"react": 5, "typescript": 4, "css": 4, "ux": 2},                     0.88),
    "priya":  ("Priya Nair",       {"python": 5, "fastapi": 4, "sql": 4, "security": 3},                 0.91),
    "rohan":  ("Rohan Gupta",      {"node": 5, "sql": 4, "aws": 3, "python": 3},                         0.72),
    "sneha":  ("Sneha Kulkarni",   {"ml": 5, "python": 4, "data": 5},                                    0.84),
    "karan":  ("Karan Singh",      {"testing": 5, "automation": 4, "python": 2},                         0.79),
    "ananya": ("Ananya Iyer",      {"devops": 5, "docker": 5, "aws": 4, "ci": 4},                        0.86),
    "vikram": ("Vikram Rao",       {"figma": 5, "ux": 5, "css": 3},                                      0.68),
    "meera":  ("Meera Joshi",      {"react": 4, "python": 4, "sql": 3, "testing": 3},                    0.76),
    "arjun":  ("Arjun Verma",      {"flutter": 5, "mobile": 5, "node": 3, "react": 2},                   0.58),
    "divya":  ("Divya Menon",      {"ml": 4, "data": 4, "sql": 3, "python": 3},                          0.81),
    "sid":    ("Siddharth Jain",   {"react": 2, "node": 2, "css": 3, "testing": 2},                      0.62),
    "neha":   ("Neha Kapoor",      {"python": 4, "sql": 5, "security": 5, "fastapi": 3},                 0.93),
}

# Extra login that is an admin of every project, so one account shows all 16.
PRESENTER = ("demo@intellipm.demo", "demo", "Demo Presenter")
DEMO_EMAIL_DOMAIN = "@intellipm.demo"
# Override for a public deployment:  DEMO_PASSWORD="something-else" python -m seed.seed_demo
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo@1234")

PROJECTS = [
    # ── 1 ─────────────────────────────────────────────────────────────────
    dict(
        title="Hospital Management System", priority="high",
        story="Healthy, on track",
        description="Web system for patient records, appointments and billing for a 200-bed hospital.",
        expect=("Low risk", (0.0, 0.25)),
        params=dict(progress=0.45, slip=0.0, f=1.5, dens=0.25, growth=0.05, overdue=0, sprints=3),
        team=[("priya", "admin", 32), ("aarav", "member", 30), ("meera", "member", 28),
              ("karan", "member", 24), ("ananya", "member", 20), ("vikram", "member", 16)],
        tasks="""
Auth & Roles | Design role model (doctor, nurse, admin) | security,sql | 6
Auth & Roles | Implement login and JWT sessions | python,fastapi | 10
Auth & Roles | Role-based access middleware | python,security | 8
Patient Records | Patient registration form UI | react,css | 12
Patient Records | Patient table schema and migrations | sql,python | 8
Patient Records | Medical history timeline view | react,typescript | 14
Patient Records | Upload and store lab reports | python,aws | 12
Appointments | Doctor availability calendar | react,typescript | 16
Appointments | Booking API with clash detection | python,fastapi | 14
Appointments | SMS and email reminders | python | 8
Billing | Invoice generation service | python,sql | 14
Billing | Insurance claim export | python | 10
Billing | Billing dashboard | react,css | 12
Quality | End-to-end test suite | testing,automation | 16
Quality | Accessibility review of patient screens | ux,css | 6
Deployment | CI pipeline and staging environment | devops,docker,ci | 12
""",
        decisions=[
            ("Use role-based access control", "Permissions are attached to roles, not to individual users.",
             "Hospital staff change roles often and an audit needs a single source of truth.", "priya", 0, 40),
            ("Store lab reports in object storage", "PDF lab reports go to S3-compatible storage; only metadata in SQL.",
             "Keeps the database small and backups fast.", "ananya", 6, 25),
        ],
    ),
    # ── 2 ─────────────────────────────────────────────────────────────────
    dict(
        title="E-commerce Platform", priority="high",
        story="Delayed, high delay probability",
        description="Multi-vendor online store with catalogue, cart, payments and order tracking.",
        expect=("High risk", (0.65, 1.0)),
        params=dict(progress=0.28, slip=0.34, f=0.72, dens=0.35, growth=0.22, overdue=5, sprints=3),
        team=[("rohan", "admin", 30), ("aarav", "member", 30), ("meera", "member", 25),
              ("sid", "member", 20), ("karan", "member", 20), ("ananya", "member", 15)],
        tasks="""
Catalogue | Product schema and category tree | sql,node | 8
Catalogue | Product listing page with filters | react,typescript | 16
Catalogue | Product detail page and image gallery | react,css | 14
Catalogue | Search with autocomplete | node,sql | 18
Cart | Cart state and persistence | react,typescript | 12
Cart | Coupon and discount engine | node,sql | 16
Cart | Guest checkout flow | react,node | 14
Payments | Payment gateway integration | node,security | 22
Payments | Refund and webhook handling | node,security | 14
Payments | Payment failure retries | node | 8
Orders | Order state machine | node,sql | 14
Orders | Order tracking page | react,css | 10
Orders | Invoice PDF generation | node | 8
Vendors | Vendor onboarding portal | react,node | 18
Vendors | Payout calculation job | node,sql | 16
Vendors | Vendor analytics dashboard | react,typescript | 16
Platform | Admin moderation panel | react,node | 14
Platform | Performance and load testing | testing,automation | 16
Platform | Security hardening checklist | security | 10
Platform | Docker images and deploy scripts | devops,docker | 12
Platform | Monitoring and alerting | devops,aws | 10
Platform | Regression test suite | testing,automation | 18
""",
        decisions=[
            ("Pick Stripe-style hosted checkout", "Card data never touches our servers.",
             "Cuts PCI scope; the team has no security specialist.", "rohan", 7, 30),
            ("Postpone multi-currency", "Launch with INR only.", "Payments integration is already behind schedule.", "rohan", None, 12),
        ],
    ),
    # ── 3 ─────────────────────────────────────────────────────────────────
    dict(
        title="Mobile Banking App", priority="high",
        story="One developer severely overloaded",
        description="Cross-platform mobile app for balances, transfers, bill payment and card controls.",
        expect=("Medium risk", (0.0, 0.7)),
        params=dict(progress=0.35, slip=0.12, f=1.2, dens=0.3, growth=0.1, overdue=1,
                    skew=("arjun", 0.7), sprints=3),
        team=[("neha", "admin", 30), ("arjun", "member", 30), ("priya", "member", 24),
              ("karan", "member", 20), ("ananya", "member", 15)],
        tasks="""
Foundation | Threat model and security requirements | security | 8
Foundation | Flutter project setup and navigation | flutter,mobile | 8
Foundation | Biometric login | flutter,security | 14
Accounts | Account summary screen | flutter,mobile | 12
Accounts | Transaction history with pagination | flutter,mobile | 14
Accounts | Statement download | flutter,mobile | 8
Transfers | Beneficiary management | flutter,mobile | 14
Transfers | Fund transfer flow with OTP | flutter,security | 20
Transfers | Transfer limits API | python,fastapi | 12
Transfers | Fraud rule checks | python,security | 14
Cards | Card freeze and unfreeze | flutter,mobile | 10
Cards | Virtual card creation | flutter,mobile | 16
Payments | Bill payment integration | flutter,mobile | 16
Payments | QR code payments | flutter,mobile | 14
Release | Device compatibility testing | testing | 16
Release | Penetration test fixes | security,python | 12
Release | Store listing and release pipeline | devops,ci | 10
Release | Crash reporting setup | flutter,mobile | 6
""",
        decisions=[
            ("Use Flutter for both platforms", "One Flutter codebase for Android and iOS.",
             "Only one mobile specialist; two native apps are not affordable.", "neha", 1, 35),
            ("OTP over SMS plus in-app approval", "Transfers above the limit need an OTP and an in-app approval.",
             "Recommended by the security review.", "neha", 7, 20),
        ],
    ),
    # ── 4 ─────────────────────────────────────────────────────────────────
    dict(
        title="University Portal", priority="medium",
        story="Blocked dependency chain",
        description="Student portal for enrolment, timetables, results and fee payment.",
        expect=("Medium risk", (0.2, 1.0)),
        params=dict(progress=0.22, wip=1, slip=0.15, f=1.0, dens=0.95, growth=0.1, overdue=2, sprints=2),
        team=[("priya", "admin", 28), ("aarav", "member", 24), ("sid", "member", 20), ("karan", "member", 16)],
        tasks="""
Identity | Single sign-on with university LDAP | python,security | 12
Identity | Student profile service | python,sql | 8
Enrolment | Course catalogue API | python,sql | 10
Enrolment | Prerequisite validation | python | 14
Enrolment | Seat allocation and waitlist | python,sql | 16
Enrolment | Enrolment UI | react,typescript | 16
Timetable | Timetable generation | python | 18
Timetable | Timetable calendar view | react,css | 12
Results | Grade import from exam system | python,sql | 12
Results | Transcript PDF export | python | 10
Fees | Fee calculation rules | python,sql | 12
Fees | Online payment page | react,typescript | 14
Quality | Integration test pack | testing | 14
Quality | Load test before semester start | testing,automation | 10
""",
        decisions=[
            ("Authenticate against the existing LDAP", "No new password store; SSO through LDAP.",
             "The university IT office will not allow a second credential database.", "priya", 0, 28),
        ],
    ),
    # ── 5 ─────────────────────────────────────────────────────────────────
    dict(
        title="Food Delivery App", priority="medium",
        story="Nearly finished",
        description="Ordering app for a local restaurant group with live delivery tracking.",
        expect=("Low risk", (0.0, 0.2)),
        params=dict(progress=0.9, slip=0.0, f=1.9, dens=0.3, growth=0.06, overdue=0, wip=2, sprints=3),
        team=[("rohan", "admin", 30), ("arjun", "member", 30), ("aarav", "member", 24),
              ("karan", "member", 16), ("ananya", "member", 12)],
        tasks="""
Ordering | Restaurant and menu browsing | flutter,mobile | 14
Ordering | Cart and order placement | flutter,mobile | 14
Ordering | Order history | flutter,mobile | 8
Delivery | Rider assignment service | node,sql | 14
Delivery | Live map tracking | flutter,mobile | 16
Delivery | Delivery status push notifications | node | 8
Payments | UPI and card payments | node,security | 16
Payments | Wallet and promo codes | node,sql | 10
Restaurant | Restaurant order dashboard | react,css | 14
Restaurant | Menu management screen | react,typescript | 10
Release | Load test peak lunch traffic | testing,automation | 8
Release | Production rollout and monitoring | devops,aws | 8
""",
        decisions=[
            ("Use polling for rider location", "Riders post position every 10 s; clients poll.",
             "Simpler than sockets and good enough for the launch city.", "rohan", 4, 30),
        ],
    ),
    # ── 6 ─────────────────────────────────────────────────────────────────
    dict(
        title="Library Management", priority="low",
        story="Just started (all tasks unassigned, use Recommend assignments)",
        description="Catalogue, lending and fines system for a college library.",
        expect=("Low risk", (0.0, 0.3)),
        params=dict(progress=0.0, slip=0.0, f=1.6, dens=0.3, growth=0.05, overdue=0,
                    unassigned=True, elapsed=2, wip=0, sprints=2),
        team=[("meera", "admin", 28), ("sid", "member", 20), ("priya", "member", 20),
              ("vikram", "member", 12), ("karan", "member", 12)],
        tasks="""
Catalogue | Book and author schema | sql,python | 6
Catalogue | Catalogue search API | python,fastapi | 10
Catalogue | Catalogue search page | react,css | 12
Members | Member registration and ID cards | react,python | 10
Lending | Issue and return workflow | python,sql | 14
Lending | Fine calculation job | python,sql | 8
Lending | Overdue notice emails | python | 6
UX | Librarian desk screen mockups | figma,ux | 10
Reports | Monthly circulation report | python,sql | 8
Quality | Acceptance test scripts | testing | 8
""",
        decisions=[],
    ),
    # ── 7 ─────────────────────────────────────────────────────────────────
    dict(
        title="Smart Attendance (ML)", priority="medium",
        story="ML-skilled work, few matching members",
        description="Face-recognition attendance for classrooms with a teacher dashboard.",
        expect=("Medium risk", (0.1, 0.9)),
        params=dict(progress=0.25, slip=0.18, f=1.0, dens=0.4, growth=0.1, overdue=2,
                    skew=("sneha", 0.5), sprints=2),
        team=[("sneha", "admin", 30), ("divya", "member", 28), ("meera", "member", 24),
              ("aarav", "member", 16), ("karan", "member", 12)],
        tasks="""
Data | Collect and label classroom face dataset | data,ml | 20
Data | Augmentation and quality filters | data,python | 12
Model | Face detection baseline | ml,python | 16
Model | Face embedding training | ml,python | 24
Model | Threshold tuning and evaluation | ml,data | 14
Model | Spoof and photo-attack detection | ml | 22
Model | Model export and optimisation | ml,python | 12
Service | Recognition API | python,fastapi | 14
Service | Attendance records store | python,sql | 8
Dashboard | Teacher dashboard | react,typescript | 16
Dashboard | Absence report export | python,sql | 8
Quality | Accuracy regression tests | testing,ml | 10
""",
        decisions=[
            ("Pick a pretrained embedding over training from scratch", "Fine-tune a pretrained face embedding.",
             "The dataset is only a few thousand images.", "sneha", 3, 22),
            ("Run inference on the classroom PC", "Recognition runs locally; only attendance rows are sent to the server.",
             "Avoids sending student photos over the network.", "sneha", 6, 15),
        ],
    ),
    # ── 8 ─────────────────────────────────────────────────────────────────
    dict(
        title="Online Exam System", priority="high",
        story="Medium risk, deadline close",
        description="Proctored online exams with question banks and automatic marking, needed before the exam season.",
        expect=("Medium risk", (0.3, 0.95)),
        params=dict(progress=0.58, slip=0.2, f=0.93, dens=0.3, growth=0.12, overdue=2, sprints=3),
        team=[("neha", "admin", 30), ("aarav", "member", 28), ("rohan", "member", 24),
              ("karan", "member", 20), ("sid", "member", 20)],
        tasks="""
Question Bank | Question and answer schema | sql,python | 6
Question Bank | Question authoring UI | react,typescript | 14
Question Bank | Random paper generator | python | 12
Exam Runtime | Timed exam player | react,typescript | 18
Exam Runtime | Autosave answers | node,sql | 8
Exam Runtime | Tab-switch and webcam proctoring | react,security | 20
Marking | Auto-marking for objective questions | python | 12
Marking | Manual marking screen | react,css | 12
Marking | Result publishing | python,sql | 8
Admin | Student roster import | python,sql | 6
Admin | Exam scheduling | react,node | 10
Quality | Load test with 2,000 concurrent users | testing,automation | 14
Quality | Security review | security | 10
Deployment | Scalable hosting setup | devops,aws | 12
Deployment | Backup and rollback plan | devops | 6
""",
        decisions=[
            ("Proctoring is flag-only", "The system flags suspicious events; a human decides.",
             "Automatic penalties caused too many false positives in the pilot.", "neha", 5, 18),
        ],
    ),
    # ── 9 ─────────────────────────────────────────────────────────────────
    dict(
        title="Real-Estate Listing Site", priority="medium",
        story="Overdue tasks pile up",
        description="Property listing marketplace with search, maps and agent dashboards.",
        expect=("High risk", (0.5, 1.0)),
        params=dict(progress=0.3, slip=0.27, f=0.85, dens=0.3, growth=0.15, overdue=8, wip=5, sprints=3),
        team=[("rohan", "admin", 28), ("aarav", "member", 26), ("vikram", "member", 14),
              ("sid", "member", 18), ("meera", "member", 22)],
        tasks="""
Listings | Listing schema and photo upload | node,sql | 12
Listings | Listing creation wizard | react,typescript | 16
Listings | Listing moderation queue | react,node | 10
Search | Map-based search | react,typescript | 20
Search | Filters and saved searches | node,sql | 14
Search | Email alerts for saved searches | node | 8
Agents | Agent profiles | react,css | 8
Agents | Lead inbox | react,node | 14
Agents | Viewing appointment scheduler | react,node | 12
Agents | Agent analytics | react,typescript | 12
Design | Brand style guide | figma,ux | 8
Design | Listing page redesign | figma,ux | 10
Platform | SEO and sitemap | node | 6
Platform | Image optimisation pipeline | node,aws | 10
Platform | Rate limiting and spam protection | node,security | 8
Platform | Test suite | testing | 12
Platform | Production deployment | devops,aws | 10
""",
        decisions=[
            ("Drop the mortgage calculator for launch", "Mortgage calculator moves to phase 2.",
             "Too many open tasks are already overdue.", "rohan", None, 10),
        ],
    ),
    # ── 10 ────────────────────────────────────────────────────────────────
    dict(
        title="Travel Planner", priority="medium",
        story="Well balanced team",
        description="Trip planning app: itineraries, bookings and shared budgets.",
        expect=("Low risk", (0.0, 0.25)),
        params=dict(progress=0.4, slip=0.0, f=1.55, dens=0.25, growth=0.05, overdue=0, sprints=3),
        team=[("meera", "admin", 30), ("aarav", "member", 28), ("priya", "member", 28),
              ("vikram", "member", 20), ("karan", "member", 20), ("ananya", "member", 14)],
        tasks="""
Itinerary | Trip and day-plan schema | sql,python | 8
Itinerary | Drag-and-drop itinerary builder | react,typescript | 18
Itinerary | Map route preview | react,typescript | 12
Bookings | Flight search integration | python,fastapi | 16
Bookings | Hotel search integration | python,fastapi | 14
Bookings | Booking confirmations inbox | python | 8
Budget | Shared budget tracker | react,python | 12
Budget | Currency conversion service | python | 6
UX | Onboarding flow design | figma,ux | 10
UX | Mobile layout polish | css,ux | 8
Quality | Cross-browser tests | testing,automation | 12
Quality | API contract tests | testing,python | 10
Deployment | CI/CD and preview environments | devops,ci | 10
Deployment | Observability dashboards | devops | 8
""",
        decisions=[
            ("Aggregate providers through one adapter layer", "Flights and hotels use the same provider interface.",
             "Lets us add a provider without touching the UI.", "priya", 3, 20),
        ],
    ),
    # ── 11 ────────────────────────────────────────────────────────────────
    dict(
        title="Inventory Tracker", priority="low",
        story="Underused member available (Karan has capacity but almost no tasks)",
        description="Stock tracking for a small warehouse with barcode scanning and reorder alerts.",
        expect=("Low risk", (0.0, 0.3)),
        params=dict(progress=0.35, slip=0.0, f=1.4, dens=0.3, growth=0.05, overdue=0, idle="karan", sprints=2),
        team=[("priya", "admin", 28), ("rohan", "member", 26), ("meera", "member", 26),
              ("karan", "member", 24), ("vikram", "member", 20)],
        tasks="""
Stock | Item and location schema | sql,python | 6
Stock | Stock movement API | python,fastapi | 12
Stock | Barcode scan screen | react,typescript | 12
Alerts | Reorder level rules | python,sql | 8
Alerts | Low-stock email alerts | python | 6
Reports | Stock valuation report | python,sql | 10
Reports | Dashboard charts | react,typescript | 12
Admin | User roles and audit trail | python,security | 10
Quality | Test plan for stock counts | testing | 8
""",
        decisions=[],
    ),
    # ── 12 ────────────────────────────────────────────────────────────────
    dict(
        title="Chat Application", priority="medium",
        story="Scope creep (estimates growing)",
        description="Team chat with channels, file sharing and search. Requirements keep growing.",
        expect=("Medium risk", (0.5, 1.0)),
        params=dict(progress=0.5, slip=0.2, f=0.95, dens=0.3, growth=0.42, overdue=3,
                    creep=True, sprints=3),
        team=[("rohan", "admin", 30), ("aarav", "member", 30), ("meera", "member", 26),
              ("sid", "member", 20), ("ananya", "member", 14), ("karan", "member", 18)],
        tasks="""
Messaging | Message model and delivery | node,sql | 12
Messaging | Realtime transport | node | 14
Messaging | Channel and DM UI | react,typescript | 16
Messaging | Read receipts and typing indicators | react,node | 10
Messaging | Message edit and delete | node,react | 8
Files | File upload and previews | node,aws | 12
Files | Inline image and video viewer | react,css | 10
Search | Message full-text search | node,sql | 14
Search | Search filters by person and date | react,typescript | 8
Threads | Threaded replies | react,node | 14
Threads | Mentions and notifications | node | 12
Integrations | Slash commands | node | 12
Integrations | Webhook bots | node | 10
Integrations | Calendar integration | node | 10
Mobile | Responsive layout | react,css | 10
Mobile | Push notifications | node | 8
Quality | Message ordering tests | testing | 10
Quality | Load test 10k connections | testing,automation | 12
Deployment | Websocket scaling setup | devops,aws | 12
Deployment | Monitoring | devops | 6
""",
        decisions=[
            ("Add threads to v1", "Threaded replies are part of the first release.",
             "Requested by the pilot users; moved up from v2.", "rohan", 9, 20),
            ("Freeze scope after the next sprint", "No new features after sprint 3.",
             "Estimates have grown for three sprints in a row.", "rohan", None, 6),
        ],
    ),
    # ── 13 ────────────────────────────────────────────────────────────────
    dict(
        title="Learning Management System", priority="high",
        story="Large project, multiple sprints",
        description="Course platform with video lessons, quizzes, certificates and instructor analytics.",
        expect=("Medium risk", (0.1, 0.9)),
        params=dict(progress=0.38, slip=0.18, f=1.1, dens=0.3, growth=0.1, overdue=3, sprints=4),
        team=[("priya", "admin", 32), ("aarav", "member", 30), ("meera", "member", 28),
              ("rohan", "member", 28), ("vikram", "member", 20), ("karan", "member", 24),
              ("ananya", "member", 16), ("divya", "member", 12)],
        tasks="""
Accounts | Registration and email verification | python,fastapi | 10
Accounts | Instructor and student roles | python,security | 8
Accounts | Profile and notification settings | react,typescript | 10
Courses | Course and module schema | sql,python | 8
Courses | Course builder for instructors | react,typescript | 22
Courses | Video upload and transcoding | node,aws | 20
Courses | Lesson player with progress tracking | react,typescript | 18
Courses | Downloadable resources | node,aws | 8
Quizzes | Question types and quiz schema | sql,python | 10
Quizzes | Quiz taking interface | react,typescript | 16
Quizzes | Auto-grading and feedback | python | 14
Quizzes | Plagiarism check on assignments | python,data | 12
Learning | Course recommendations | ml,python | 16
Learning | Learner dashboard | react,css | 14
Learning | Discussion forums | react,node | 16
Learning | Live class scheduling | react,node | 12
Certificates | Certificate template designer | figma,ux | 8
Certificates | PDF certificate generation | python | 8
Certificates | Public certificate verification | python,fastapi | 6
Payments | Course purchase flow | node,security | 16
Payments | Coupons and bundles | node,sql | 10
Analytics | Instructor analytics | react,typescript | 14
Analytics | Completion funnel report | python,sql | 10
Analytics | Data export | python | 6
Platform | Accessibility audit | ux,css | 10
Platform | Internationalisation | react,typescript | 12
Platform | End-to-end tests | testing,automation | 18
Platform | Performance tuning | node,sql | 12
Platform | CI/CD pipeline | devops,ci | 10
Platform | Production monitoring | devops,aws | 8
""",
        decisions=[
            ("Transcode video with a managed service", "Use a managed transcoding service instead of running ffmpeg ourselves.",
             "Saves two weeks; cost is acceptable.", "priya", 5, 35),
            ("Recommendations start rule-based", "Ship tag-based recommendations first; ML later.",
             "The ML data does not exist until the platform has users.", "priya", 12, 18),
        ],
    ),
    # ── 14 ────────────────────────────────────────────────────────────────
    dict(
        title="Fitness Tracker", priority="low",
        story="Completed project (history for calibration)",
        description="Workout and nutrition logging app with weekly summaries. Delivered.",
        expect=("Low risk", (0.0, 0.05)),
        params=dict(progress=1.0, slip=0.0, f=1.0, dens=0.3, growth=0.12, overdue=0,
                    completed=True, sprints=3),
        team=[("arjun", "admin", 30), ("divya", "member", 22), ("aarav", "member", 16), ("karan", "member", 12)],
        tasks="""
Tracking | Workout logging screens | flutter,mobile | 14
Tracking | Exercise library | flutter,mobile | 10
Tracking | Step counter integration | flutter,mobile | 12
Nutrition | Food database search | node,sql | 12
Nutrition | Calorie summary view | flutter,mobile | 10
Insights | Weekly summary emails | node | 8
Insights | Progress charts | flutter,mobile | 12
Insights | Goal recommendation model | ml,data | 16
Social | Friends and challenges | node,flutter | 14
Social | Leaderboard | flutter,mobile | 8
Account | Sign-up and profile | node,flutter | 10
Quality | Device test matrix | testing | 12
Quality | Beta feedback fixes | flutter,mobile | 10
Release | App store submission | mobile,ci | 6
""",
        decisions=[
            ("Rule-based goals instead of ML at launch", "Weekly goals use simple rules; the model is shown as a suggestion only.",
             "Not enough user history yet.", "arjun", 7, 70),
        ],
    ),
    # ── 15 ────────────────────────────────────────────────────────────────
    dict(
        title="IoT Dashboard", priority="high",
        story="Dependencies on a late backend",
        description="Dashboard for factory sensors. The device-data backend is late and blocks most of the UI work.",
        expect=("High risk", (0.5, 1.0)),
        params=dict(progress=0.22, wip=3, slip=0.3, f=0.9, dens=0.9, growth=0.12, overdue=5, sprints=3,
                    cross=[("Dashboard", "Cloud API"), ("Alerts", "Cloud API")]),
        team=[("ananya", "admin", 28), ("rohan", "member", 28), ("divya", "member", 20),
              ("aarav", "member", 24), ("karan", "member", 14)],
        tasks="""
Firmware | Sensor message format | node,aws | 8
Firmware | Gateway simulator | node | 10
Firmware | Device provisioning script | devops,aws | 10
Cloud API | Ingestion endpoint | node,aws | 16
Cloud API | Time-series storage | sql,aws | 14
Cloud API | Query API for dashboards | node,sql | 16
Cloud API | Device registry API | node,sql | 10
Dashboard | Live sensor tiles | react,typescript | 14
Dashboard | Historical charts | react,typescript | 16
Dashboard | Device map | react,css | 12
Alerts | Threshold rules engine | node | 14
Alerts | Alert notification UI | react,typescript | 10
Analytics | Anomaly detection | ml,data | 18
Analytics | Maintenance forecast | ml,python | 16
Quality | Hardware-in-the-loop tests | testing,automation | 14
Quality | Load test with simulated devices | testing | 10
""",
        decisions=[
            ("Mock the API so the UI can move", "UI uses a mock Query API until the real one lands.",
             "The backend is late and blocks the dashboard work.", "ananya", 5, 14),
            ("Use MQTT between gateway and cloud", "Gateways publish over MQTT.",
             "Lower bandwidth than HTTP polling on factory networks.", "rohan", 3, 45),
        ],
    ),
    # ── 16 ────────────────────────────────────────────────────────────────
    dict(
        title="Event Booking System", priority="medium",
        story="Decision log heavy (use it for the M12 Ask demo)",
        description="Ticketing and seat-booking platform for college and community events.",
        expect=("Low risk", (0.0, 0.3)),
        params=dict(progress=0.42, slip=0.02, f=1.35, dens=0.3, growth=0.07, overdue=0, sprints=3),
        team=[("neha", "admin", 28), ("meera", "member", 26), ("aarav", "member", 26),
              ("vikram", "member", 16), ("karan", "member", 16)],
        tasks="""
Events | Event and venue schema | sql,python | 8
Events | Event creation form | react,typescript | 12
Events | Public event page | react,css | 12
Seating | Seat map editor | react,typescript | 20
Seating | Seat holding with 10-minute timeout | python,sql | 14
Tickets | Ticket purchase flow | react,python | 16
Tickets | QR code tickets | python | 8
Tickets | Gate scanning check-in | react,typescript | 12
Payments | Payment gateway integration | python,security | 16
Payments | Refund policy engine | python,sql | 10
Comms | Confirmation emails | python | 6
Quality | Double-booking stress tests | testing,automation | 12
Quality | Usability test with organisers | ux | 8
""",
        decisions=[
            ("Hold seats for 10 minutes", "A selected seat is held for 10 minutes during checkout.",
             "Long enough to pay, short enough to avoid empty seats at popular events.", "neha", 4, 40),
            ("Use database row locks for holds", "Seat holds use row-level locking in SQL, not a separate cache.",
             "One less system to run; traffic is modest.", "neha", 4, 38),
            ("Choose a hosted payment page", "Card entry happens on the gateway's hosted page.",
             "Keeps card data out of our system and reduces audit work.", "neha", 8, 33),
            ("Refunds only until 48 hours before the event", "No refunds in the last 48 hours.",
             "Organisers asked for it; reduces last-minute seat churn.", "meera", 9, 28),
            ("QR tickets are single-use", "Each QR code can be scanned once; re-entry needs a hand stamp.",
             "Prevents passing the same ticket to several people.", "aarav", 6, 24),
            ("Seat map built with SVG", "The editor and viewer both use SVG, not canvas.",
             "Easier accessibility and testing.", "aarav", 3, 36),
            ("Email only, no SMS", "Confirmations are sent by email only.",
             "SMS cost is not justified for free events.", "meera", 10, 20),
            ("Cap one booking at 6 seats", "A single booking is limited to 6 seats.",
             "Stops one buyer taking a whole block.", "neha", 4, 15),
        ],
    ),
]
