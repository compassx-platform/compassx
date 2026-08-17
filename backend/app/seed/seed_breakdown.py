"""
Seed script: upsert the breakdown_event_form schema into the forms table.

Run with:
    python -m backend.app.seed.seed_breakdown
or via the create_db.py helper.
"""

import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.form import Form

logger = logging.getLogger(__name__)

BREAKDOWN_FORM_ID = "breakdown_event_form"
BREAKDOWN_ENTITY = "breakdown_event"

BREAKDOWN_SCHEMA = {
    "form_id": BREAKDOWN_FORM_ID,
    "entity": BREAKDOWN_ENTITY,
    "fields": [
        # ── Row 1: Event Date (col 0-3) | Scheduled (col 3-6) | Impact Type (col 6-9) | Loss Category (col 9-12)
        {
            "id": "event_date",
            "type": "date",
            "label": "Event Date",
            "required": True,
            "default_value": "today",
            "layout": {"x": 0, "y": 0, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "scheduled",
            "type": "toggle",
            "label": "Scheduled / Unscheduled",
            "required": True,
            "default_value": "Unscheduled",
            "options": ["Unscheduled", "Scheduled"],
            "layout": {"x": 3, "y": 0, "w": 3, "h": 5, "minW": 3, "minH": 4},
        },
        {
            "id": "impact_type",
            "type": "toggle",
            "label": "Impact Type",
            "required": True,
            "options": ["Availability", "Performance"],
            "layout": {"x": 6, "y": 0, "w": 3, "h": 5, "minW": 3, "minH": 4},
        },
        {
            "id": "loss_category",
            "type": "toggle",
            "label": "Loss Category",
            "required": True,
            "options": ["Known", "Unforeseen", "Curtailment", "Soiling"],
            "layout": {"x": 9, "y": 0, "w": 3, "h": 5, "minW": 3, "minH": 4},
        },
        # ── Row 2: Equipment Category (full width toggle)
        {
            "id": "equipment_category",
            "type": "toggle",
            "label": "Equipment Category",
            "required": True,
            "options": [
                "Inverter", "IDT", "Power Trafo", "Grid",
                "SCB Cable", "Module", "String Cable",
                "Tracker", "ICR Switchgear", "Internal TL",
            ],
            "layout": {"x": 0, "y": 5, "w": 12, "h": 5, "minW": 6, "minH": 4},
        },
        # ── Row 3: Block No | Inverter | Inverter Slot | SCB No
        {
            "id": "block_no",
            "type": "dropdown",
            "label": "Block No.",
            "required": False,
            "options": ["Block 1", "Block 2", "Block 3", "Block 4A", "Block 4B", "Block 5"],
            "layout": {"x": 0, "y": 10, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "inverter_name",
            "type": "async_select",
            "label": "Inverter",
            "required": True,
            "data_source": {
                "type": "api",
                "endpoint": "/proxy/assets",
                "filter_by_type_name": "Inverter",
            },
            "layout": {"x": 3, "y": 10, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "inverter_slot",
            "type": "string",
            "label": "Inverter Slot / Unit",
            "required": False,
            "layout": {"x": 6, "y": 10, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "scb_no",
            "type": "string",
            "label": "SCB No.",
            "required": False,
            "layout": {"x": 9, "y": 10, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        # ── Row 4: Sub Category | Fault Code | Grid Outage Flag
        {
            "id": "sub_category",
            "type": "conditional_dropdown",
            "label": "Sub Category",
            "required": False,
            "depends_on": "equipment_category",
            "options_map": {
                "Inverter": [
                    "Inverter GFDI Failure", "Inverter IGBT Failure",
                    "Inverter AC Over current", "Inverter Manual Trip",
                    "Inverter AC UV & OV",
                ],
                "IDT": [
                    "IDT LV Bushing Damage", "IDT Bucholz",
                    "IDT Over Voltage", "IDT Manual Trip", "IDT WTI",
                ],
                "Power Trafo": [
                    "Power Trafo OTI", "Power Trafo PRV",
                    "Power Trafo Overcurrent / Earth Fault",
                    "Power Trafo Under Voltage",
                ],
                "Grid": [
                    "Grid Failure", "Grid Load Curtailment",
                    "Grid Load Shedding", "Grid Force Majeure", "GSS RPR",
                ],
                "SCB Cable": [
                    "SCB Cable / DC Cable Burn",
                    "SCB Cable / DC Cable Insulation Failure",
                    "SCB Cable / DC Cable Joint Failure",
                ],
                "Module": [
                    "Module Burn", "Module Physical Damage",
                    "Module Junction Box Damage",
                ],
                "String Cable": ["String Cable UG Short Circuit"],
                "ICR Switchgear": [
                    "ICR Switchgear CT Failure",
                    "ICR Switchgear Vacuum Chamber Failure",
                    "ICR Switchgear TTB Failure",
                    "ICR Switchgear Annunciator Failure",
                    "ICR Switchgear Power Pack",
                ],
                "Tracker": ["Tracker Controller Node"],
                "Internal TL": [
                    "Internal TL Overhead Replacement",
                    "Internal TL Overhead Earth Fault",
                ],
            },
            "layout": {"x": 0, "y": 14, "w": 4, "h": 4, "minW": 3, "minH": 3},
        },
        {
            "id": "fault_code",
            "type": "string",
            "label": "Fault / Error Code",
            "required": False,
            "layout": {"x": 4, "y": 14, "w": 4, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "grid_outage_flag",
            "type": "toggle",
            "label": "Grid Outage Flag",
            "required": False,
            "default_value": "No",
            "options": ["Yes", "No"],
            "layout": {"x": 8, "y": 14, "w": 4, "h": 5, "minW": 3, "minH": 4},
        },
        # ── Row 5: Fault Start | Fault End | POA Irradiation
        {
            "id": "fault_from",
            "type": "time",
            "label": "Fault Start Time",
            "required": True,
            "layout": {"x": 0, "y": 19, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "fault_to",
            "type": "time",
            "label": "Fault End Time",
            "required": True,
            "layout": {"x": 3, "y": 19, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "poa_irradiation",
            "type": "number",
            "label": "POA Irradiation (kWh/m²)",
            "required": False,
            "layout": {"x": 6, "y": 19, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
        # ── Row 6: Reason / Fault Description (full width)
        {
            "id": "reason",
            "type": "textarea",
            "label": "Reason / Fault Description",
            "required": True,
            "layout": {"x": 0, "y": 23, "w": 12, "h": 6, "minW": 6, "minH": 4},
        },
        # ── Row 7: Final Loss Bifurcation | Resolution Date | Resolution Time
        {
            "id": "final_loss_bifurcation",
            "type": "dropdown",
            "label": "Final Loss Bifurcation",
            "required": False,
            "options": [
                "MTPL", "Force Majeure", "Grid", "Soiling",
                "Clipping", "Scheduled Maintenance", "Equipment Failure",
            ],
            "layout": {"x": 0, "y": 29, "w": 4, "h": 4, "minW": 3, "minH": 3},
        },
        {
            "id": "resolution_date",
            "type": "date",
            "label": "Resolution Date",
            "required": False,
            "default_value": "today",
            "layout": {"x": 4, "y": 29, "w": 4, "h": 4, "minW": 2, "minH": 3},
        },
        {
            "id": "resolution_time",
            "type": "time",
            "label": "Resolution Time",
            "required": False,
            "layout": {"x": 8, "y": 29, "w": 4, "h": 4, "minW": 2, "minH": 3},
        },
        # ── Row 8: Standard Action | Scope | Status
        {
            "id": "standard_action",
            "type": "dropdown",
            "label": "Standard Action Taken",
            "required": True,
            "options": [
                "Manual Reset", "Component Replacement",
                "Cleaning / Maintenance", "Grid Restored",
                "Relay Reset", "IGBT Replacement", "Cable Replacement",
                "Busbar Replacement", "Bypass & Charge",
                "OEM Called", "Under Investigation",
            ],
            "layout": {"x": 0, "y": 33, "w": 4, "h": 4, "minW": 3, "minH": 3},
        },
        {
            "id": "scope",
            "type": "dropdown",
            "label": "Scope",
            "required": False,
            "default_value": "Contractor",
            "options": ["Contractor", "In-house", "OEM"],
            "layout": {"x": 4, "y": 33, "w": 4, "h": 4, "minW": 3, "minH": 3},
        },
        {
            "id": "status",
            "type": "dropdown",
            "label": "Status",
            "required": True,
            "default_value": "Open",
            "options": ["Open", "Resolved", "Pending OEM", "Monitoring"],
            "layout": {"x": 8, "y": 33, "w": 4, "h": 4, "minW": 3, "minH": 3},
        },
        # ── Row 9: Action Remark (full width) | External Reference
        {
            "id": "action_remark",
            "type": "textarea",
            "label": "Action Remark",
            "required": False,
            "layout": {"x": 0, "y": 37, "w": 9, "h": 5, "minW": 6, "minH": 4},
        },
        {
            "id": "external_reference",
            "type": "string",
            "label": "External Reference",
            "required": False,
            "layout": {"x": 9, "y": 37, "w": 3, "h": 4, "minW": 2, "minH": 3},
        },
    ],
}


def seed():
    """Upsert the breakdown_event_form schema. Safe to run multiple times."""
    db: Session = SessionLocal()
    try:
        existing = db.query(Form).filter(Form.form_id == BREAKDOWN_FORM_ID).first()
        if existing:
            existing.entity_name = BREAKDOWN_ENTITY
            existing.schema = BREAKDOWN_SCHEMA
            db.commit()
            logger.info("Updated breakdown_event_form schema.")
            print("✔ Updated breakdown_event_form.")
        else:
            db.add(Form(
                form_id=BREAKDOWN_FORM_ID,
                entity_name=BREAKDOWN_ENTITY,
                schema=BREAKDOWN_SCHEMA,
            ))
            db.commit()
            logger.info("Created breakdown_event_form schema.")
            print("✔ Created breakdown_event_form.")
    except Exception as exc:
        db.rollback()
        logger.error("Seed failed: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    import os
    # Allow running as: python backend/app/seed/seed_breakdown.py
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    seed()
