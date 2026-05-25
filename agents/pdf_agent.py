"""PDF generator agent."""
from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from config import settings
from state import TripState
from tools.guardrails import redact_dict


def _styles():
    b = getSampleStyleSheet()
    b.add(ParagraphStyle(name="Cover", parent=b["Title"], fontSize=28, leading=34,
                          textColor=colors.HexColor("#1f4e79"), alignment=1, spaceAfter=20))
    b.add(ParagraphStyle(name="Section", parent=b["Heading1"], fontSize=18,
                          textColor=colors.HexColor("#1f4e79"), spaceBefore=12, spaceAfter=8))
    b.add(ParagraphStyle(name="Sub", parent=b["Heading2"], fontSize=13,
                          textColor=colors.HexColor("#365f91"), spaceBefore=8, spaceAfter=4))
    b.add(ParagraphStyle(name="Body", parent=b["BodyText"], fontSize=10.5, leading=15))
    return b


def _kv(rows, widths=(5*cm, 11*cm)):
    t = Table(rows, colWidths=list(widths))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eef3f9")),
        ("BOX", (0,0), (-1,-1), 0.4, colors.HexColor("#90a5c2")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#c4d2e6")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    return t


def _grid(header, rows, widths=None):
    t = Table([header] + rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9.5),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#90a5c2")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f6f9fd")]),
    ]))
    return t


def _build_pdf(state, out_path):
    state = redact_dict(dict(state))
    p = state.get("trip_preferences", {})
    w = state.get("weather_data", {})
    tr = state.get("transport_data", {})
    h = state.get("hotel_data", {})
    pl = state.get("places_data", {})
    b = state.get("budget_summary", {})
    it = state.get("itinerary", {})

    s = _styles()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                             leftMargin=2*cm, rightMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm,
                             title=f"Trip Plan: {p.get('destination','')}")
    story = []
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("Your Personalized Trip Plan", s["Cover"]))
    story.append(Paragraph(f"<b>{p.get('source','?')}</b> → <b>{p.get('destination','?')}</b>",
                            ParagraphStyle("c", parent=s["Body"], alignment=1, fontSize=16)))
    story.append(_kv([
        ["Travel Dates", f"{p.get('start_date','TBD')} → {p.get('end_date','TBD')}"],
        ["Duration", f"{p.get('duration_days','?')} days"],
        ["Travelers", f"{p.get('travelers',1)} ({p.get('travel_type','n/a')})"],
        ["Budget", f"{p.get('currency','INR')} {p.get('budget','?')}"],
        ["Hotel", p.get("hotel_pref","mid")],
        ["Transport", p.get("transport_pref","flight")],
        ["Interests", ", ".join(p.get("interests",[]) or []) or "General sightseeing"],
    ]))
    story.append(PageBreak())

    story.append(Paragraph("Weather Forecast", s["Section"]))
    days = w.get("forecast", [])
    if days:
        rows = [[d.get("date"), d.get("summary"),
                 f"{d.get('temp_min_c')}-{d.get('temp_max_c')}C",
                 f"{d.get('rain_mm',0)}mm"] for d in days]
        story.append(_grid(["Date","Conditions","Temp","Rain"], rows))
    story.append(PageBreak())

    story.append(Paragraph("Flights & Transport", s["Section"]))
    flights = tr.get("flights", {}).get("options", [])
    if flights:
        rows = [[f["airline"], f["flight_no"], f"{f['depart']}-{f['arrive']}",
                 f["duration"], f"Rs {f['price_per_person']}", f"Rs {f['total_price']}"]
                for f in flights]
        story.append(_grid(["Airline","Flight","Time","Duration","Per pax","Total"], rows))
    story.append(PageBreak())

    story.append(Paragraph("Hotel Recommendations", s["Section"]))
    opts = h.get("options", [])
    if opts:
        rows = [[o["name"], o["band"], f"{o['rating']}", f"Rs {o['per_night']}",
                 f"Rs {o['total']}"] for o in opts]
        story.append(_grid(["Hotel","Tier","Rating","Per night","Total"], rows))
    story.append(PageBreak())

    story.append(Paragraph("Day-wise Itinerary", s["Section"]))
    for d in it.get("days", []):
        story.append(Paragraph(f"Day {d['day']} — {d.get('date','')}: {d.get('title','')}", s["Sub"]))
        story.append(_kv([
            ["Morning", d.get("morning","")],
            ["Afternoon", d.get("afternoon","")],
            ["Evening", d.get("evening","")],
            ["Meals", ", ".join(d.get("meals",[]) or [])],
            ["Notes", d.get("notes","")],
        ]))
        story.append(Spacer(1, 0.4*cm))
    story.append(PageBreak())

    story.append(Paragraph("Budget Report", s["Section"]))
    if b:
        br = b["breakdown"]
        rows = [["Transport", f"Rs {int(br['transport'])}"],
                ["Hotel", f"Rs {int(br['hotel'])}"],
                ["Food", f"Rs {int(br['food'])}"],
                ["Activities", f"Rs {int(br['activities'])}"],
                ["Local Transport", f"Rs {int(br['local_transport'])}"],
                ["Misc", f"Rs {int(br['misc'])}"],
                ["TOTAL", f"Rs {int(b['estimated_total'])}"],
                ["Budget", f"Rs {int(b['budget'])}"],
                ["Status", "Within budget" if b['within_budget'] else f"Over by Rs {int(b['overshoot'])}"]]
        story.append(_kv(rows))
    story.append(PageBreak())

    story.append(Paragraph("Packing Checklist", s["Section"]))
    items = ["Govt ID + copies", "Tickets / bookings", "Power bank + chargers",
             "Toiletries + medication", "Sunscreen + sunglasses",
             "Weather-appropriate clothing", "First-aid kit", "Cash + cards"]
    for i in items:
        story.append(Paragraph(f"☐ {i}", s["Body"]))
    story.append(PageBreak())

    story.append(Paragraph("Emergency Contacts", s["Section"]))
    story.append(_kv([["Police","100"],["Ambulance","108"],["Tourist Helpline","1363"]]))

    doc.build(story)


def pdf_generator_agent(state: TripState) -> Dict[str, Any]:
    review = state.get("review_status", {}) or {}
    if not review.get("approved", False):
        return {"pdf_status": {"generated": False}}
    out_dir = settings.outputs_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = state.get("trip_preferences", {}).get("destination", "trip").replace(" ", "_")
    fn = f"TripPlan_{dest}_{uuid.uuid4().hex[:6]}.pdf"
    path = out_dir / fn
    _build_pdf(state, path)
    return {"pdf_status": {"generated": True, "path": str(path), "filename": fn},
            "pdf_path": str(path),
            "final_message": "Thank you, happy journey!"}
