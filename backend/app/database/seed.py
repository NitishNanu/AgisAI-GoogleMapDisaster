from geoalchemy2.elements import WKTElement

from app.database.session import SessionLocal
from app.models.disaster import Disaster
from app.models.hospital import Hospital
from app.models.rescue_team import RescueTeam
from app.models.shelter import Shelter
from app.models.user import User


def seed_database():

    db = SessionLocal()

    try:

        # ============================================================
        # FIND EXISTING USER
        # ============================================================
        #
        # Your disasters table requires reported_by.
        # Therefore, we use an existing user as the demo reporter.
        #

        reporter = (
            db.query(User)
            .order_by(User.id)
            .first()
        )

        if reporter is None:

            raise RuntimeError(
                "No user found in the database. "
                "Please create a user first using the "
                "registration API and then run the seed again."
            )

        print(
            f"Using user ID {reporter.id} "
            f"as demo disaster reporter."
        )


        # ============================================================
        # CLEAR EXISTING DEMO DATA
        # ============================================================
        #
        # WARNING:
        # This deletes existing demo disasters, teams,
        # hospitals and shelters.
        #
        # Do NOT use this against a production database.
        #

        db.query(Disaster).delete(
            synchronize_session=False
        )

        db.query(RescueTeam).delete(
            synchronize_session=False
        )

        db.query(Hospital).delete(
            synchronize_session=False
        )

        db.query(Shelter).delete(
            synchronize_session=False
        )

        db.commit()


        # ============================================================
        # RESCUE TEAMS
        # ============================================================

        rescue_teams = [

            RescueTeam(
                team_name="Chandigarh Rescue Team 1",
                vehicle_type="AMBULANCE",
                members=6,
                status="AVAILABLE",

                latitude=30.7335,
                longitude=76.7794,

                location=WKTElement(
                    "POINT(76.7794 30.7335)",
                    srid=4326
                )
            ),

            RescueTeam(
                team_name="Chandigarh Fire & Rescue 2",
                vehicle_type="FIRE_TRUCK",
                members=8,
                status="AVAILABLE",

                latitude=30.7410,
                longitude=76.7680,

                location=WKTElement(
                    "POINT(76.7680 30.7410)",
                    srid=4326
                )
            ),

            RescueTeam(
                team_name="Sector 17 Emergency Unit",
                vehicle_type="RESCUE_VAN",
                members=5,
                status="AVAILABLE",

                latitude=30.7400,
                longitude=76.7930,

                location=WKTElement(
                    "POINT(76.7930 30.7400)",
                    srid=4326
                )
            ),

            RescueTeam(
                team_name="Mohali Disaster Response Team",
                vehicle_type="AMBULANCE",
                members=5,
                status="AVAILABLE",

                latitude=30.7046,
                longitude=76.7179,

                location=WKTElement(
                    "POINT(76.7179 30.7046)",
                    srid=4326
                )
            ),

            RescueTeam(
                team_name="Panchkula Emergency Team",
                vehicle_type="RESCUE_VAN",
                members=7,
                status="AVAILABLE",

                latitude=30.6942,
                longitude=76.8606,

                location=WKTElement(
                    "POINT(76.8606 30.6942)",
                    srid=4326
                )
            ),

            RescueTeam(
                team_name="Rapid Response Unit 6",
                vehicle_type="FIRE_TRUCK",
                members=9,
                status="AVAILABLE",

                latitude=30.7500,
                longitude=76.8100,

                location=WKTElement(
                    "POINT(76.8100 30.7500)",
                    srid=4326
                )
            )

        ]

        db.add_all(rescue_teams)


        # ============================================================
        # HOSPITALS
        # ============================================================

        hospitals = [

            Hospital(
                name="Government Multi-Specialty Hospital",

                beds=500,

                icu_beds=80,

                oxygen_available=True,

                latitude=30.7352,
                longitude=76.7756,

                location=WKTElement(
                    "POINT(76.7756 30.7352)",
                    srid=4326
                )
            ),

            Hospital(
                name="PGI Emergency Medical Center",

                beds=900,

                icu_beds=150,

                oxygen_available=True,

                latitude=30.7646,
                longitude=76.7754,

                location=WKTElement(
                    "POINT(76.7754 30.7646)",
                    srid=4326
                )
            ),

            Hospital(
                name="Sector 32 Emergency Hospital",

                beds=400,

                icu_beds=60,

                oxygen_available=True,

                latitude=30.7057,
                longitude=76.7947,

                location=WKTElement(
                    "POINT(76.7947 30.7057)",
                    srid=4326
                )
            ),

            Hospital(
                name="Fortis Mohali Emergency Center",

                beds=350,

                icu_beds=55,

                oxygen_available=True,

                latitude=30.6942,
                longitude=76.7160,

                location=WKTElement(
                    "POINT(76.7160 30.6942)",
                    srid=4326
                )
            ),

            Hospital(
                name="Civil Hospital Panchkula",

                beds=300,

                icu_beds=40,

                oxygen_available=True,

                latitude=30.6946,
                longitude=76.8500,

                location=WKTElement(
                    "POINT(76.8500 30.6946)",
                    srid=4326
                )
            )

        ]

        db.add_all(hospitals)


        # ============================================================
        # SHELTERS
        # ============================================================

        shelters = [

            Shelter(
                name="Sector 17 Community Shelter",

                capacity=1000,

                available_space=750,

                latitude=30.7398,
                longitude=76.7821,

                location=WKTElement(
                    "POINT(76.7821 30.7398)",
                    srid=4326
                )
            ),

            Shelter(
                name="Sector 22 Emergency Shelter",

                capacity=700,

                available_space=520,

                latitude=30.7339,
                longitude=76.7727,

                location=WKTElement(
                    "POINT(76.7727 30.7339)",
                    srid=4326
                )
            ),

            Shelter(
                name="Manimajra Relief Center",

                capacity=800,

                available_space=600,

                latitude=30.7232,
                longitude=76.8320,

                location=WKTElement(
                    "POINT(76.8320 30.7232)",
                    srid=4326
                )
            ),

            Shelter(
                name="Mohali Community Relief Center",

                capacity=600,

                available_space=420,

                latitude=30.7045,
                longitude=76.7178,

                location=WKTElement(
                    "POINT(76.7178 30.7045)",
                    srid=4326
                )
            ),

            Shelter(
                name="Panchkula Disaster Shelter",

                capacity=900,

                available_space=650,

                latitude=30.6970,
                longitude=76.8600,

                location=WKTElement(
                    "POINT(76.8600 30.6970)",
                    srid=4326
                )
            ),

            Shelter(
                name="Sector 35 Relief Camp",

                capacity=500,

                available_space=350,

                latitude=30.7120,
                longitude=76.7650,

                location=WKTElement(
                    "POINT(76.7650 30.7120)",
                    srid=4326
                )
            )

        ]

        db.add_all(shelters)


        # ============================================================
        # DISASTERS
        # ============================================================

        disasters = [

            Disaster(
                title="Industrial Fire",

                description=(
                    "Large industrial fire requiring "
                    "immediate fire and medical response."
                ),

                disaster_type="FIRE",

                severity="CRITICAL",

                status="ACTIVE",

                latitude=30.7415,
                longitude=76.7785,

                # IMPORTANT:
                # reported_by is NOT NULL in your database.
                reported_by=reporter.id,

                location=WKTElement(
                    "POINT(76.7785 30.7415)",
                    srid=4326
                )
            ),


            Disaster(
                title="Building Collapse",

                description=(
                    "Partial building collapse with "
                    "possible trapped civilians."
                ),

                disaster_type="BUILDING_COLLAPSE",

                severity="CRITICAL",

                status="ACTIVE",

                latitude=30.7330,
                longitude=76.7850,

                reported_by=reporter.id,

                location=WKTElement(
                    "POINT(76.7850 30.7330)",
                    srid=4326
                )
            ),


            Disaster(
                title="Major Flood Near Sector 17",

                description=(
                    "Flooding reported around roads "
                    "near Sector 17."
                ),

                disaster_type="FLOOD",

                severity="HIGH",

                status="ACTIVE",

                latitude=30.7355,
                longitude=76.7900,

                reported_by=reporter.id,

                location=WKTElement(
                    "POINT(76.7900 30.7355)",
                    srid=4326
                )
            ),


            Disaster(
                title="Road Accident NH-5",

                description=(
                    "Major road accident requiring "
                    "ambulance and rescue response."
                ),

                disaster_type="ACCIDENT",

                severity="HIGH",

                status="ACTIVE",

                latitude=30.7505,
                longitude=76.8105,

                reported_by=reporter.id,

                location=WKTElement(
                    "POINT(76.8105 30.7505)",
                    srid=4326
                )
            ),


            Disaster(
                title="Gas Leak Industrial Area",

                description=(
                    "Potential hazardous gas leak "
                    "requiring emergency response."
                ),

                disaster_type="GAS_LEAK",

                severity="CRITICAL",

                status="ACTIVE",

                latitude=30.7150,
                longitude=76.7600,

                reported_by=reporter.id,

                location=WKTElement(
                    "POINT(76.7600 30.7150)",
                    srid=4326
                )
            ),


            Disaster(
                title="Flash Flood Mohali",

                description=(
                    "Flash flooding reported in "
                    "the Mohali area."
                ),

                disaster_type="FLOOD",

                severity="MEDIUM",

                status="ACTIVE",

                latitude=30.7040,
                longitude=76.7200,

                reported_by=reporter.id,

                location=WKTElement(
                    "POINT(76.7200 30.7040)",
                    srid=4326
                )
            )

        ]

        db.add_all(disasters)


        # ============================================================
        # SAVE EVERYTHING
        # ============================================================

        db.commit()


        # ============================================================
        # SUCCESS MESSAGE
        # ============================================================

        print()
        print("=" * 65)
        print("          RescueNet AI Database Seeded")
        print("=" * 65)
        print()
        print(f"Reporter      : User ID {reporter.id}")
        print("Rescue Teams  : 6")
        print("Hospitals     : 5")
        print("Shelters      : 6")
        print("Disasters     : 6")
        print()
        print("Demo location : Chandigarh / Mohali / Panchkula")
        print()
        print("Disasters:")
        print("  1. Industrial Fire")
        print("  2. Building Collapse")
        print("  3. Major Flood Near Sector 17")
        print("  4. Road Accident NH-5")
        print("  5. Gas Leak Industrial Area")
        print("  6. Flash Flood Mohali")
        print()
        print("Rescue Teams:")
        print("  1. Chandigarh Rescue Team 1")
        print("  2. Chandigarh Fire & Rescue 2")
        print("  3. Sector 17 Emergency Unit")
        print("  4. Mohali Disaster Response Team")
        print("  5. Panchkula Emergency Team")
        print("  6. Rapid Response Unit 6")
        print()
        print("=" * 65)


    except Exception as error:

        db.rollback()

        print()
        print("=" * 65)
        print("          Database Seeding Failed")
        print("=" * 65)
        print()
        print(error)
        print()

        raise


    finally:

        db.close()


# ================================================================
# RUN SCRIPT
# ================================================================

if __name__ == "__main__":

    seed_database()
