"""Budget aggregation."""
from typing import Any, Dict


def optimize_budget(budget, transport_cost, hotel_cost, travelers, days):
    food, act, loc, misc = 600, 500, 200, 300
    food_t = food * travelers * days
    act_t = act * travelers * days
    loc_t = loc * travelers * days
    misc_t = misc * travelers * days
    total = transport_cost + hotel_cost + food_t + act_t + loc_t + misc_t
    overshoot = total - budget
    sugg = []
    if overshoot > 0:
        sugg += ["Consider a budget hotel.","Switch flights to train.",
                  "Eat at local eateries."]
    else:
        sugg.append("Budget looks comfortable.")
    return {"budget": budget, "estimated_total": total,
            "overshoot": max(0.0, overshoot),
            "within_budget": total <= budget,
            "breakdown": {"transport": transport_cost, "hotel": hotel_cost,
                           "food": food_t, "activities": act_t,
                           "local_transport": loc_t, "misc": misc_t},
            "per_person_per_day": food + act + loc + misc,
            "suggestions": sugg, "currency": "INR"}
